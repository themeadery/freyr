import time
import glob
import board
import adafruit_si7021
import requests
import subprocess
import vcgencmd

# OpenWeather API
query = {'lat':'put your latitude here', 'lon':'put your longitude here', 'appid':'put your API key here'}
# Initialize Si7021
sensor = adafruit_si7021.SI7021(board.I2C())
# Initialize DS18B20
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

# Global Celsius to Fahrenheit conversion function
def c_to_f(temp_c):
    return (temp_c * 1.8) + 32.0

# Indoor Si7021 function
def indoor_temp_hum():
    temp_c = sensor.temperature - 1.0 # Sensor error correction
    temp_f = c_to_f(temp_c)
    hum = sensor.relative_humidity
    return temp_c, temp_f, hum

# DS18B20 functions
def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp():
    lines = read_temp_raw()
    print(f"Debug read_temp_raw #1: {lines}") # Debug
    while len(lines) != 2:
        print(f"Debug read_temp_raw #2: {lines}") # Debug
        time.sleep(0.2)
        lines = read_temp_raw()
        print(f"Debug read_temp_raw #3: {lines}") # Debug
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = c_to_f(temp_c)
        return temp_c, temp_f

# Pi Temperature function
def pi_temp():
    temp_c = vcgencmd.measure_temp()
    temp_f = c_to_f(temp_c)
    return temp_c, temp_f

# Main Loop
while True:
    print("\n--------------------------------")
    print("\nOutdoor")
    try:
        response = requests.get('https://api.openweathermap.org/data/2.5/weather', params=query, timeout=5)
        response.raise_for_status()
        # Code below here will only run if the request is successful
        main = response.json()['main']
        tempk = main['temp']
        outdoor_c = tempk - 273.14
        outdoor_f = c_to_f(outdoor_c)
        outdoor_hum = main['humidity']
        print(f"Temperature: {outdoor_c:.2f} °C | {outdoor_f:.2f} °F")
        print(f"Humidity: {outdoor_hum:.1f}%")
        # Code above here will only run if the request is successful
    except requests.exceptions.HTTPError as errh:
        print(errh)
    except requests.exceptions.ConnectionError as errc:
        print(errc)
    except requests.exceptions.Timeout as errt:
        print(errt)
    except requests.exceptions.RequestException as err:
        print(err)

    print("\nIndoor")
    # indoor_c = sensor.temperature - 1.8 # Sensor error correction
    # indoor_f = c_to_f(indoor_c)
    # indoor_hum = sensor.relative_humidity
    indoor_c, indoor_f, indoor_hum = indoor_temp_hum()
    print(f"Temperature: {indoor_c:.2f} °C | {indoor_f:.2f} °F")
    print(f"Humidity: {indoor_hum:.1f}%")

    print("\nTank")
    tank_c, tank_f = read_temp()
    print(f"Temperature: {tank_c:.2f} °C | {tank_f:.2f} °F")

    print("\nPi")
    pi_temp_c, pi_temp_f = pi_temp()
    print(f"CPU: {pi_temp_c:.2f} °C | {pi_temp_f:.2f} °F")

    print("\nUpdating RRD databases...")
    # Debug
    # print(f"Debug rrdtool temperature string N:{outdoor_c}:{indoor_c}:{tank_c}")
    # print(f"Debug rrdtool humidity string N:{outdoor_hum}:{indoor_hum}")
    #
    subprocess.run(["rrdtool", "updatev", "temperatures.rrd", f"N:{outdoor_c}:{indoor_c}:{tank_c}:{pi_temp_c}"])
    subprocess.run(["rrdtool", "updatev", "humidities.rrd", f"N:{outdoor_hum}:{indoor_hum}"])
    print("Done")

    print("\nCreating graphs...")
    subprocess.run([
     "rrdtool", "graph",
     "temperatures.png",
     "--font", "DEFAULT:10:",
     "--title", "Temperature",
     "--vertical-label", "Celsius",
     "--right-axis-label", "Fahrenheit",
     "--right-axis", "1.8:32",
     "--width", "600", "--height", "220",
     "--alt-autoscale",
     "DEF:outdoor=temperatures.rrd:outdoor:MAX",
     "DEF:indoor=temperatures.rrd:indoor:MAX",
     "DEF:tank=temperatures.rrd:tank:MAX",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:%2.1lf °C",
     "CDEF:outdoor-f=outdoor,1.8,*,32,+", "GPRINT:outdoor-f:LAST:%2.1lf °F",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST:%2.1lf °C",
     "CDEF:indoor-f=indoor,1.8,*,32,+", "GPRINT:indoor-f:LAST:%2.1lf °F",
     "LINE1:tank#00ff00:Tank",
     "GPRINT:tank:LAST:%2.1lf °C",
     "CDEF:tank-f=tank,1.8,*,32,+", "GPRINT:tank-f:LAST:%2.1lf °F"
     ])
    subprocess.run([
     "rrdtool", "graph",
     "humidities.png",
     "--font", "DEFAULT:10:",
     "--title", "Humidity",
     "--vertical-label", "Relative (%)",
     "--right-axis", "1:0",
     "--width", "600", "--height", "160",
     "--alt-autoscale",
     "DEF:outdoor=humidities.rrd:outdoor:MAX",
     "DEF:indoor=humidities.rrd:indoor:MAX",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:%2.1lf%%",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST:%2.1lf%%"
     ])
    subprocess.run([
      "rrdtool", "graph",
      "pi.png",
      "--font", "DEFAULT:10:",
      "--title", "Pi Temperature",
      "--vertical-label", "Celsius",
      "--right-axis-label", "Fahrenheit",
      "--right-axis", "1.8:32",
      "--width", "600", "--height", "140",
      # "--alt-autoscale",
      "DEF:pi=temperatures.rrd:pi:MAX",
      "LINE1:pi#ff0000:CPU",
      "GPRINT:pi:LAST:%2.1lf °C",
      "CDEF:pi-f=pi,1.8,*,32,+", "GPRINT:pi-f:LAST:%2.1lf °F",
     ])
    print("Done")

    time.sleep(60)
