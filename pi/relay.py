import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)

while True:
    currentTime = time.localtime()
    if currentTime.tm_hour >= 7 and currentTime.tm_hour < 19:
        GPIO.output(17, 1)
    else:
        GPIO.output(17, 0)
    time.sleep(60)

GPIO.cleanup()
