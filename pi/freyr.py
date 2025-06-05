import time
from datetime import datetime, timedelta
import config
import bme680
import requests
import rrdtool
import vcgencmd
import math
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import signal
import sys

def init():
    global connection, cursor
    global sensor

    # Set up logging
    logging.basicConfig(
        handlers=[RotatingFileHandler(config.LOG_PATH + config.LOG_FILE, maxBytes=4000000, backupCount=3)],
        level=logging.DEBUG, # Set logging level. logging.WARNING = less info , logging.DEBUG = more info
        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.warning("Starting freyr") # Throw something in the log on start just so I know everything is working

    # Connect to SQLite db
    try:
        logging.info(f"Connecting to SQLite database")
        connection = sqlite3.connect(config.DATABASE_PATH + config.DATABASE)
        cursor = connection.cursor()
    except Exception as e:
        logging.error(f"Couldn't open SQLite database: {e}")

    # Initialize BME680
    try:
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
    except (RuntimeError, IOError):
        sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)
    # These oversampling settings can be tweaked to
    # change the balance between accuracy and noise in the data.
    sensor.set_humidity_oversample(bme680.OS_2X)
    sensor.set_pressure_oversample(bme680.OS_4X)
    sensor.set_temperature_oversample(bme680.OS_8X)
    sensor.set_filter(bme680.FILTER_SIZE_3)
    sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
    sensor.set_gas_heater_temperature(320) # 320 °C
    sensor.set_gas_heater_duration(150) # 150 ms
    sensor.select_gas_heater_profile(0) # Profile 1 of 10

    # BME680 must be read twice in order to fire up the heater and become heat_stable
    warmup_time = 5  # in sec
    for _ in range(2): # Loop iterates 2 times using a throwaway variable "_"
        logging.info(f"Warming up BME680 sensor for {warmup_time} seconds...")
        sensor.get_sensor_data() # call function from bme680 module, but don't return anything, this fires up heater
        time.sleep(warmup_time)

    offset = -0.4 # Temperature offset in deg C. Slight compensation for heating from components on PCB, wires to sensor, etc.
    sensor.set_temp_offset(offset)
    # Done initializing BME680

# Global Celsius to Fahrenheit conversion function
def c_to_f(temp_c):
    return (temp_c * 1.8) + 32.0

# Station pressure to MSL Pressure conversion function
# Formula source: https://gist.github.com/cubapp/23dd4e91814a995b8ff06f406679abcf
def sta_press_to_mslp(sta_press, temp_c):
    mslp = sta_press + ((sta_press * 9.80665 * config.STA_ALT)/(287 * (273 + temp_c + (config.STA_ALT/400))))
    return mslp

# Dewpoint calculation function
# Formula source: https://gist.github.com/sourceperl/45587ea99ff123745428
def calc_dewpoint(humidity, temp_c):
    a = 17.625
    b = 243.04
    alpha = math.log(humidity/100.0) + ((a * temp_c) / (b + temp_c))
    return (b * alpha) / (a - alpha)

# Outdoor Pi Pico W + Si7021 sensor function
def get_outdoor():
    logging.info("Outdoor sensor data:")
    try:
        offset = 1.0 # Sensor correction in degrees C
        # Initialize variables so if request fails graphs still populate with NaN
        outdoor_c = outdoor_hum = outdoor_dew = picow_temp_c = 'U'
        responseSatellite = requests.get(config.SATELLITE, timeout=5)
        responseSatellite.raise_for_status() # If error, try to catch it in except clauses below
        # Code below here will only run if the request is successful
        outdoor_c = responseSatellite.json()['temperature'] + offset
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

