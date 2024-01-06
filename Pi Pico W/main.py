import time
from machine import Pin, I2C
from SI7021 import SI7021
from microdot import Microdot
import gc

# Initialize si7021 sensor
i2c = I2C(0, sda=Pin(0), scl=Pin(1))  # i2c0 pins for Pico
si = SI7021(i2c)

app = Microdot()

@app.before_request
async def start_timer(request):
    request.g.start_time = time.ticks_ms()
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

@app.after_request
async def end_timer(request, response):
    duration = time.ticks_diff(time.ticks_ms(), request.g.start_time)
    print(f'Request took {duration} ms')
    print(f'gc.mem_alloc(): {gc.mem_alloc()}')
    print(f'gc.mem_free(): {gc.mem_free()}')
    print('Taking out the garbage...')
    gc.collect()
    print(f'gc.mem_alloc(): {gc.mem_alloc()}')
    print(f'gc.mem_free(): {gc.mem_free()}')

@app.get('/')
async def index(request):
    humidity = si.humidity()
    temperature = si.temperature(new=False)
    print(f'Temperature: {temperature} °C')
    print(f'Humidity: {humidity} %')
    return {'temperature': temperature,
            'humidity': humidity}

app.run(port=80, debug=True)
