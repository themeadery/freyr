import webrepl
import network
import secrets
from utime import sleep

wlan = network.WLAN(network.STA_IF)
wlan.active(True) # power up the WiFi chip
sleep(3) # wait X seconds for the chip to power up and initialize
wlan.connect(secrets.SSID, secrets.PASSWORD)
sleep(6)

webrepl.start()
