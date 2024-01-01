# SPDX-FileCopyrightText: Copyright (c) 2023 Jose D. Montoya
#
# SPDX-License-Identifier: MIT
"""
`micropython_si7021`
================================================================================

MicroPython Driver for the SI7021 Temperature and Humidity sensor


* Author(s): Jose D. Montoya

Implementation Notes
--------------------

**Software and Dependencies:**

This library depends on Micropython

"""

# pylint: disable=too-many-arguments, missing-function-docstring, unused-variable

import time
import struct
from micropython import const


__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/jposada202020/MicroPython_SI7021.git"


class RegisterStructRW:
    """
    Register Struct
    """

    def __init__(
        self,
        form: str,
        cmd_read: int = None,
        cmd_write: int = None,
    ) -> None:
        self.format = form
        self.lenght = struct.calcsize(form)
        self.cmd_read = cmd_read
        self.cmd_write = cmd_write

    def __get__(
        self,
        obj,
        objtype=None,
    ):
        payload = bytes([self.cmd_read])
        obj._i2c.writeto(obj._address, payload)

        data = bytearray(self.lenght)
        data = obj._i2c.readfrom(obj._address, self.lenght)

        val = struct.unpack(self.format, data)[0]

        return val

    def __set__(self, obj, value):
        payload = bytes([self.cmd_read])
        obj._i2c.writeto(obj._address, payload)

        data = bytearray(self.lenght)
        data = obj._i2c.readfrom(obj._address, self.lenght)

        data = bytearray(self.lenght)
        payload = payload = bytes([self.cmd_write, value])
        obj._i2c.writeto(obj._address, payload)


_REG_WHOAMI = const(0x40)
_TEMP_NOHOLD_CMD = const(0xF3)
_HUMIDITY_NOHOLD_CMD = const(0xF5)

TEMP_14_RH_12 = const(0)
TEMP_12_RH_8 = const(1)
TEMP_13_RH_10 = const(128)
TEMP_11_RH_11 = const(129)
sensor_resolution = (TEMP_14_RH_12, TEMP_12_RH_8, TEMP_13_RH_10, TEMP_11_RH_11)

HEATER_ON = const(4)
HEATER_OFF = const(0)
heater_options = (HEATER_ON, HEATER_OFF)


