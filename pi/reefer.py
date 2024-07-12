import time
from datetime import datetime
from datetime import timedelta
import bme680
import requests
import subprocess
import vcgencmd
import math
import logging
from logging.handlers import RotatingFileHandler

# Loop interval
interval = 60 # in seconds
interval = timedelta(seconds=interval) # Convert integer into proper time format

# Set up logging
logging.basicConfig(
    handlers=[RotatingFileHandler('reefer.log', maxBytes=4000000, backupCount=3)],
    level=logging.WARNING, # Set logging level
    format='%(asctime)s - %(levelname)s - %(message)s')

# API query definitions
#queryOWN = {'lat':'put your lat here', 'lon':'put your lon here', 'appid':'put your API key here'} # OpenWeatherMap API

# Initialize HTTP(S) request sessions for reuse during API calls
#sessionOWN = requests.Session() # OpenWeatherMap API
sessionSatellite = requests.Session() # Pi Pico W + si7021 sensor API

# Station altitude in meters
sta_alt = 280.0

# Initialize BME680
try:
    sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
except (RuntimeError, IOError):
    sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)
# These oversampling settings can be tweaked to
# change the balance between accuracy and noise in
# the data.
sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)
sensor.set_gas_status(bme680.ENABLE_GAS_MEAS) # turn on heater for gas measurements
logging.info('Initial reading:')
for name in dir(sensor.data):
    value = getattr(sensor.data, name)

    if not name.startswith('_'):
        logging.info('{}: {}'.format(name, value))
sensor.set_gas_heater_temperature(320) # 320 °C
sensor.set_gas_heater_duration(150) # 150 ms
sensor.select_gas_heater_profile(0) # Profile 1 of 10

# Global Celsius to Fahrenheit conversion function
def c_to_f(temp_c):
    return (temp_c * 1.8) + 32.0

# Station pressure to MSL Pressure conversion function
# Formula source: https://gist.github.com/cubapp/23dd4e91814a995b8ff06f406679abcf
def sta_press_to_mslp(sta_press, temp_c):
    mslp = sta_press + ((sta_press * 9.80665 * sta_alt)/(287 * (273 + temp_c + (sta_alt/400))))
    return mslp

# Dewpoint calculation function
def calc_dewpoint(humidity, temp_c):
    a = 17.625
    b = 243.04
    alpha = math.log(humidity/100.0) + ((a * temp_c) / (b + temp_c))
    return (b * alpha) / (a - alpha)

# Outdoor Pi Pico W + Si7021 sensor function
def get_outdoor():
    logging.info("")
    logging.info("Outdoor\n")
    try:
        # Initialize variables so if request fails graphs still populate with NaN
        outdoor_c = outdoor_hum = outdoor_dew = picow_temp_c ='U'

        responseSatellite = sessionSatellite.get('http://192.168.0.5', timeout=10) # Don't use HTTPS
        responseSatellite.raise_for_status() # If error, try to catch it in except clauses below
        # Code below here will only run if the request is successful
        outdoor_c = responseSatellite.json()['temperature']
        outdoor_f = c_to_f(outdoor_c)
        outdoor_hum = responseSatellite.json()['humidity']
        outdoor_dew = calc_dewpoint(outdoor_hum, outdoor_c)
        picow_temp_c = responseSatellite.json()['mcu']
        picow_temp_f = c_to_f(picow_temp_c)
        logging.info(f"Temperature: {outdoor_c} °C | {outdoor_f} °F")
        logging.info(f"Humidity: {outdoor_hum} %")
        logging.info(f"Dewpoint: {outdoor_dew} °C")
        logging.info(f"Pi Pico W: {picow_temp_c} °C | {picow_temp_f} °F")
        # Code above here will only run if the request is successful
    except requests.exceptions.HTTPError as errh:
        logging.error(errh)
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err)
    return outdoor_c, outdoor_hum, outdoor_dew, picow_temp_c

# Indoor BME680 function
def get_indoor():
    logging.info("")
    logging.info("Indoor\n")
    if sensor.get_sensor_data():
        temp_c = sensor.data.temperature - 0.5 # Insert sensor error correction here if needed
        temp_f = c_to_f(temp_c)
        logging.info(f"Temperature: {temp_c} °C | {temp_f} °F")
        hum = sensor.data.humidity
        logging.info(f"Humidity: {hum}%")
        dew = calc_dewpoint(hum, temp_c)
        logging.info(f"Dewpoint: {dew} °C")
        sta_press = sensor.data.pressure
        logging.info(f"Raw Pressure: {sta_press} hPa raw station pressure")
        press = sta_press_to_mslp(sta_press, temp_c) # convert to MSLP
        logging.info(f"Pressure: {press} hPa MSLP") # converted to MSLP
        if sensor.data.heat_stable:
            gas = sensor.data.gas_resistance
            logging.info(f"Gas Resistance: {gas} Ω")
        else:
            gas = 'U'
            logging.warning("No data from gas sensor")
        return temp_c, hum, dew, press, gas
    else:
        temp_c = hum = dew = press = gas = 'U' # Set all variables to NaN if sensor data fails
        logging.error("No sensor data available")
        return temp_c, hum, dew, press, gas