def get_OpenUV_Index():
    logging.info("Fetching data from OpenUV:")
    uv = 'U' # Set to rrdtool's definition of NaN if request fails
    urlOpenUV = "https://api.openuv.io/api/v1/uv"
    headersOpenUV = {"x-access-token": config.OPENUVKEY} # OpenUV.io API key
    paramsOpenUV = {
        "lat": config.LAT,
        "lng": config.LON,
        "alt": config.STA_ALT,
        "dt": ""  # If you want to specify a datetime, you can put it here
    }
    sessionOpenUV = requests.Session() # Initialize session for reuse during API calls
    try:
        responseOpenUV = sessionOpenUV.get(urlOpenUV, headers=headersOpenUV, params=paramsOpenUV, timeout=5)
        responseOpenUV.raise_for_status() # If error, try to catch it in except clauses below
        # Code below here will only run if the request is successful
        uv = responseOpenUV.json()['result']['uv']
        logging.info(f"UV Index: {uv}")
    except requests.exceptions.HTTPError as errh: # If the error is an HTTP error code, then:
        logging.error(errh) # log error code, example " - ERROR - 403 Client Error: Forbidden for url:"
        logging.error(f"Full Response: {responseOpenUV.json()}") # Show full JSON response, Expected key should be 'error':
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err)
    return uv

def get_OWM():
    logging.info("Fetching data from OpenWeatherMap:")
    #wind = windGust = 'U' # Set to rrdtool's definition of NaN if request fails
    #urlOWM = "https://api.openweathermap.org/data/3.0/onecall"
    urlOWM = "https://api.openweathermap.org/data/2.5/weather"
    """paramsOWM = {
        "lat": config.LAT,
        "lon": config.LON,
        "exclude": "minutely,hourly,daily,alerts",
        "units": "imperial",
        "appid": config.OWMKEY
    }"""
    paramsOWM = {
        "lat": config.LAT,
        "lon": config.LON,
        "appid": config.OWMKEY,
        "units": "imperial"
    }
    try:
        responseOWM = requests.get(urlOWM, params=paramsOWM, timeout=5)
        responseOWM.raise_for_status() # If error, try to catch it in except clauses below
        # Code below here will only run if the request is successful
        #current_data = responseOWM.json().get('current', {}) # take the 'current' key values and throw them in 'current_data'
        w = responseOWM.json().get('wind', {}) # take the 'wind' key values and throw them in 'w'
        #wind = current_data.get('wind_speed', 'U') # if 'wind_speed' key does not exist, fallback to 'U' which is rrdtool's def of NaN
        wind = w.get('speed', 'U') # if 'wind_speed' key does not exist, fallback to 'U' which is rrdtool's def of NaN
        #windGust = current_data.get('wind_gust', 'U') # if 'wind_gust' key does not exist, fallback to 'U' which is rrdtool's def of NaN
        windGust = w.get('gust', 'U') # if 'wind_gust' key does not exist, fallback to 'U' which is rrdtool's def of NaN
        logging.info(f"Wind: {wind} mph") # this kinda assume the key exists
        if windGust != 'U':
            logging.info(f"Wind Gust: {windGust} mph")
        else:
            logging.warning("Wind Gust data not available.") # catch/log the error I think was happening
    except requests.exceptions.HTTPError as errh: # If the error is an HTTP error code, then:
        logging.error(errh) # log error code, example "- ERROR - 429 Client Error: Too Many Requests for url:"
        logging.error(f"Full Response: {responseOWM.json()}") # Show full JSON response, Expected key should be "cod" "message" and "parameters"
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err)
    return wind, windGust

def post_WU(outdoor_c, outdoor_dew, outdoor_hum, indoor_press):
    logging.info("Posting data to Weather Underground:")
    outdoor_f = c_to_f(outdoor_c)
    outdoor_dew_f = c_to_f(outdoor_dew)
    pressure_in = indoor_press * 0.02953 # Convert hPa to inHg
    urlWU = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
    paramsWU = {
        "ID": config.WU_ID,
        "PASSWORD": config.WU_KEY,
        "dateutc": "now",  # or use datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') if needed
        "humidity": outdoor_hum,
        "dewptf": outdoor_dew_f,
        "tempf": outdoor_f,
        "baromin": pressure_in,
        "action": "updateraw"
    }
    try:
        responseWU = requests.get(urlWU, params=paramsWU, timeout=5) # WU actually uses GET, not POST
        responseWU.raise_for_status() # If error, try to catch it in except clauses below
        logging.debug(f"Weather Underground response RAW: {responseWU}")
        logging.info(f"Weather Underground status code: {responseWU.status_code}")
        logging.info(f"Weather Underground response text: {responseWU.text}")
    except requests.exceptions.HTTPError as errh:
        logging.error(errh)
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err)

