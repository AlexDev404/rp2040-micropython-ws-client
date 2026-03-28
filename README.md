# rp2040-micropython-ws-client

Minimal WebSocket client for the RP2040 + ESP-01 configuration, running MicroPython. Includes a lightweight HTTP client and a WebSocket client that route traffic through the ESP-01 AT-command interface.

## Hardware requirements

- RP2040-based board (e.g. Raspberry Pi Pico)
- ESP-01 (or any ESP8266/ESP32 module loaded with AT firmware) connected on UART0
  - TX: GPIO 0
  - RX: GPIO 1

## Dependencies

- [`esp_at_socket`](https://github.com/georgerobotics/cyw43-driver) - provides `ATDevice` and `register_uwebsocket` for routing sockets through the ESP-AT interface (install separately or copy to the board)

## Project structure

```
rp2040-micropython-ws-client/
├── http/
│   └── __init__.py       # HTTPClient - thin HTTP/1.1 client over ATDevice sockets
├── uwebsockets/
│   ├── client.py         # WebSocket client (connect, send, recv)
│   └── protocol.py       # WebSocket framing protocol
└── examples/
    └── soil_moisture_sensor.py   # Full example: sensor -> WebSocket stream
```

## Configuration

Create an `env.py` file on the board's filesystem with your credentials:

```python
HOST = "192.168.1.100"      # API server host (no scheme, no trailing slash)
WIFI_SSID = "your-ssid"
WIFI_PASS = "your-password"
USERNAME = "your-username"
PASSWORD = "your-password"
API_KEY = "your-api-key"
```

## Usage

### Connecting to Wi-Fi

```python
from esp_at_socket import ATDevice

device = ATDevice(uart_id=0, tx_pin=0, rx_pin=1)
device.initialize()
device.connect_network("your-ssid", "your-password")
print("IP:", device.ip_address)
```

### HTTP requests

```python
from http import HTTPClient as Http

headers, body = Http.request(
    device,
    method="GET",
    url="http://example.com/api/resource",
    headers={"Authorization": "Bearer <token>"},
    data=None
)
print(body)
```

`Http.request` returns a `(headers_str, body_str)` tuple. The raw HTTP response headers are in `headers_str`; check for status codes with `headers_str.find("HTTP/1.1 200")`.

### WebSocket connection

```python
from esp_at_socket import register_uwebsocket
from uwebsockets import client as ws_client

# Call once after Wi-Fi is up so uwebsockets uses the ESP-AT transport
register_uwebsocket(device)

ws = ws_client.connect("ws://example.com/ws", authorization="Bearer <token>")
ws.send('{"hello": "world"}')
msg = ws.recv()
```

## Example: soil moisture sensor

`examples/soil_moisture_sensor.py` demonstrates a complete application:

**Wiring**

| Signal         | GPIO |
|----------------|------|
| Sensor ADC in  | 28   |
| Sensor 3.3 V   | 15   |
| ESP-01 TX      | 0    |
| ESP-01 RX      | 1    |

1. Connects to Wi-Fi via the ESP-01 AT interface.
2. Posts an `ONLINE` status to an HTTP API. If the API key has expired it re-authenticates, persists the new token to `env.py`, and reboots.
3. Opens a WebSocket to a streaming endpoint.
4. Reads a capacitive soil moisture sensor on ADC pin 28 (powered via GPIO 15) once per second, converts the raw 16-bit ADC reading to a 0-100% moisture value, and sends a JSON message over the WebSocket.
5. On any WebSocket send failure it resets the modem, reconnects Wi-Fi, and re-opens the WebSocket before continuing.

**Calibration** - set `wet_reading` and `dry_reading` in the example to the ADC values measured in saturated and completely dry soil for your specific sensor:

```python
wet_reading = 320    # ADC reading in saturated soil
dry_reading = 24500  # ADC reading in completely dry soil
```
