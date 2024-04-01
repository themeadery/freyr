import time
from machine import Pin, I2C, ADC
from SI7021 import SI7021
from microdot import Microdot
import gc

debug = False # set to True to turn on debugging info below

# Initialize si7021 sensor
i2c = I2C(0, sda=Pin(0), scl=Pin(1))  # i2c0 pins for Pico
si = SI7021(i2c)

# Initialize internal mcu temperature sensor
sensor = ADC(4) # ADC Pin 4

app = Microdot()

def read_mcu_temp():
    adc_value = sensor.read_u16()
    volt = (3.3/65535) * adc_value
    mcu_temp = 27 - (volt - 0.706)/0.001721
    return (mcu_temp)

@app.before_request
async def start_timer(request):
    request.g.start_time = time.ticks_ms()
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

@app.after_request
async def end_timer(request, response):
    duration = time.ticks_diff(time.ticks_ms(), request.g.start_time)
    if debug:
        print(f'Request took {duration} ms')
        print(f'gc.mem_alloc(): {gc.mem_alloc()}')
        print(f'gc.mem_free(): {gc.mem_free()}')
        print('Taking out the garbage...')
    gc.collect()
    if debug:
        print(f'gc.mem_alloc(): {gc.mem_alloc()}')
        print(f'gc.mem_free(): {gc.mem_free()}')

@app.get('/')
async def index(request):
    humidity = si.humidity()
    temperature = si.temperature(new=False)
    mcu_temp = read_mcu_temp()
    if debug:
        print(f'Temperature: {temperature} °C')
        print(f'Humidity: {humidity} %')
        print(f'MCU Temperature: {mcu_temp} °C')
    return {'temperature': temperature,
            'humidity': humidity, 'mcu': mcu_temp}

app.run(port=80, debug=True)