# Indoor BME680 function
def get_indoor():
    logging.info("Indoor sensor data:")
    if sensor.get_sensor_data() and sensor.data.heat_stable:
        temp_c = sensor.data.temperature #- 0.5 # Insert sensor error correction here if needed. BAD IDEA, use internal function, changes all values below.
        temp_f = c_to_f(temp_c)
        logging.info(f"Temperature: {temp_c} °C | {temp_f} °F")
        hum = sensor.data.humidity
        logging.info(f"Humidity: {hum}%")
        dew = calc_dewpoint(hum, temp_c)
        logging.info(f"Dewpoint: {dew} °C")
        sta_press = sensor.data.pressure # This data is incorrect (low) if sensor is not heat_stable or only on first iteration
        logging.info(f"Raw Pressure: {sta_press} hPa raw station pressure")
        press = sta_press_to_mslp(sta_press, temp_c) # convert to MSLP
        logging.info(f"Pressure: {press} hPa MSLP") # converted to MSLP
        gas = sensor.data.gas_resistance
        logging.info(f"Gas Resistance: {gas} Ω")
        return temp_c, hum, dew, press, gas
    else:
        temp_c = hum = dew = press = gas = 'U' # Set all variables to NaN if sensor data fails
        logging.error("Sensor is not ready or not heat_stable. No sensor data available. All vars set to 'U'")
        return temp_c, hum, dew, press, gas

# Pi Zero W Temperature function
def pi_temp():
    temp_c = 'U'
    try:
        temp_c = vcgencmd.measure_temp()
        temp_f = c_to_f(temp_c)
        logging.info(f"Pi Zero W: {temp_c:.2f} °C | {temp_f:.2f} °F")
    except Exception as e:
        logging.error(f"Failed to read Pi temperature: {e}")
    return temp_c

def update_rrd(rrd_filename, alignedEpoch, values_string):
    logging.info(f"Updating {rrd_filename}...")
    try:
        last_update = rrdtool.last(config.RRD_PATH + rrd_filename)
        if alignedEpoch > last_update:
            result = rrdtool.updatev(config.RRD_PATH + rrd_filename, values_string)
            logging.debug(f"Full result from rrdtool.updatev: {result}")
            logging.info(f"Success! Updated {rrd_filename} with values {values_string}") #Show what went into the RRD
        else:
            logging.warning(f"Skipped update for {rrd_filename}: timestamp {alignedEpoch} <= last update {last_update}")
            return
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error updating {rrd_filename}: {err}")
        logging.error(f"Fail! Result: {result}")

