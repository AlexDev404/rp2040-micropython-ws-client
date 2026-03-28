"""
Websockets client for micropython

Based very heavily off
https://github.com/aaugustin/websockets/blob/master/websockets/client.py
"""
try:
    import usocket as socket
except ImportError:
    socket = None

import ubinascii as binascii
import urandom as random
import select
import _thread

from .protocol import Websocket, urlparse

try:
    import ussl
except ImportError:
    ussl = None

_SOCKET_FACTORY = None


def set_socket_factory(factory):
    """Override the socket creation logic (e.g. to use ESP-AT)."""
    global _SOCKET_FACTORY
    _SOCKET_FACTORY = factory


class WebsocketClient(Websocket):
    is_client = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Start a separate thread to process incoming WebSocket control messages
        _thread.start_new_thread(self._process_ws_ctrl_msg, ())

    def _process_ws_ctrl_msg(self):
        """Process incoming WebSocket control messages (call in a thread)."""
        while True:
            try:
                r, _, _ = select.select([self.sock], [], [], 0)
                if self.sock in r:
                    _ = self.recv()  # Handle control messages accordingly
            except Exception as e:
                print("WebSocket error:", e)
                break


def connect(uri, socket_factory=None, authorization=""):
    """
    Connect a websocket.
    """

    uri = urlparse(uri)
    assert uri

    # print("open connection " + uri.hostname + ":" + str(uri.port))

    factory = socket_factory or _SOCKET_FACTORY

    if factory:
        sock = factory(uri)
    else:
        if socket is None:
            raise RuntimeError('no socket implementation available')
        sock = socket.socket()
        addr = socket.getaddrinfo(uri.hostname, uri.port)
        sock.connect(addr[0][4])
        if uri.protocol == 'wss':
            if ussl is None:
                raise RuntimeError('ussl module not available for wss connection')
            sock = ussl.wrap_socket(sock, server_hostname=uri.hostname)

    def send_header(header, *args):
        # print(str(header) + str(args))
        sock.write(header % args + '\r\n')

    # Sec-WebSocket-Key is 16 bytes of random base64 encoded
    key = binascii.b2a_base64(bytes(random.getrandbits(8)
                                    for _ in range(16)))[:-1]

    send_header(b'GET %s HTTP/1.1', uri.path or '/')
    send_header(b'Host: %s:%s', uri.hostname, uri.port)
    send_header(b'Connection: Upgrade')
    send_header(b'Upgrade: websocket')
    send_header(b'Sec-WebSocket-Key: %s', key)
    send_header(b'Sec-WebSocket-Version: 13')
    send_header(b'Origin: http://{hostname}:{port}'.format(
        hostname=uri.hostname,
        port=uri.port)
    )
    if authorization != '':
        send_header(b'Authorization: %s', authorization)
    send_header(b'')

    header = sock.readline()[:-2]
    assert header.startswith(b'HTTP/1.1 101 '), header

    # We don't (currently) need these headers
    # FIXME: should we check the return key?
    while header:
        # print(str(header))
        header = sock.readline()[:-2]

    return WebsocketClient(sock)
