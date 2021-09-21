import time
import board
import adafruit_si7021
import requests
import json

query = {'lat':'put your latitude here', 'lon':'put your longitude here', 'appid':'put your API key here'}
sensor = adafruit_si7021.SI7021(board.I2C())
#hasl = 217 # Height above sea-level for weather station in meters

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
        # press = main['pressure']
        # print("Aggregate Uncorrected Station Pressures: %0.2f hPA" % press)
        # slpress = press + ((press * 9.80665 * hasl)/(287 * (273 + tempc + (hasl/400))))
        # print("Sea-Level Pressure: %0.2f hPA" % slpress)
        # slpress = (press * pow(1 - (0.0065 * hasl / (tempc + 0.0065 * hasl + 273.15)), -5.257))
        # print("Sea-Level Pressure: %0.2f hPA" % slpress)
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
    time.sleep(15)