class SI7021:
    """Main class for the Sensor

    :param ~machine.I2C i2c: The I2C bus the SI7021 is connected to.
    :param int address: The I2C device address. Defaults to :const:`0x40`

    :raises RuntimeError: if the sensor is not found


    **Quickstart: Importing and using the device**

    Here is an example of using the :class:`micropython_si7021.SI7021` class.
    First you will need to import the libraries to use the sensor

    .. code-block:: python

        from machine import Pin, I2C
        import micropython_si7021 as si7021

    Once this is done you can define your `machine.I2C` object and define your sensor object

    .. code-block:: python

        i2c = I2C(sda=Pin(8), scl=Pin(9))
        si = si7021.SI7021(i2c)

    Now you have access to the :attr:`temperature` and `humidity` attributes

    .. code-block:: python

        temp = si.temperature
        hum = si.humidity

    """

    _reg_1 = RegisterStructRW("B", 0xE7, 0xE6)

    _sensor_res = {
        0: "TEMP_14_RH_12",
        1: "TEMP_12_RH_8",
        128: "TEMP_13_RH_10",
        129: "TEMP_11_RH_11",
    }
    _heater_status = {0: "OFF", 4: "ON"}
    # Conversion Times According to Datasheet Table 2
    conversion_time = {
        "TEMP_14_RH_12": 10.8,
        "TEMP_12_RH_8": 3.8,
        "TEMP_13_RH_10": 6.2,
        "TEMP_11_RH_11": 2.4,
    }

    # Register User 1
    # | RES(1) | VDDS |  ---- | ---- | ---- | HTRE | ---- | RES(0) |

    def __init__(self, i2c, address=0x40):
        self._i2c = i2c
        self._address = address
        self._conversion_time = self.conversion_time[self.resolution]

    @property
    def resolution(self):
        """
        Meassurement resolution. The resolution of the measures. This will return the
        `temperature` and `humidity` resolution. These values are linked so change the
        resolution in temperature will affect humidity's resolution

        +----------+--------+--------+
        | Value    | RH     | Temp   |
        +==========+========+========+
        | 00       | 12 bit | 14 bit |
        +----------+--------+--------+
        | 01       | 8 bit  | 12 bit |
        +----------+--------+--------+
        | 10       | 10 bit | 13 bit |
        +----------+--------+--------+
        | 11       | 11 bit | 11 bit |
        +----------+--------+--------+

        When selecting the values use the following variables:

        +----------------------------------------+-------------------------+
        | Mode                                   | Value                   |
        +========================================+=========================+
        | :py:const:`si7021.TEMP_14_RH_12`       | :py:const:`0b00000000`  |
        +----------------------------------------+-------------------------+
        | :py:const:`si7021.TEMP_12_RH_8`        | :py:const:`0b00000001`  |
        +----------------------------------------+-------------------------+
        | :py:const:`si7021.TEMP_13_RH_10`       | :py:const:`0b10000000`  |
        +----------------------------------------+-------------------------+
        | :py:const:`si7021.TEMP_11_RH_11`       | :py:const:`0b10000001`  |
        +----------------------------------------+-------------------------+

        Example
        ########

        .. code-block:: python

            from machine import Pin, I2C
            import micropython_si7021 as si7021

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            si = si7021.SI7021(i2c)

            si.resolution = si7021.TEMP_13_RH_10

        """

        mask = 0b10000001
        value = self._reg_1 & mask

        return self._sensor_res[value]

    @resolution.setter
    def resolution(self, value):
        if value not in sensor_resolution:
            raise ValueError("Please select a valid resolution")

        mask = 0b01111110
        reg_to_write = self._reg_1 & mask | value
        self._reg_1 = reg_to_write
        self._conversion_time = self.conversion_time[self.resolution]

    @property
    def temperature(self):
        """
        Returns the temperature in Celsius. Temperature resolution can be adjusted with
        the :attr:`temperature` attribute

        Example
        ########

        .. code-block:: python

            from machine import Pin, I2C
            import micropython_si7021 as si7021

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            si = si7021.SI7021(i2c)

            print("Temperature: ", si.temperature)

        """

        data = bytearray(3)
        self._i2c.writeto(self._address, struct.pack("B", _TEMP_NOHOLD_CMD))
        data = self.verify_data(data)

        value, _ = struct.unpack(">HB", data)

        value = value * 175.72 / 65536.0 - 46.85
        return value

    @property
    def humidity(self):
        """Returns the humidity in %. Temperature resolution can be adjusted with the
         :attr:`humidity` attribute

        Example
        ########

        .. code-block:: python

            from machine import Pin, I2C
            import micropython_si7021 as si7021

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            si = si7021.SI7021(i2c)

            print("Relative Humidity: ", si.humidity)


        """
        data = bytearray(3)
        data[0] = 0x69
        self._i2c.writeto(self._address, struct.pack("B", _HUMIDITY_NOHOLD_CMD))

        time.sleep(self._conversion_time / 1000)
        data = self.verify_data(data)

        value, _ = struct.unpack(">HB", data)

        value = value * 125.0 / 65536.0 - 6
        return value

    def verify_data(self, data):
        while True:
            try:
                self._i2c.readfrom_into(self._address, data)
            except OSError:
                pass
            else:
                if data[0] != 0x69:
                    break
        return data

    @property
    def heater(self):
        """
        Sensor Heater Status.

        * `False` : Off
        * `True` : ON

        Example
        ########

        .. code-block:: python

            from machine import Pin, I2C
            import micropython_si7021 as si7021

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            si = si7021.SI7021(i2c)

            # Turning ON the Heater
            print("Status of the Sensor Heater: ", si.heater)
            si.heater = si7021.HEATER_ON
            print("Status of the Sensor Heater: ", si.heater)

        """

        mask = 0b00000100
        value = self._reg_1 & mask

        return self._heater_status[value]

    @heater.setter
    def heater(self, value):
        if value not in heater_options:
            raise ValueError("Please select a valid option")

        mask = 0b11111011
        reg_to_write = self._reg_1 & mask | value
        self._reg_1 = reg_to_write
