# reefer

This started out as a project to control my reef aquarium, hence the name. It then morphed into a simple Python script to check the indoor temp/humidity and compare it with the outdoors using OpenWeather API.

The hardware is a FT232H from Adafruit and a Si7021 sensor. The FT232H is a pain in the butt to set up from scratch, espcially on Windows. I use Zadig to change the driver to libusbK, then the environment variable must be set "BLINKA_FT232H=1". Use the hack to refresh the environment variables without rebooting (now included, see ```RefreshEnv.cmd```), then the Python script should work. If you ever switch USB ports you must use Zadig to change the driver again.

Adafruit has written a guide for the FT232H, but it is confusing and becoming out of date: https://learn.adafruit.com/circuitpython-on-any-computer-with-ft232h

## Requires:
- Python 3
- pip
- pyftdi
- pyserial
- pyusb
- Adafruit-Blinka
- adafruit-circuitpython-busdevice
- adafruit-circuitpython-si7021
- Adafruit-PlatformDetect
- Adafruit-PureIO
- requests
- charset_normalizer
- certifi
- urllib3
- idna
- rrdtool (added to system $PATH/%PATH%/Path)

## RRD
#### Create RRD databases:

```
$ rrdtool create temperatures-c.rrd --step 60 DS:outdoor:GAUGE:120:0:55 DS:indoor:GAUGE:120:0:55 RRA:MAX:0.5:1:1440
$ rrdtool create humidities.rrd --step 60 DS:outdoor:GAUGE:120:0:100 DS:indoor:GAUGE:120:0:100 RRA:MAX:0.5:1:1440
```
This will create databases with a 60 second interval, 120 second heartbeat timeout, between 0 and 55 degrees Celsius, and 0-100% relative humidity, with 24 hours of data before rolling over. You may need to configure for lower than 0 degrees Celsius, but I live in the second hottest place on the planet so these are my settings.

More information here: https://michael.bouvy.net/post/graph-data-rrdtool-sensors-arduino

## HTML

```index.html```

Very simple HTML to display both graphs. This does not need a webserver. It can be opened locally and will refresh the entire page every 60 seconds.
