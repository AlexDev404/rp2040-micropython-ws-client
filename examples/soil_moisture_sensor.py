"""
Soil Moisture Sensor Example
=============================
Reads an analog soil moisture sensor on GPIO 28, streams readings over a
WebSocket, and uses an HTTP API to report device status.

Hardware:
  - RP2040-based board
  - ESP-01 (or compatible) AT-command Wi-Fi module on UART0 (TX=0, RX=1)
  - Capacitive or resistive soil moisture sensor on ADC pin 28
  - 3.3 V rail controlled via GPIO 15 (used to power the sensor)

Configuration:
  Create env.py in the root of the filesystem with the following variables:
    HOST, WIFI_SSID, WIFI_PASS, USERNAME, PASSWORD, API_KEY
"""

import time
import machine
import ujson
from http import HTTPClient as Http

import env
from machine import Pin as PIN, ADC
from esp_at_socket import ATDevice, register_uwebsocket
from uwebsockets import client as ws_client

WIFI_SSID = env.WIFI_SSID
WIFI_PASSWORD = env.WIFI_PASS


def connect_wifi(device):
    if not device.initialize():
        print("Failed to initialise AT device")
        return False

    if not device.connect_network(WIFI_SSID, WIFI_PASSWORD):
        print("Failed to connect to WiFi")
        return False

    print("Connected to WiFi. IP:", device.ip_address)
    return True


def read_sensor(pin_number):
    """Reads an analog value from the specified pin."""
    adc = ADC(PIN(pin_number, PIN.IN))
    value = adc.read_u16()
    return value


def main():
    device = ATDevice(uart_id=0, tx_pin=0, rx_pin=1)
    if not connect_wifi(device):
        print("[SYS-CRASH]: Hard reset.")
        time.sleep(2)
        machine.reset()

    ret = device.send_command("AT+GMR")
    print("Firmware version:", ret[0])

    # Post initial online status
    try:
        post_status(device, status="ONLINE", status_message="Device is ready.")
    except Exception as e:
        print("Failed to post initial online status:", e)
        # Re-authenticate and persist the new token
        login_data = {
            "username": env.USERNAME,
            "password": env.PASSWORD
        }
        headers, result_data = Http.request(
            device,
            method="POST",
            url=f"http://{env.HOST}/v1/auth/login",
            headers=None,
            data=str(login_data).replace("'", '"')
        )
        print("Login response: ", result_data)
        response_object = ujson.loads(str(result_data))
        env.API_KEY = response_object.get("token", env.API_KEY)

        with open("env.py", "w") as f:
            f.write(f'HOST = "{env.HOST}"\n')
            f.write(f'WIFI_SSID = "{env.WIFI_SSID}"\n')
            f.write(f'WIFI_PASS = "{env.WIFI_PASS}"\n')
            f.write(f'USERNAME = "{env.USERNAME}"\n')
            f.write(f'PASSWORD = "{env.PASSWORD}"\n')
            f.write(f'API_KEY = "{env.API_KEY}"\n')
        print("[SYS-CRASH]: Hard reset.")
        time.sleep(2)
        machine.reset()

    # Register the socket factory so uwebsockets uses the ESP-AT transport
    register_uwebsocket(device)
    auth = f"Bearer {env.API_KEY}"
    ws = None
    try:
        ws = ws_client.connect(f"ws://{env.HOST}/v1/faucet", authorization=auth)
    except Exception as e:
        try:
            post_status(device, status_message=str(e))
        except Exception as f:
            print("Failed to post error status:", f)
        print("Failed to connect WebSocket:", e)
        print("[SYS-CRASH]: Hard reset.")
        time.sleep(2)
        machine.reset()

    sensor_pin = 28
    _3v_pin = PIN(15, PIN.OUT)
    _3v_pin.value(1)  # Enable power to the sensor

    # Calibration values - adjust to match your sensor in your soil type
    wet_reading = 320    # ADC reading in saturated soil
    dry_reading = 24500  # ADC reading in completely dry soil

    while True:
        adc_reading = read_sensor(sensor_pin)
        voltage = adc_reading * 3.3 / 65535
        percent = ((wet_reading - adc_reading) / (wet_reading - dry_reading)) * 100
        percent = max(0, min(100, int(percent)))
        print(f"ADC: {adc_reading:5d}, Voltage: {voltage:.3f}V, Moisture: {percent:.1f}%")
        time.sleep(1)

        data = {
            "type": "device_update",
            "data": {
                "device_id": 1,
                "moisture_content": percent,
                "user_id": 3
            }
        }
        try:
            ws.send(str(data).replace("'", '"'))
        except Exception as e:
            try:
                post_status(device, status_message=str(e))
            except Exception as f:
                print("Failed to post error status:", f)
            print("Error sending data over WebSocket:", e)
            print("Attempting to reconnect WebSocket...")
            print("Restarting modem...")
            device.reset_modem()
            time.sleep(5)
            if not connect_wifi(device):
                print("Failed to reconnect Wi-Fi after modem reset")
                print("[SYS-CRASH]: Hard reset.")
                time.sleep(2)
                machine.reset()
            try:
                ws = ws_client.connect(f"ws://{env.HOST}:4000/v1/faucet", authorization=auth)
            except Exception as e:
                try:
                    post_status(device, status_message=str(e))
                except Exception as f:
                    print("Failed to post error status:", f)
                print("Failed to reconnect WebSocket:", e)
                print("[SYS-CRASH]: Hard reset.")
                time.sleep(2)
                machine.reset()


def post_status(device, status="ERROR", status_message=""):
    post_data = {
        "status": status,
        "status_details": status_message
    }
    headers, res = Http.request(
        device,
        method="PUT",
        url=f"http://{env.HOST}/v1/nodes/1",
        headers={
            "Authorization": f"Bearer {env.API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        data=str(post_data).replace("'", '"')
    )
    print("HTTP PUT response:", res)
    if headers.find("HTTP/1.1 401") != -1:
        raise RuntimeError("Unauthorized: Invalid API Key")
    print("Posted status:", status)


if __name__ == "__main__":
    main()
