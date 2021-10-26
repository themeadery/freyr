# reefer

This started out as a project to control my reef aquarium, hence the name. It then morphed into a simple Python script to check the indoor temp/humidity and compare it with the outdoors using OpenWeather API.

The hardware is a FT232H from Adafruit and a Si7021 sensor. The FT232H is a pain in the butt to set up from scratch, espcially on Windows. I use Zadig to change the driver to libusbK, then the environment variable must be set "BLINKA_FT232H=1". Use the hack to refresh the environment variables without rebooting (now included, see RefreshEnv.cmd), then the Python script should work. If you ever switch USB ports you must use Zadig to change the driver again.

Adafruit has written a guide for the FT232H, but it is confusing and becoming out of date: https://learn.adafruit.com/circuitpython-on-any-computer-with-ft232h

Requires Python 3

At one point it created RRD graphs and updated a local website, but that feature is currently broken.
