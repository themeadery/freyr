import time
import board
import adafruit_si7021
import requests
import subprocess

query = {'lat':'put your latitude here', 'lon':'put your longitude here', 'appid':'put your API key here'}
sensor = adafruit_si7021.SI7021(board.I2C())

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
        tempc = tempk-273.14
        print("Temperature: %0.2f °C" % tempc)
        tempf = tempc*9/5+32
        print("Temperature: %0.2f °F" % tempf)
        hum = main['humidity']
        print("Humidity: %0.1f%%" % hum)
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
    fahrenheit = sensor.temperature*9/5+32
    print("Temperature: %0.2f °C" % sensor.temperature)
    print("Temperature: %0.2f °F" % fahrenheit)
    print("Humidity: %0.1f%%" % sensor.relative_humidity)

    print("\nUpdating RRD databases...")
    subprocess.run(["rrdtool", "update", "temperatures-c.rrd", "N:%0.2f" % tempc + ":%0.2f" % sensor.temperature])
    subprocess.run(["rrdtool", "update", "humidities.rrd", "N:%0.1f" % hum + ":%0.1f" % sensor.relative_humidity])
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
     "DEF:outdoor=temperatures-c.rrd:outdoor:MAX",
     "DEF:indoor=temperatures-c.rrd:indoor:MAX",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:%2.1lf °C",
     "CDEF:outdoor-f=outdoor,1.8,*,32,+", "GPRINT:outdoor-f:LAST:%2.1lf °F",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST:%2.1lf °C",
     "CDEF:indoor-f=indoor,1.8,*,32,+", "GPRINT:indoor-f:LAST:%2.1lf °F"])
    subprocess.run([
     "rrdtool", "graph",
     "humidities.png",
     "--font", "DEFAULT:10:",
     "--title", "Humidity",
     "--vertical-label", "Relative (%)",
     "--right-axis", "1:0",
     "--width", "600", "--height", "200",
     "--alt-autoscale",
     "DEF:outdoor=humidities.rrd:outdoor:MAX",
     "DEF:indoor=humidities.rrd:indoor:MAX",
     "LINE1:outdoor#ff0000:Outdoor",
     "GPRINT:outdoor:LAST:%2.1lf%%",
     "LINE1:indoor#0000ff:Indoor",
     "GPRINT:indoor:LAST:%2.1lf%%"])
    print("Done")

    time.sleep(60)
