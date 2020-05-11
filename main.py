# main.py
# Main set of functions for the controller
# author: callen
#

import time
import machine
import pycom
from mqtt import MQTTClient
from network import WLAN
from config import ConfigMqtt, ConfigAccelerometer
from pycoproc import WAKE_REASON_ACCELEROMETER, WAKE_REASON_TIMER


# From:https://github.com/pycom/pycom-libraries
from LIS2HH12 import LIS2HH12
from pytrack import Pytrack


py = Pytrack()
pycom.heartbeat(False)
time.sleep(2)

# Setup mqtt client
# mqtt = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, ConfigMqtt.PORT, user=ConfigMqtt.USER, password=ConfigMqtt.PASSWORD)
# mqtt.connect()

# while True:
#     print("Sending heartbeat")
#     mqtt.publish(ConfigMqtt.TOPIC_HEARTBEAT, msg="1")
#     time.sleep(10)

if py.get_wake_reason() == WAKE_REASON_ACCELEROMETER:
    pycom.rgbled(0xFF0000) #red
else:
    pycom.rgbled(0x7f7f00) #yellow
time.sleep(5)

# Enable wakeup source from INT pin
py.setup_int_pin_wake_up(False)
# Instantiate accelerometer
acc = LIS2HH12()

# Enable activity and inactivity interrupts with acceleration threshold and min duration
py.setup_int_wake_up(True, True)
acc.enable_activity_interrupt(ConfigAccelerometer.INTERRUPT_THRESHOLD, ConfigAccelerometer.INTERRUPT_DURATION)

# Go to sleep 1 minutes max if no accelerometer interrupt happens
py.setup_sleep(60)
py.go_to_sleep()
