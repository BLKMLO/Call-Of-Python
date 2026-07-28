"""Couche réseau LAN — bibliothèque standard uniquement.

Des datagrammes UDP transportant du JSON compact : suffisant pour un
réseau local (latence négligeable, pertes rares, et le protocole de
`coop.py` tolère la perte d'instantanés puisque chacun écrase le
précédent). Les sockets sont non bloquantes et lues dans la boucle de
jeu : aucun thread.
"""

import json
import socket
import sys
import zlib

DEFAULT_PORT = 5577
BUFFER_SIZE = 65507          # taille utile maximale d'un datagramme IPv4/UDP
MAX_MESSAGES_PER_TICK = 128 # un flot LAN ne doit pas affamer le rendu
UDP_COMPRESS_THRESHOLD = 1100
MAX_DECOMPRESSED_SIZE = BUFFER_SIZE
COMPRESSED_PREFIX = b"Z1"


class UdpPeer:
    """Extrémité UDP non bloquante (hôte si `port` est fourni)."""

    def __init__(self, port=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        if port is not None:
            if sys.platform == "win32":
                # Sous Windows, SO_REUSEADDR laisse un SECOND processus
                # binder le même port UDP : deux hôtes se partageraient
                # alors silencieusement les datagrammes au lieu que le
                # second échoue proprement ("port déjà utilisé").
                self.sock.setsockopt(socket.SOL_SOCKET,
                                     socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", port))

    def send(self, message, addr, compress=False):
        """Envoie un dict JSON, compressé si demandé et utile.

        Le préfixe court garde la lecture rétrocompatible des datagrammes JSON
        historiques. La compression des gros instantanés réduit fortement la
        fragmentation IP, donc la probabilité de perdre tout le datagramme.
        """
        try:
            data = json.dumps(message, separators=(",", ":")).encode()
            if compress and len(data) >= UDP_COMPRESS_THRESHOLD:
                compressed = COMPRESSED_PREFIX + zlib.compress(data, level=3)
                if len(compressed) < len(data):
                    data = compressed
            self.sock.sendto(data, addr)
        except (OSError, TypeError, ValueError, RecursionError):
            pass  # câble débranché, hôte injoignable... le jeu continue

    def receive(self, limit=MAX_MESSAGES_PER_TICK):
        """Draine la socket ; retourne [(message, addr), ...]."""
        messages = []
        for _ in range(max(0, min(int(limit), MAX_MESSAGES_PER_TICK))):
            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
            except BlockingIOError:
                break
            except OSError:
                break
            try:
                if data.startswith(COMPRESSED_PREFIX):
                    inflater = zlib.decompressobj()
                    data = inflater.decompress(
                        data[len(COMPRESSED_PREFIX):],
                        MAX_DECOMPRESSED_SIZE + 1,
                    )
                    if (len(data) > MAX_DECOMPRESSED_SIZE
                            or not inflater.eof
                            or inflater.unused_data):
                        continue
                message = json.loads(data.decode())
                if isinstance(message, dict):
                    messages.append((message, addr))
            except (ValueError, UnicodeDecodeError, RecursionError,
                    zlib.error):
                pass  # datagramme corrompu : ignoré
        return messages

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
