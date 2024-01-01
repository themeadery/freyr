import webrepl
import network
import secrets
from utime import sleep
from machine import Pin

led = machine.Pin("LED", machine.Pin.OUT)

wlan = network.WLAN(network.STA_IF)
wlan.active(True) # power up the WiFi chip
sleep(3) # wait X seconds for the chip to power up and initialize
wlan.connect(secrets.SSID, secrets.PASSWORD)
sleep(6) # wait for connection handshake to finish
if wlan.isconnected():
    print("wlan connected")
    led.on()
else:
    print("wlan connection error")

webrepl.start()
