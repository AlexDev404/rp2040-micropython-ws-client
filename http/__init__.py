from esp_at_socket import ATDevice


class HTTPClient:
    @staticmethod
    def request(self, device=ATDevice(uart_id=0, tx_pin=0, rx_pin=1), method="GET", url="", headers=None, data=None):
        """Sends an HTTP POST request using the ATDevice."""
        url_ssl = url.startswith("https://")
        sock = device.open_socket(ssl=url_ssl)
        host = url.split("/")[2]
        sock.connect((host, 443 if url_ssl else 80))
        path = "/" + "/".join(url.split("/")[3:])
        request_headers = f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n"
        if headers:
            for key, value in headers.items():
                request_headers += f"{key}: {value}\r\n"
        request_headers += "Connection: close\r\n"
        if data:
            request_headers += f"Content-Length: {len(data)}\r\n"
        request_headers += "\r\n"
        request = request_headers
        if data:
            request += data
        sock.write(request)
        response = bytearray()
        while True:
            chunk = sock.read(256)
            if not chunk:
                break
            response.extend(chunk)
        sock.close()
        raw_response = response.decode("utf-8", "ignore")
        # Split headers and body
        header_body_split = raw_response.split("\r\n\r\n", 1)
        if len(header_body_split) > 1:
            body = header_body_split[1]
        else:
            body = ""
        headers = header_body_split[0]
        return headers, body
