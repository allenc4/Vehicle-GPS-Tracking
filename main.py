# main.py
# Main set of functions for the controller
# author: callen
#

import time
import machine
from mqtt import MQTTClient
from network import WLAN
from config import ConfigMqtt


# From:https://github.com/pycom/pycom-libraries
from LIS2HH12 import LIS2HH12
from pytrack import Pytrack

py = Pytrack()
acc = LIS2HH12()
wlan = WLAN()

while False:
    pitch = acc.pitch()
    roll = acc.roll()
    print('{}, {}'.format(pitch, roll))
    time.sleep_ms(100)

#ensure the network is connected
counter = 0
while not wlan.isconnected():
    if (counter % 100 == 0):
        print("Waiting for Wlan connection {}".format(counter))
    if (counter >= 10000):
        print("Resetting device")
        machine.reset()
    counter += 1
    machine.idle()

client = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, ConfigMqtt.PORT, user=ConfigMqtt.USER, password=ConfigMqtt.PASSWORD)
client.connect()

while True:
    print("Sending heartbeat")
    client.publish(ConfigMqtt.TOPIC_HEARTBEAT, msg="1")
    time.sleep(10)
