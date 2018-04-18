import RPi.GPIO as GPIO
import time

class GpioCtr(object):
    def __init__(self):
        super(GpioCtr, self).__init__()
        pin_4GPower = 11
        pin_LockPower = 15
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(pin_4GPower, GPIO.OUT)
        GPIO.setup(pin_LockPower, GPIO.OUT)

    def LockPowerOn(self):
        GPIO.output(15, False)

    def LockPowerOff(self):
        GPIO.output(15, True)

    def Route4GReboot(self):
        GPIO.output(11, True)
        time.sleep(3)
        GPIO.output(11, False)