# Pi Zero W Temperature function
def pi_temp():
    temp_c = vcgencmd.measure_temp()
    temp_f = c_to_f(temp_c)
    logging.info(f"Pi Zero W: {temp_c:.2f} °C | {temp_f:.2f} °F")
    return temp_c, temp_f

# Update RRD databases function
def update_rrd(outdoor_c, outdoor_hum, outdoor_dew, picow_temp_c, indoor_c, indoor_hum, indoor_dew, indoor_press, indoor_gas, pi_temp_c):
    logging.info("")
    logging.info("Updating RRD databases...\n")

    result = subprocess.run(["rrdtool", "updatev", "temperatures.rrd",
     f"N:{outdoor_c}:{indoor_c}:{pi_temp_c}:{picow_temp_c}:{outdoor_dew}:{indoor_dew}"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run(["rrdtool", "updatev", "humidities.rrd",
     f"N:{outdoor_hum}:{indoor_hum}"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run(["rrdtool", "updatev", "pressures.rrd",
     f"N:{indoor_press}"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run(["rrdtool", "updatev", "gas.rrd",
     f"N:{indoor_gas}"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    logging.info("Done")

# RRDtool graphing function
def create_graphs():
    logging.info("Creating graphs...")

    # Reduce duplicate lines of code
    common_args = [
     "--end", "now", "--start", "end-1780m", "--step", "120",
     "--width", "890",
     "--font", "DEFAULT:10:",
     "--font", "AXIS:8:",
     "--x-grid","MINUTE:30:HOUR:1:HOUR:2:0:%H:00",
     "--alt-autoscale",
     "--border", "0",
     "--slope-mode",
     "-c", "BACK#333333",
     "-c", "CANVAS#18191A",
     "-c", "FONT#DDDDDD",
     "-c", "GRID#DDDDDD1A",
     "-c", "MGRID#DDDDDD33",
     "-c", "FRAME#18191A",
     "-c", "ARROW#333333",
     "--disable-rrdtool-tag"
    ]

    result = subprocess.run([
     "rrdtool", "graph",
     "/mnt/tmp/temperatures.png",
     "--title", "Temperature",
     "--vertical-label", "Celsius",
     "--right-axis-label", "Fahrenheit",
     "--right-axis", "1.8:32",
     "--height", "380",
     "DEF:outdoor=temperatures.rrd:outdoor:LAST",
     "DEF:indoor=temperatures.rrd:indoor:LAST",
     "DEF:outdoor_dew=temperatures.rrd:outdoor_dew:LAST",
     "DEF:indoor_dew=temperatures.rrd:indoor_dew:LAST",
     "CDEF:outdoor-f=outdoor,1.8,*,32,+",
     "CDEF:indoor-f=indoor,1.8,*,32,+",
     "CDEF:outdoor_dew-f=outdoor_dew,1.8,*,32,+",
     "CDEF:indoor_dew-f=indoor_dew,1.8,*,32,+",
     "VDEF:outdoorMax=outdoor,MAXIMUM",
     "VDEF:outdoorMin=outdoor,MINIMUM",
     "VDEF:indoorMax=indoor,MAXIMUM",
     "VDEF:indoorMin=indoor,MINIMUM",
     "VDEF:outdoor_dewMax=outdoor_dew,MAXIMUM",
     "VDEF:outdoor_dewMin=outdoor_dew,MINIMUM",
     "VDEF:indoor_dewMax=indoor_dew,MAXIMUM",
     "VDEF:indoor_dewMin=indoor_dew,MINIMUM",
     "LINE1:outdoor#ff0000:Outdoor         ",
     "GPRINT:outdoor:LAST:Cur\: %.1lf °C",
     "GPRINT:outdoor-f:LAST:%.1lf °F",
     "GPRINT:outdoorMax:Max\: %.1lf °C",
     "GPRINT:outdoorMin:Min\: %.1lf °C\l",
     "LINE1:outdoor_dew#ff00ff:Outdoor Dewpoint",
     "GPRINT:outdoor_dew:LAST:Cur\: %.1lf °C",
     "GPRINT:outdoor_dew-f:LAST:%.1lf °F",
     "GPRINT:outdoor_dewMax:Max\: %.1lf °C",
     "GPRINT:outdoor_dewMin:Min\: %.1lf °C\l",
     "LINE1:indoor#0000ff:Indoor          ",
     "GPRINT:indoor:LAST:Cur\: %.1lf °C",
     "GPRINT:indoor-f:LAST:%.1lf °F",
     "GPRINT:indoorMax:Max\: %.1lf °C",
     "GPRINT:indoorMin:Min\: %.1lf °C\l",
     "LINE1:indoor_dew#00ffff:Indoor Dewpoint ",
     "GPRINT:indoor_dew:LAST:Cur\: %.1lf °C",
     "GPRINT:indoor_dew-f:LAST:%.1lf °F",
     "GPRINT:indoor_dewMax:Max\: %.1lf °C",
     "GPRINT:indoor_dewMin:Min\: %.1lf °C\l",
     ] + common_args, capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run([
     "rrdtool", "graph",
     "/mnt/tmp/humidities.png",
     "--title", "Humidity",
     "--vertical-label", "Relative (%)",
     "--right-axis-label", "Relative (%)",
     "--right-axis", "1:0",
     "--height", "300",
     "DEF:outdoor=humidities.rrd:outdoor:LAST",
     "DEF:indoor=humidities.rrd:indoor:LAST",
     "VDEF:outdoorMax=outdoor,MAXIMUM",
     "VDEF:outdoorMin=outdoor,MINIMUM",
     "VDEF:indoorMax=indoor,MAXIMUM",
     "VDEF:indoorMin=indoor,MINIMUM",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:Cur\: %.1lf%%",
     "GPRINT:outdoorMax:Max\: %.1lf%%",
     "GPRINT:outdoorMin:Min\: %.1lf%%",
     "COMMENT:\l",
     "LINE1:indoor#0000ff:Indoor ",
     "GPRINT:indoor:LAST:Cur\: %.1lf%%",
     "GPRINT:indoorMax:Max\: %.1lf%%",
     "GPRINT:indoorMin:Min\: %.1lf%%",
     "COMMENT:\l",
     ] + common_args, capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run([
     "rrdtool", "graph",
     "/mnt/tmp/pressures.png",
     "--title", "Barometric Pressure (MSL)",
     "--vertical-label", "hPa",
     "--right-axis-label", "hPa",
     "--right-axis", "1:0", "--right-axis-format", "%4.0lf",
     "--height", "300",
     "--lower-limit", "1002", "--upper-limit", "1030",
     "--y-grid", "1:2",
     "--units-exponent", "0",
     "DEF:indoor=pressures.rrd:indoor:LAST",
     "VDEF:indoorMax=indoor,MAXIMUM",
     "VDEF:indoorMin=indoor,MINIMUM",
     "LINE1:indoor#00ff00:Local",
     "GPRINT:indoor:LAST:Cur\: %.2lf hPa",
     "GPRINT:indoorMax:Max\: %.2lf hPa",
     "GPRINT:indoorMin:Min\: %.2lf hPa\l",
     ] + common_args, capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run([
     "rrdtool", "graph",
     "/mnt/tmp/gas.png",
     "--title", "Gas Resistance",
     "--vertical-label", "Ω",
     "--right-axis-label", "Ω",
     "--right-axis", "1:0",
     "--height", "300",
     "DEF:indoor=gas.rrd:indoor:LAST",
     "VDEF:indoorMax=indoor,MAXIMUM",
     "VDEF:indoorMin=indoor,MINIMUM",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST:Cur\: %.1lf%s Ω",
     "GPRINT:indoorMax:Max\: %.1lf%s Ω",
     "GPRINT:indoorMin:Min\: %.1lf%s Ω\l",
     ] + common_args, capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run([
     "rrdtool", "graph",
     "/mnt/tmp/pi.png",
     "--title", "Pi Temperatures",
     "--vertical-label", "Celsius",
     "--right-axis-label", "Fahrenheit",
     "--right-axis", "1.8:32",
     "--height", "120",
     "DEF:pi=temperatures.rrd:pi:LAST",
     "DEF:picow=temperatures.rrd:picow:LAST",
     "CDEF:picow-f=picow,1.8,*,32,+",
     "CDEF:pi-f=pi,1.8,*,32,+",
     "LINE1:picow#ff0000:Pico W MCU",
     "GPRINT:picow:LAST:Cur\: %.1lf °C",
     "GPRINT:picow-f:LAST:%.1lf °F\l",
     "LINE1:pi#0000ff:Zero W CPU",
     "GPRINT:pi:LAST:Cur\: %.1lf °C",
     "GPRINT:pi-f:LAST:%.1lf °F\l",
     ] + common_args, capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    logging.info("Done")

# Main Loop
while True:
    started = datetime.now() # Start timing the operation

    logging.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~") # Start logging cycle with a row of tildes to differentiate
    outdoor_c, outdoor_hum, outdoor_dew, picow_temp_c = get_outdoor()
    indoor_c, indoor_hum, indoor_dew, indoor_press, indoor_gas = get_indoor()
    #tank_c = 'U' # Tank sensor is broken so set to NaN
    pi_temp_c, pi_temp_f = pi_temp()
    update_rrd(outdoor_c, outdoor_hum, outdoor_dew, picow_temp_c, indoor_c, indoor_hum, indoor_dew, indoor_press, indoor_gas, pi_temp_c)
    create_graphs()

    ended = datetime.now() # Stop timing the operation
    # Compute the amount of time it took to run the loop above
    # then sleep for the remaining time left
    # if it is less than the configured loop interval
    if started and ended and ended - started < interval:
        logging.info("Sleeping...\n")
        time.sleep((interval - (ended - started)).seconds)
