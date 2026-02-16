from machine import ADC, Pin
import math
import ujson as json

thermistor = ADC(26)  # Thermistor is on GP26 (ADC0 Pin 31)
mcu = ADC(ADC.CORE_TEMP) # Internal MCU Temperature Sensor
led = Pin(25, Pin.OUT) # Onboard LED for debugging

# Voltage Divider
Vin = 3.3
Ro = 10000  # 10k Resistor

# Steinhart Constants
A = 0.001129148
B = 0.000234125
C = 0.0000000876741

def read_mcu_temp():
    adc_value = mcu.read_u16()
    volt = (3.3/65535) * adc_value
    mcu_temp = 27 - (volt - 0.706)/0.001721
    return mcu_temp

def read_thermistor_temp():
    n = 64 # Number of samples
    samples = [] # Create an empty list for all 64 samples
    for _ in range(n):
        adc = thermistor.read_u16()
        samples.append(adc)
    average = sum(samples) / len(samples)
    #print("Average ADC value:", average) # Debug
    Vout = (3.3/65535)*average
    Rt = (Vout * Ro) / (Vin - Vout) # Calculate Resistance
    TempK = 1 / (A + (B * math.log(Rt)) + C * math.pow(math.log(Rt), 3)) # Steinhart - Hart Equation
    TempC = TempK - 273.15 # Convert from Kelvin to Celsius
    return TempC

def main():
    led.on()
    thermistor_temp = read_thermistor_temp()
    mcu_temp = read_mcu_temp() # reading is low because thermistor is causing Vdroop on 3.3v rail?
    data = {
    "temperature": thermistor_temp,
    "mcu": mcu_temp
    }
    print(json.dumps(data))
    led.off()

if __name__ == "__main__":
    main()
