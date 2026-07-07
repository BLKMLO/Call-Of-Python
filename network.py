"""Couche réseau LAN — bibliothèque standard uniquement.

Des datagrammes UDP transportant du JSON compact : suffisant pour un
réseau local (latence négligeable, pertes rares, et le protocole de
`coop.py` tolère la perte d'instantanés puisque chacun écrase le
précédent). Les sockets sont non bloquantes et lues dans la boucle de
jeu : aucun thread.
"""

import json
import socket

DEFAULT_PORT = 5577
BUFFER_SIZE = 65536


class UdpPeer:
    """Extrémité UDP non bloquante (hôte si `port` est fourni)."""

    def __init__(self, port=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        if port is not None:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", port))

    def send(self, message, addr):
        """Envoie un dict JSON à `addr` ; silencieux en cas d'échec réseau."""
        try:
            data = json.dumps(message, separators=(",", ":")).encode()
            self.sock.sendto(data, addr)
        except OSError:
            pass  # câble débranché, hôte injoignable... le jeu continue

    def receive(self):
        """Draine la socket ; retourne [(message, addr), ...]."""
        messages = []
        while True:
            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
            except BlockingIOError:
                break
            except OSError:
                break
            try:
                messages.append((json.loads(data.decode()), addr))
            except (ValueError, UnicodeDecodeError):
                pass  # datagramme corrompu : ignoré
        return messages

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
