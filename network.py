"""Transport UDP LAN defensif et observable.

Les messages applicatifs restent des objets JSON. Les charges utiles sont
compressees puis, si necessaire, fragmentees en datagrammes de 1 200 octets
maximum afin d'eviter la fragmentation IP sur les chemins IPv4/IPv6 usuels.
La reconstitution est bornee en taille, en nombre et dans le temps.
"""

from __future__ import annotations

import json
import secrets
import socket
import struct
import sys
import time
import zlib
from dataclasses import asdict, dataclass

DEFAULT_PORT = 5577
BUFFER_SIZE = 65507
MAX_MESSAGES_PER_TICK = 128
MAX_RAW_DATAGRAMS_PER_TICK = 512
SAFE_DATAGRAM_SIZE = 1200
UDP_COMPRESS_THRESHOLD = 900
MAX_DECOMPRESSED_SIZE = BUFFER_SIZE
COMPRESSED_PREFIX = b"Z1"
FRAGMENT_PREFIX = b"F1"
FRAGMENT_HEADER = struct.Struct("!IHH")  # identifiant, index, total
FRAGMENT_PAYLOAD_SIZE = SAFE_DATAGRAM_SIZE - len(FRAGMENT_PREFIX) - FRAGMENT_HEADER.size
MAX_FRAGMENT_SETS = 64
FRAGMENT_TTL = 2.0
SOURCE_RATE = 256.0
SOURCE_BURST = 384.0
SOURCE_BUCKET_TTL = 30.0
MAX_SOURCE_BUCKETS = 1024


@dataclass
class NetworkMetrics:
    """Compteurs monotones exportables dans un diagnostic de partie."""

    sent_messages: int = 0
    sent_datagrams: int = 0
    sent_bytes: int = 0
    send_errors: int = 0
    received_datagrams: int = 0
    received_bytes: int = 0
    received_messages: int = 0
    invalid_datagrams: int = 0
    rate_limited: int = 0
    fragmented_messages: int = 0
    reassembled_messages: int = 0

    def snapshot(self):
        return asdict(self)


