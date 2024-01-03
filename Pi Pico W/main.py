from machine import Pin, I2C
from micropython_si7021 import si7021
from microdot import Microdot

# Initialize si7021 sensor
i2c = I2C(0, sda=Pin(0), scl=Pin(1))  # i2c0 pins for Pico
si = si7021.SI7021(i2c)

app = Microdot()

@app.get('/')
async def index(request):
    return {'temperature': si.temperature,
            'humidity': si.humidity}

app.run(port=80)
