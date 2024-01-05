import webrepl
import network
import secrets
from utime import sleep
import machine

led = machine.Pin("LED", machine.Pin.OUT)

wlan = network.WLAN(network.STA_IF)
wlan.active(True) # power up the WiFi chip
sleep(2) # wait X seconds for the chip to power up and initialize

while not wlan.isconnected():
    print("Trying to connect to WLAN...")
    wlan.connect(secrets.SSID, secrets.PASSWORD)
    led.on()
    sleep(0.1)
    led.off()
    sleep(1.4)

print("WLAN connected")
led.on()

webrepl.start()
