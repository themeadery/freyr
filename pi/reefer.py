import time
from datetime import datetime
from datetime import timedelta
#import glob
import bme680
import requests
import subprocess
import vcgencmd
import logging

# Loop interval
interval = 60 # in seconds
interval = timedelta(seconds=interval) # Convert integer into proper time format

# Set up logging
logging.basicConfig(filename='reefer.log', format='%(asctime)s - %(levelname)s - %(message)s')
logging.root.setLevel(logging.WARNING)

# API query definitions
queryOWN = {'lat':'put your lat here', 'lon':'put your lon here', 'appid':'put your API key here'} # OpenWeatherMap API
#queryAWC = {'ids':'put your airport code here', 'format':'json'} # Aviation Weather Center API

# Initialize HTTP(S) request sessions for reuse during API calls
sessionOWN = requests.Session() # OpenWeatherMap API
#sessionAWC = requests.Session() # Aviation Weather Center API

# Station altitude in meters
sta_alt = 276.0

""" # Initialize DS18B20
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave' """
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

# Global Celsius to Fahrenheit conversion function
def c_to_f(temp_c):
    return (temp_c * 1.8) + 32.0

# Station pressure to MSL Pressure conversion function
# Formula source: https://gist.github.com/cubapp/23dd4e91814a995b8ff06f406679abcf
def sta_press_to_mslp(sta_press, temp_c):
    mslp = sta_press + ((sta_press * 9.80665 * sta_alt)/(287 * (273 + temp_c + (sta_alt/400))))
    logging.info(f"{mslp:.2f} hPa MSL")
    return mslp

""" # DS18B20 functions
def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp():
    lines = read_temp_raw()
    # logging.info(f"Debug read_temp_raw #1: {lines}") # Debug
    while len(lines) != 2:
        logging.debug(f"Debug read_temp_raw #2: {lines}") # Debug
        time.sleep(0.2)
        lines = read_temp_raw()
        logging.debug(f"Debug read_temp_raw #3: {lines}") # Debug
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0 + 0.5 # Insert sensor error correction here if needed
        temp_f = c_to_f(temp_c)
        return temp_c, temp_f """
# Indoor BME680 function
def indoor_temp_hum_press():
    if sensor.get_sensor_data():
        temp_c = sensor.data.temperature # Insert sensor error correction here if needed, BME680 is pretty accurate
        temp_f = c_to_f(temp_c)
        hum = sensor.data.humidity
        sta_press = sensor.data.pressure
        logging.debug(f"{sta_press} hPa raw station pressure")
        press = sta_press_to_mslp(sta_press, temp_c) # convert to MSLP
        logging.debug(f"{temp_c} {temp_f} {hum} {press}")
        return temp_c, temp_f, hum, press

# Pi Temperature function
def pi_temp():
    temp_c = vcgencmd.measure_temp()
    temp_f = c_to_f(temp_c)
    return temp_c, temp_f

