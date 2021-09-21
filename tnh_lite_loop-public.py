import time
import board
import adafruit_si7021
import requests

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
    time.sleep(15)
