# bare minimum exec code to run on pico
# write extra logic in freyr.py
import pyboard

pyb = pyboard.Pyboard('/dev/ttyACM0', 115200)
pyb.enter_raw_repl()
pyb.exec('from machine import ADC')
pyb.exec('thermistor = ADC(26)')
pyb.exec('raw_adc = thermistor.read_u16()')
result = int(pyb.exec('print(raw_adc)').decode('utf-8').strip())
pyb.exit_raw_repl()
print(result)