# Main Loop
while True:
    started = datetime.now() # Start timing the operation

    logging.info("Outdoor")

    try:
        responseOWN = sessionOWN.get('http://api.openweathermap.org/data/2.5/weather', params=queryOWN, timeout=8) # Don't use HTTPS
        responseOWN.raise_for_status()
        # Code below here will only run if the request is successful
        main = responseOWN.json()['main']
        tempk = main['temp']
        outdoor_c = tempk - 273.14
        outdoor_f = c_to_f(outdoor_c)
        outdoor_hum = main['humidity']
        logging.info(f"Temperature: {outdoor_c:.2f} °C | {outdoor_f:.2f} °F")
        logging.info(f"Humidity: {outdoor_hum:.1f}%")
        # Code above here will only run if the request is successful
    except requests.exceptions.HTTPError as errh:
        logging.error(errh)
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err)

    # Get barometric pressure from AWC METAR because it is more accurate than OpenWeather
    """ try:
        responseAWC = sessionAWC.get('https://beta.aviationweather.gov/cgi-bin/data/metar.php', params=queryAWC, timeout=8)
        # If the above command takes a long time (10+ seconds) you have an ipv6 routing/DNS error
        # This error was introduced somewhere between Python 3.7 and 3.9 or Raspbian Bullseye
        # The Python devs and the Requests Library devs have failed to merge proposed patches
        # Disable ipv6 temporarily by running "sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1"
        # If faster, look into a more permanent way to disable/fix ipv6 as the above is not persistent across reboots
        responseAWC.raise_for_status()
        outdoor_pressure = 'U' # Set to RRDtool specific null value if json from API is broken
        try:
            index0 = responseAWC.json()[0]
        except KeyError as errK:
            logging.error(errK)
        except IndexError as errI:
            logging.error(errI)
        except TypeError as errT:
            logging.error(errT)
        else:
            outdoor_pressure = index0['altim']
        logging.info(f"Barometric Pressure: {outdoor_pressure} hPa (MSL)")
    except requests.exceptions.HTTPError as errh:
        logging.error(errh)
    except requests.exceptions.ConnectionError as errc:
        logging.error(errc)
    except requests.exceptions.Timeout as errt:
        logging.error(errt)
    except requests.exceptions.RequestException as err:
        logging.error(err) """
    outdoor_pressure = 'U' # service above is broken indefinitely

    logging.info("Indoor")

    indoor_c, indoor_f, indoor_hum, indoor_press = indoor_temp_hum_press()
    logging.info(f"Temperature: {indoor_c:.2f} °C | {indoor_f:.2f} °F")
    logging.info(f"Humidity: {indoor_hum:.1f}%")
    logging.info(f"Pressure: {indoor_press:.2f} hPa MSLP") # converted to MSLP

    logging.info("Tank")
    """ tank_c, tank_f = read_temp()
    logging.info(f"Temperature: {tank_c:.2f} °C | {tank_f:.2f} °F") """
    tank_c = "U" # Sensor is broken

    logging.info("Pi")
    pi_temp_c, pi_temp_f = pi_temp()
    logging.info(f"CPU: {pi_temp_c:.2f} °C | {pi_temp_f:.2f} °F")

    logging.info("Updating RRD databases...")

    result = subprocess.run(["rrdtool", "updatev", "temperatures.rrd",
     f"N:{outdoor_c}:{indoor_c}:{tank_c}:{pi_temp_c}"
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
     f"N:{outdoor_pressure}:{indoor_press}"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')
    
    logging.info("Done")

    logging.info("Creating graphs...")
    result = subprocess.run([
     "rrdtool", "graph",
     "temperatures.png",
     "--font", "DEFAULT:10:",
     "--title", "Temperature",
     "--vertical-label", "Celsius",
     "--right-axis-label", "Fahrenheit",
     "--right-axis", "1.8:32",
     "--width", "860", "--height", "340",
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
     "DEF:outdoor=temperatures.rrd:outdoor:MAX",
     "DEF:indoor=temperatures.rrd:indoor:MAX",
     "DEF:tank=temperatures.rrd:tank:MAX",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:%2.1lf °C",
     "CDEF:outdoor-f=outdoor,1.8,*,32,+", "GPRINT:outdoor-f:LAST:%2.1lf °F",
     "COMMENT:\l",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST: %2.1lf °C",
     "CDEF:indoor-f=indoor,1.8,*,32,+", "GPRINT:indoor-f:LAST:%2.1lf °F",
     "COMMENT:\l",
     "LINE1:tank#00ff00:Tank",
     "GPRINT:tank:LAST:   %2.1lf °C",
     "CDEF:tank-f=tank,1.8,*,32,+", "GPRINT:tank-f:LAST:%2.1lf °F",
     "COMMENT:\l"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')

    result = subprocess.run([
     "rrdtool", "graph",
     "humidities.png",
     "--font", "DEFAULT:10:",
     "--title", "Humidity",
     "--vertical-label", "Relative (%)",
     "--right-axis", "1:0",
     "--width", "865", "--height", "280",
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
     "DEF:outdoor=humidities.rrd:outdoor:MAX",
     "DEF:indoor=humidities.rrd:indoor:MAX",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:%2.1lf%%",
     "COMMENT:\l",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST: %2.1lf%%",
     "COMMENT:\l"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')
    
    result = subprocess.run([
      "rrdtool", "graph",
      "pressures.png",
      "--font", "DEFAULT:10:",
      "--title", "Barometric Pressure (MSL)",
      "--vertical-label", "hPa",
      "--right-axis", "1:0", "--right-axis-format", "%4.0lf",
      "--width", "865", "--height", "540",
      "--lower-limit", "990", "--upper-limit", "1030",
      "--y-grid", "2:1",
      "--units-exponent", "0",
      "--border", "0",
      "--slope-mode",
      "-c", "BACK#333333",
      "-c", "CANVAS#18191A",
      "-c", "FONT#DDDDDD",
      "-c", "GRID#DDDDDD1A",
      "-c", "MGRID#DDDDDD33",
      "-c", "FRAME#18191A",
      "-c", "ARROW#333333",
      "DEF:outdoor=pressures.rrd:outdoor:MAX",
      "DEF:indoor=pressures.rrd:indoor:MAX",
      #"LINE1:outdoor#ff0000:Outdoor",
      #"GPRINT:outdoor:LAST:%.2lf hPa",
      #"COMMENT:\l",
      "LINE1:indoor#00ff00:Local",
      "GPRINT:indoor:LAST: %.2lf hPa",
      "COMMENT:\l"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')
    
    result = subprocess.run([
      "rrdtool", "graph",
      "pi.png",
      "--font", "DEFAULT:10:",
      "--title", "Pi Temperature",
      "--vertical-label", "Celsius",
      "--right-axis-label", "Fahrenheit",
      "--right-axis", "1.8:32",
      "--width", "860", "--height", "100",
      "--border", "0",
      "--slope-mode",
      "-c", "BACK#333333",
      "-c", "CANVAS#18191A",
      "-c", "FONT#DDDDDD",
      "-c", "GRID#DDDDDD1A",
      "-c", "MGRID#DDDDDD33",
      "-c", "FRAME#18191A",
      "-c", "ARROW#333333",
      "DEF:pi=temperatures.rrd:pi:MAX",
      "AREA:pi#ff0000#320000:CPU",
      "GPRINT:pi:LAST:%2.1lf °C",
      "CDEF:pi-f=pi,1.8,*,32,+", "GPRINT:pi-f:LAST:%2.1lf °F",
      "COMMENT:\l"
     ], capture_output=True, text=True)
    logging.info(f'return code: {result.returncode}')
    logging.info(f'{result.stdout}')
    if result.stderr:
        logging.error(f'errors: {result.stderr}')
    
    logging.info("Done")

    ended = datetime.now() # Stop timing the operation
    # Compute the amount of time it took to run the loop above
    # then sleep for the remaining time left
    # if it is less than the configured loop interval
    if started and ended and ended - started < interval:
        logging.info("Sleeping...")
        time.sleep((interval - (ended - started)).seconds)