class UdpPeer:
    """Extremite UDP non bloquante (hote si ``port`` est fourni)."""

    def __init__(self, port=None, *, clock=time.monotonic):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self._clock = clock
        self.metrics = NetworkMetrics()
        self._fragments = {}
        self._source_buckets = {}
        if port is not None:
            try:
                if sys.platform == "win32":
                    self.sock.setsockopt(
                        socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1,
                    )
                # Ne jamais activer SO_REUSEADDR ici. Sous Linux/macOS comme
                # sous Windows, un hote doit posseder son port exclusivement.
                self.sock.bind(("", port))
            except OSError:
                self.sock.close()
                raise

    def _ensure_state(self):
        """Initialise l'etat aussi pour les doubles de socket des tests."""
        if not hasattr(self, "_clock"):
            self._clock = time.monotonic
        if not hasattr(self, "metrics"):
            self.metrics = NetworkMetrics()
        if not hasattr(self, "_fragments"):
            self._fragments = {}
        if not hasattr(self, "_source_buckets"):
            self._source_buckets = {}

    def _encode(self, message, compress):
        data = json.dumps(message, separators=(",", ":")).encode("utf-8")
        if len(data) > BUFFER_SIZE:
            raise ValueError("message UDP trop volumineux")
        if compress and len(data) >= UDP_COMPRESS_THRESHOLD:
            compressed = COMPRESSED_PREFIX + zlib.compress(data, level=3)
            if len(compressed) < len(data):
                data = compressed
        return data

    def send(self, message, addr, compress=False):
        """Envoie un objet JSON et retourne ``True`` en cas de succes complet."""
        self._ensure_state()
        try:
            data = self._encode(message, compress)
            datagrams = [data]
            if len(data) > SAFE_DATAGRAM_SIZE:
                message_id = secrets.randbits(32)
                chunks = [
                    data[offset:offset + FRAGMENT_PAYLOAD_SIZE]
                    for offset in range(0, len(data), FRAGMENT_PAYLOAD_SIZE)
                ]
                if len(chunks) > 0xFFFF:
                    raise ValueError("trop de fragments UDP")
                datagrams = [
                    FRAGMENT_PREFIX
                    + FRAGMENT_HEADER.pack(message_id, index, len(chunks))
                    + chunk
                    for index, chunk in enumerate(chunks)
                ]
                self.metrics.fragmented_messages += 1
            for datagram in datagrams:
                sent = self.sock.sendto(datagram, addr)
                if sent is not None and sent != len(datagram):
                    raise OSError("datagramme UDP envoye partiellement")
                sent = len(datagram) if sent is None else sent
                self.metrics.sent_datagrams += 1
                self.metrics.sent_bytes += sent
            self.metrics.sent_messages += 1
            return True
        except (OSError, TypeError, ValueError, RecursionError):
            self.metrics.send_errors += 1
            return False

    def _source_allowed(self, addr, now):
        source = addr[0]
        tokens, updated = self._source_buckets.get(
            source, (SOURCE_BURST, now),
        )
        tokens = min(SOURCE_BURST, tokens + (now - updated) * SOURCE_RATE)
        if tokens < 1.0:
            self._source_buckets[source] = (tokens, now)
            self.metrics.rate_limited += 1
            return False
        self._source_buckets[source] = (tokens - 1.0, now)
        return True

    def _prune_fragments(self, now):
        stale = [
            key for key, state in self._fragments.items()
            if now - state["created"] > FRAGMENT_TTL
        ]
        for key in stale:
            del self._fragments[key]
            self.metrics.invalid_datagrams += 1
        if len(self._fragments) > MAX_FRAGMENT_SETS:
            oldest = sorted(
                self._fragments,
                key=lambda key: self._fragments[key]["created"],
            )
            for key in oldest[:len(self._fragments) - MAX_FRAGMENT_SETS]:
                del self._fragments[key]
                self.metrics.invalid_datagrams += 1
        stale_sources = [
            source for source, (_tokens, updated) in self._source_buckets.items()
            if now - updated > SOURCE_BUCKET_TTL
        ]
        for source in stale_sources:
            del self._source_buckets[source]
        if len(self._source_buckets) > MAX_SOURCE_BUCKETS:
            oldest_sources = sorted(
                self._source_buckets,
                key=lambda source: self._source_buckets[source][1],
            )
            for source in oldest_sources[:len(self._source_buckets) - MAX_SOURCE_BUCKETS]:
                del self._source_buckets[source]

    def _reassemble(self, data, addr, now):
        header_size = len(FRAGMENT_PREFIX) + FRAGMENT_HEADER.size
        if len(data) <= header_size:
            return None
        message_id, index, total = FRAGMENT_HEADER.unpack_from(
            data, len(FRAGMENT_PREFIX),
        )
        if total < 2 or index >= total or total > 128:
            return None
        payload = data[header_size:]
        key = (addr, message_id)
        state = self._fragments.get(key)
        if state is None:
            state = {"created": now, "total": total, "parts": {}, "size": 0}
            self._fragments[key] = state
        if state["total"] != total:
            del self._fragments[key]
            return None
        if index not in state["parts"]:
            state["parts"][index] = payload
            state["size"] += len(payload)
        if state["size"] > BUFFER_SIZE:
            del self._fragments[key]
            return None
        if len(state["parts"]) != total:
            return b""
        try:
            complete = b"".join(state["parts"][part] for part in range(total))
        except KeyError:
            return b""
        del self._fragments[key]
        self.metrics.reassembled_messages += 1
        return complete

    @staticmethod
    def _decode(data):
        if data.startswith(COMPRESSED_PREFIX):
            inflater = zlib.decompressobj()
            data = inflater.decompress(
                data[len(COMPRESSED_PREFIX):], MAX_DECOMPRESSED_SIZE + 1,
            )
            if (len(data) > MAX_DECOMPRESSED_SIZE
                    or not inflater.eof
                    or inflater.unused_data
                    or inflater.unconsumed_tail):
                raise ValueError("charge compressee invalide")
        message = json.loads(data.decode("utf-8"))
        if not isinstance(message, dict):
            raise ValueError("la racine JSON doit etre un objet")
        return message

    def receive(self, limit=MAX_MESSAGES_PER_TICK):
        """Draine la socket et retourne une liste ``(message, adresse)``."""
        self._ensure_state()
        accepted_limit = max(0, min(int(limit), MAX_MESSAGES_PER_TICK))
        messages = []
        now = self._clock()
        self._prune_fragments(now)
        raw_limit = min(MAX_RAW_DATAGRAMS_PER_TICK, accepted_limit)
        for _ in range(raw_limit):
            try:
                data, addr = self.sock.recvfrom(SAFE_DATAGRAM_SIZE + 1)
            except BlockingIOError:
                break
            except OSError:
                break
            self.metrics.received_datagrams += 1
            self.metrics.received_bytes += len(data)
            if len(data) > SAFE_DATAGRAM_SIZE or not self._source_allowed(addr, now):
                if len(data) > SAFE_DATAGRAM_SIZE:
                    self.metrics.invalid_datagrams += 1
                continue
            if data.startswith(FRAGMENT_PREFIX):
                data = self._reassemble(data, addr, now)
                if data == b"":
                    continue
                if data is None:
                    self.metrics.invalid_datagrams += 1
                    continue
            if len(messages) >= accepted_limit:
                continue
            try:
                message = self._decode(data)
            except (ValueError, UnicodeDecodeError, RecursionError, zlib.error):
                self.metrics.invalid_datagrams += 1
                continue
            messages.append((message, addr))
            self.metrics.received_messages += 1
        return messages

    def diagnostics(self):
        """Retourne une copie serialisable des compteurs du transport."""
        return self.metrics.snapshot()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