def create_graphs():
    logging.info("Creating graphs...")

    # Reduce duplicate lines of code
    common_args = [
        "--end", "now", "--start", "end-2880m", "--step", "120",
        "--width", "1440",
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

    try:
        result = rrdtool.graph("/mnt/tmp/temperatures.png",
            common_args,
            "--title", "Temperature",
            "--vertical-label", "Celsius",
            "--right-axis-label", "Fahrenheit",
            "--right-axis", "1.8:32",
            "--height", "380",
            "DEF:outdoor=./rrd/temperatures.rrd:outdoor:LAST",
            "DEF:indoor=./rrd/temperatures.rrd:indoor:LAST",
            "DEF:outdoor_dew=./rrd/temperatures.rrd:outdoor_dew:LAST",
            "DEF:indoor_dew=./rrd/temperatures.rrd:indoor_dew:LAST",
            "DEF:outdoorMax=./rrd/temperatures.rrd:outdoor:MAX",
            "DEF:indoorMax=./rrd/temperatures.rrd:indoor:MAX",
            "DEF:outdoor_dewMax=./rrd/temperatures.rrd:outdoor_dew:MAX",
            "DEF:indoor_dewMax=./rrd/temperatures.rrd:indoor_dew:MAX",
            "DEF:outdoorMin=./rrd/temperatures.rrd:outdoor:MIN",
            "DEF:indoorMin=./rrd/temperatures.rrd:indoor:MIN",
            "DEF:outdoor_dewMin=./rrd/temperatures.rrd:outdoor_dew:MIN",
            "DEF:indoor_dewMin=./rrd/temperatures.rrd:indoor_dew:MIN",
            "CDEF:outdoor-f=outdoor,1.8,*,32,+",
            "CDEF:indoor-f=indoor,1.8,*,32,+",
            "CDEF:outdoor_dew-f=outdoor_dew,1.8,*,32,+",
            "CDEF:indoor_dew-f=indoor_dew,1.8,*,32,+",
            "CDEF:outdoorMax-f=outdoorMax,1.8,*,32,+",
            "CDEF:indoorMax-f=indoorMax,1.8,*,32,+",
            "CDEF:outdoor_dewMax-f=outdoor_dewMax,1.8,*,32,+",
            "CDEF:indoor_dewMax-f=indoor_dewMax,1.8,*,32,+",
            "CDEF:outdoorMin-f=outdoorMin,1.8,*,32,+",
            "CDEF:indoorMin-f=indoorMin,1.8,*,32,+",
            "CDEF:outdoor_dewMin-f=outdoor_dewMin,1.8,*,32,+",
            "CDEF:indoor_dewMin-f=indoor_dewMin,1.8,*,32,+",
            "LINE1:outdoor#ff0000:Outdoor         ",
            "GPRINT:outdoor:LAST:Cur\: %5.2lf °C",
            "GPRINT:outdoor-f:LAST: %5.1lf °F",
            "GPRINT:outdoorMax:MAX:Max\: %5.2lf °C",
            "GPRINT:outdoorMax-f:MAX: %5.1lf °F",
            "GPRINT:outdoorMin:MIN:Min\: %5.2lf °C",
            "GPRINT:outdoorMin-f:MIN: %5.1lf °F\l",
            "LINE1:outdoor_dew#ff00ff:Outdoor Dewpoint",
            "GPRINT:outdoor_dew:LAST:Cur\: %5.2lf °C",
            "GPRINT:outdoor_dew-f:LAST: %5.1lf °F",
            "GPRINT:outdoor_dewMax:MAX:Max\: %5.2lf °C",
            "GPRINT:outdoor_dewMax-f:MAX: %5.1lf °F",
            "GPRINT:outdoor_dewMin:MIN:Min\: %5.2lf °C",
            "GPRINT:outdoor_dewMin-f:MIN: %5.1lf °F\l",
            "LINE1:indoor#0000ff:Indoor          ",
            "GPRINT:indoor:LAST:Cur\: %5.2lf °C",
            "GPRINT:indoor-f:LAST: %5.1lf °F",
            "GPRINT:indoorMax:MAX:Max\: %5.2lf °C",
            "GPRINT:indoorMax-f:MAX: %5.1lf °F",
            "GPRINT:indoorMin:MIN:Min\: %5.2lf °C",
            "GPRINT:indoorMin-f:MIN: %5.1lf °F\l",
            "LINE1:indoor_dew#00ffff:Indoor Dewpoint ",
            "GPRINT:indoor_dew:LAST:Cur\: %5.2lf °C",
            "GPRINT:indoor_dew-f:LAST: %5.1lf °F",
            "GPRINT:indoor_dewMax:MAX:Max\: %5.2lf °C",
            "GPRINT:indoor_dewMax-f:MAX: %5.1lf °F",
            "GPRINT:indoor_dewMin:MIN:Min\: %5.2lf °C",
            "GPRINT:indoor_dewMin-f:MIN: %5.1lf °F\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    try:
        result = rrdtool.graph("/mnt/tmp/humidities.png",
            common_args,
            "--title", "Humidity",
            "--vertical-label", "Relative (%)",
            "--right-axis-label", "Relative (%)",
            "--right-axis", "1:0",
            "--height", "300",
            "DEF:outdoor=./rrd/humidities.rrd:outdoor:LAST",
            "DEF:indoor=./rrd/humidities.rrd:indoor:LAST",
            "VDEF:outdoorMax=outdoor,MAXIMUM",
            "VDEF:outdoorMin=outdoor,MINIMUM",
            "VDEF:indoorMax=indoor,MAXIMUM",
            "VDEF:indoorMin=indoor,MINIMUM",
            "LINE1:outdoor#ff0000:Outdoor",
            "GPRINT:outdoor:LAST:Cur\: %.1lf%%",
            "GPRINT:outdoorMax:Max\: %.1lf%%",
            "GPRINT:outdoorMin:Min\: %.1lf%%\l",
            "LINE1:indoor#0000ff:Indoor ",
            "GPRINT:indoor:LAST:Cur\: %.1lf%%",
            "GPRINT:indoorMax:Max\: %.1lf%%",
            "GPRINT:indoorMin:Min\: %.1lf%%\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    try:
        result = rrdtool.graph("/mnt/tmp/pressures.png",
            common_args,
            "--title", "Barometric Pressure (MSL)",
            "--vertical-label", "hPa",
            "--right-axis-label", "hPa",
            "--right-axis", "1:0", "--right-axis-format", "%4.0lf",
            "--height", "300",
            "--lower-limit", "998", "--upper-limit", "1018",
            "--y-grid", "1:2",
            "--units-exponent", "0",
            "DEF:indoor=./rrd/pressures.rrd:indoor:LAST",
            "VDEF:indoorMax=indoor,MAXIMUM",
            "VDEF:indoorMin=indoor,MINIMUM",
            "LINE1:indoor#00ff00:Local",
            "GPRINT:indoor:LAST:Cur\: %.2lf hPa",
            "GPRINT:indoorMax:Max\: %.2lf hPa",
            "GPRINT:indoorMin:Min\: %.2lf hPa\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    try:
        result = rrdtool.graph("/mnt/tmp/gas.png",
            common_args,
            "--title", "Gas Resistance",
            "--vertical-label", "Ω",
            "--right-axis-label", "Ω",
            "--right-axis", "1:0",
            "--height", "250",
            "DEF:indoor=./rrd/gas.rrd:indoor:LAST",
            "VDEF:indoorMax=indoor,MAXIMUM",
            "VDEF:indoorMin=indoor,MINIMUM",
            "LINE1:indoor#0000ff:Indoor",
            "GPRINT:indoor:LAST:Cur\: %.1lf%s Ω",
            "GPRINT:indoorMax:Max\: %.1lf%s Ω",
            "GPRINT:indoorMin:Min\: %.1lf%s Ω\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    try:
        result = rrdtool.graph("/mnt/tmp/wind.png",
            common_args,
            "--title", "Wind Speeds",
            "--vertical-label", "Miles Per Hour",
            "--right-axis-label", "Miles Per Hour",
            "--right-axis", "1:0",
            "--height", "250",
            "DEF:outdoor_wind=./rrd/wind.rrd:outdoor_wind:LAST",
            "DEF:outdoor_windGust=./rrd/wind.rrd:outdoor_windGust:LAST",
            "VDEF:outdoor_windMax=outdoor_wind,MAXIMUM",
            "VDEF:outdoor_windMin=outdoor_wind,MINIMUM",
            "VDEF:outdoor_windGustMax=outdoor_windGust,MAXIMUM",
            "VDEF:outdoor_windGustMin=outdoor_windGust,MINIMUM",
            "LINE1:outdoor_wind#0000ff:Wind",
            "GPRINT:outdoor_wind:LAST:Cur\: %.1lf",
            "GPRINT:outdoor_windMax:Max\: %.1lf",
            "GPRINT:outdoor_windMin:Min\: %.1lf\l",
            "LINE1:outdoor_windGust#ff0000:Gust ",
            "GPRINT:outdoor_windGust:LAST:Cur\: %.1lf",
            "GPRINT:outdoor_windGustMax:Max\: %.1lf",
            "GPRINT:outdoor_windGustMin:Min\: %.1lf\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    try:
        result = rrdtool.graph("/mnt/tmp/uv.png",
            common_args,
            "--title", "UV Index",
            "--vertical-label", "Index",
            "--right-axis-label", "Index",
            "--right-axis", "1:0",
            "--height", "250",
            "DEF:outdoor=./rrd/uv.rrd:outdoor:LAST",
            "VDEF:outdoorMax=outdoor,MAXIMUM",
            "LINE1:outdoor#ffa500:Outdoor",
            "GPRINT:outdoor:LAST:Cur\: %.1lf",
            "GPRINT:outdoorMax:Max\: %.1lf\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    try:
        result = rrdtool.graph("/mnt/tmp/pi.png",
            common_args,
            "--title", "Pi Temperatures",
            "--vertical-label", "Celsius",
            "--right-axis-label", "Fahrenheit",
            "--right-axis", "1.8:32",
            "--height", "150",
            "DEF:pi=./rrd/temperatures.rrd:pi:LAST",
            "DEF:picow=./rrd/temperatures.rrd:picow:LAST",
            "DEF:piMax=./rrd/temperatures.rrd:pi:MAX",
            "DEF:picowMax=./rrd/temperatures.rrd:picow:MAX",
            "DEF:piMin=./rrd/temperatures.rrd:pi:MIN",
            "DEF:picowMin=./rrd/temperatures.rrd:picow:MIN",
            "CDEF:pi-f=pi,1.8,*,32,+",
            "CDEF:picow-f=picow,1.8,*,32,+",
            "CDEF:piMax-f=piMax,1.8,*,32,+",
            "CDEF:piMin-f=piMin,1.8,*,32,+",
            "CDEF:picowMax-f=picowMax,1.8,*,32,+",
            "CDEF:picowMin-f=picowMin,1.8,*,32,+",
            "LINE1:picow#ff0000:Pico W MCU",
            "GPRINT:picow:LAST:Cur\: %5.2lf °C",
            "GPRINT:picow-f:LAST: %5.1lf °F",
            "GPRINT:picowMax:MAX:Max\: %5.2lf °C",
            "GPRINT:picowMax-f:MAX: %5.1lf °F",
            "GPRINT:picowMin:MIN:Min\: %5.2lf °C",
            "GPRINT:picowMin-f:MIN: %5.1lf °F\l",
            "LINE1:pi#0000ff:Zero W CPU",
            "GPRINT:pi:LAST:Cur\: %5.2lf °C",
            "GPRINT:pi-f:LAST: %5.1lf °F",
            "GPRINT:piMax:MAX:Max\: %5.2lf °C",
            "GPRINT:piMax-f:MAX: %5.1lf °F",
            "GPRINT:piMin:MIN:Min\: %5.2lf °C",
            "GPRINT:piMin-f:MIN: %5.1lf °F\l"
        )
    except (rrdtool.ProgrammingError, rrdtool.OperationalError) as err:
        logging.error(f"Error creating graph: {err}")
        logging.error(f"Fail! Result: {result}")
    else:
        logging.info(f"Success! Width: {result[0]} Height: {result[1]} Extra Info: {result[2]}")

    logging.info("Done creating graphs")

# Updates the SQLite database with the provided data
def update_sqlite_database(started, epoch, outdoor_c, outdoor_dew, outdoor_hum, indoor_c, indoor_dew, indoor_hum, indoor_press, outdoorUV, outdoor_wind, outdoor_windGust, indoor_gas, pi_temp_c, picow_temp_c):
    try:
        logging.info(f"Updating SQLite database")
        #epoch = round(started.timestamp()) # convert datetime to unix epoch time before INSERT, instead of during INSERT, in the SCHEMA or in SELECT later on
        logging.debug(f"Epoch time: {epoch}")
        cursor.execute(
            "INSERT INTO data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (started, epoch, outdoor_c, outdoor_dew, outdoor_hum, indoor_c, indoor_dew, indoor_hum, indoor_press, outdoorUV, outdoor_wind, outdoor_windGust, indoor_gas, pi_temp_c, picow_temp_c)
        )
        connection.commit()
        logging.info(f"SQLite database updated successfully.")
    except sqlite3.Error as e:
        logging.error(f"Error updating SQLite database: {e}")

# Inter-process communication with 'freyrFlask.py'
def notify_flask():
    try:
        responseFlask = requests.post("http://127.0.0.1:5000/notify", timeout=5)
        responseFlask.raise_for_status()  # Raise an error for bad responses
        # Code below here will only run if the request is successful
        logging.info(f"Flask notified: {responseFlask.status_code} - {responseFlask.text}")
    except requests.exceptions.HTTPError as errh: # If the error is an HTTP error code, then:
        logging.error(errh) # log error code
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err)
    except Exception as e:
        logging.error(f"Failed to notify Flask: {e}")

def graceful_exit(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name
    logging.warning(f"Received signal {signal_name} to exit. Cleaning up...")
    # Close the SQLite connection
    if connection:
        connection.close()
        logging.warning(f"Closed connection to SQLite database")
    logging.warning("Exiting freyr...")
    sys.exit(0)

def main():
    logging.info("Starting main while loop")
    # Loop parameters
    interval = config.LOOP_INTERVAL
    interval = timedelta(seconds=interval) # Convert integer into proper time format
    loop_counter = 0
    while True: # main while loop that should run forever
        started = datetime.now() # Start timing the operation
        logging.info("~~~~~~~~~~~~~~new cycle~~~~~~~~~~~~~~~~") # Start logging cycle with a row of tildes to differentiate
        logging.debug(f"Loop started at {started}")
        epoch = int(started.timestamp()) # truncate with int() instead of round() for time-alignment below
        logging.debug(f"Epoch time: {epoch}")
        alignedEpoch = epoch - (epoch % 60) # Align to 60 second intervals
        logging.debug(f"60 second aligned epoch time: {alignedEpoch}")
        outdoor_c, outdoor_hum, outdoor_dew, picow_temp_c = get_outdoor()
        outdoor_wind, outdoor_windGust = get_OWM()
        indoor_c, indoor_hum, indoor_dew, indoor_press, indoor_gas = get_indoor()
        pi_temp_c = pi_temp()
        logging.info("Updating databases...")
        update_rrd("temperatures.rrd", alignedEpoch, f"{alignedEpoch}:{outdoor_c}:{indoor_c}:{pi_temp_c}:{picow_temp_c}:{outdoor_dew}:{indoor_dew}")
        update_rrd("humidities.rrd", alignedEpoch, f"{alignedEpoch}:{outdoor_hum}:{indoor_hum}")
        update_rrd("gas.rrd", alignedEpoch, f"{alignedEpoch}:{indoor_gas}")
        update_rrd("pressures.rrd", alignedEpoch, f"{alignedEpoch}:{indoor_press}")
        update_rrd("wind.rrd", alignedEpoch, f"{alignedEpoch}:{outdoor_wind}:{outdoor_windGust}")

        # Only update UV every 30 loops/minutes because of API rate limits
        if loop_counter % 30 == 0:
            alignedEpoch = epoch - (epoch % 1800)  # 30-minute alignment for UV
            logging.debug(f"30 minute aligned epoch time: {alignedEpoch}")
            outdoorUV = get_OpenUV_Index()
            update_rrd("uv.rrd", alignedEpoch, f"{alignedEpoch}:{outdoorUV}")

        loop_counter += 1  # Increment loop counter
        update_sqlite_database(started, epoch, outdoor_c, outdoor_dew, outdoor_hum, indoor_c, indoor_dew, indoor_hum, indoor_press, outdoorUV, outdoor_wind, outdoor_windGust, indoor_gas, pi_temp_c, picow_temp_c)
        post_WU(outdoor_c, outdoor_dew, outdoor_hum, indoor_press) # Post to Weather Underground
        logging.info("Done updating databases")
        create_graphs()
        notify_flask()

        ended = datetime.now() # Stop timing the operation
        loop_time = (ended - started).seconds
        logging.info(f"Loop took {loop_time} seconds")
        # Compute the amount of time it took to run the loop above
        # then sleep for the remaining time left
        # if it is less than the configured loop interval
        if started and ended and ended - started < interval:
            remaining = interval.seconds - loop_time
            logging.info(f"Sleeping for {remaining} seconds...")
            time.sleep((interval - (ended - started)).seconds) # calculate this again (instead of using remaining var above) at the last moment so it's more precise

if __name__ == "__main__":
    try:
        signal.signal(signal.SIGINT, graceful_exit)
        signal.signal(signal.SIGTERM, graceful_exit)
        init()
        main()
    except Exception as e:
        logging.exception(f"main crashed. Error: {e}")
