# main.py
# Main set of functions for the controller
# author: callen
#

import time
import machine
import pycom
from mqtt import MQTTClient
from network import WLAN
from config import ConfigMqtt, ConfigAccelerometer, ConfigGPS
from pycoproc import WAKE_REASON_ACCELEROMETER
from LIS2HH12 import LIS2HH12
from L76GNSS import L76GNSS
from pytrack import Pytrack

# Declare global variables and instantiate various modules
py = Pytrack()
accel = LIS2HH12()
wlan = WLAN() #TODO Change to LTE


# Initialize local variables used within the script. Checks for network connectivity. If not able to connect after
# a timeout, resets the machine in order to try and conenct again. Also initializes MQTTClient
# Return: Object with the initialized variable properties
# {
#   'mqttClient': initializedMqttClientInstance
# }
def init(mqttClient):
     # Check if network is connected. If not, attempt to connect
    counter = 0
    while not wlan.isconnected():
        # If we surpass some counter timeout and network is still not connected, reset and attempt to connect again
        if counter > 100000:
            machine.reset()
        machine.idle()
        counter += 1

    # Initialize mqttClient
    mqttClient = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, ConfigMqtt.PORT, ConfigMqtt.USER, ConfigMqtt.PASSWORD)
    mqttClient.connect()
    return {
        "mqttClient": mqttClient
    }

def sendMQTTMessage(topic, msg, mqttClient=None):
    try:
        if mqttClient is None:
            # Instantiate a new MQTTClient
            mqttClient = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, ConfigMqtt.PORT, ConfigMqtt.USER, ConfigMqtt.PASSWORD)
            mqttClient.connect()

        # Publish the message to the topic
        mqttClient.publish(topic, msg)

    except:
        # On exception, the client may have been initialized but connected. Try to connect one more time then exit
        try:
            # Instantiate a new MQTTClient
            mqttClient = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, ConfigMqtt.PORT, ConfigMqtt.USER, ConfigMqtt.PASSWORD)
            mqttClient.connect()

            # Send the message topic
            mqttClient.publish(topic, msg)
        except:
            print("Exception occurred attempting to connect to MQTT server")


def sleepWithInterrupt(mqttClient=None):
    # Enable wakeup source from INT pin
    py.setup_int_pin_wake_up(False)

    # Enable activity and inactivity interrupts with acceleration threshold and min duration
    py.setup_int_wake_up(True, True)
    accel.enable_activity_interrupt(
        ConfigAccelerometer.INTERRUPT_THRESHOLD, ConfigAccelerometer.INTERRUPT_DURATION)

    # If mqttClient is defined, disconnect
    if mqttClient is not None:
        try:
            mqttClient.disconnect()
        except:
            print("Exception occurred disconnecting from mqtt client")

    # Go to sleep for specified amount of time if no accelerometer wakeup
    #TODO config sleep time
    time.sleep(0.1)
    py.setup_sleep(60)
    py.go_to_sleep()


def monitorLocation(bWithMotion=True, mqttClient=None):
    # Sends GPS location to Mqtt topic. Continues sending data as long as motion is detected
    # Params:
    #   bWithMotion - If true, continues to monitor and send GPS location to topic as long as 
    #                 accelerometer activity is detected. If false, only publishes location once
    print("Monitoring Location")
    gps = L76GNSS(py)
    while True:
        coordinates = gps.coordinates(debug=True)
        print(coordinates)



def accelInMotion(numReads=5):
    # Takes numReads measurements of accelerometer data to detect if there is motion.
    # Returns true if delta sensor data is above a threshold (meaning there is active motion), flase otherwise

    xyzList = list()
    xyzList.append(accel.acceleration())
    for index in range(0, numReads):
        # Print change from last reading
        time.sleep(0.5)
        xyzList.append(accel.acceleration())
        deltas = list(map(lambda b, a: abs(b - a), xyzList[-1], xyzList[-2]))  # Get last element (with -1) and subtract previous element (-2)
        # If max delta is greater than threshold, return true
        if max(deltas) >= ConfigAccelerometer.MOTION_CHECK_MIN_THRESHOLD:
            return True

    # Get the largest change in x, y, and z and see if that surpasses the threshold
    minVals = list()
    maxVals = list()
    for i in range(3):
        minVals.append(min(map(lambda a, i=i: a[i], xyzList)))
        maxVals.append(max(map(lambda a, i=i: a[i], xyzList)))

    # Get the maximum delta for x, y, z for all logged points
    deltas = list(map(lambda b, a: b - a, maxVals, minVals))
    # If any x, y, or z axis in deltas array have a total delta change past the allowed threshold, return true. Otherwise return false
    return max(deltas) >= ConfigAccelerometer.MOTION_CHECK_MIN_THRESHOLD


def accelWakeup(mqttClient=None):
    # Logic to handle board wakeup interruption due to accelerometer.
    # Sends mqtt messages for wakeup if client is defined
    print("Accelerometer wakeup")

    # Check the accelerometer is still active (preventing false negatives for alerting of theft)
    # If we dont ready any new accelerometer motion, exit this function and dont send any accelerometer wakeup or gps msgs
    if not accelInMotion():
        return

    # Not a false wakeup, so send a message to the initial accelerometer wakeup topic
    sendMQTTMessage(ConfigMqtt.TOPIC_ACCEL_WAKEUP, "1", mqttClient)

    # Send GPS updates while there has been continued motion for some time
    monitorLocation(True, mqttClient)


def main():
    mqttClient = None
    pycom.heartbeat(False)
    params = init(mqttClient)
    mqttClient = params["mqttClient"]
    time.sleep(2)

    # Send mqtt message for heartbeat to let server know we are still connected and alive
    sendMQTTMessage(ConfigMqtt.TOPIC_HEARTBEAT, "1", mqttClient)

    if py.get_wake_reason() == WAKE_REASON_ACCELEROMETER:
        # Wakeup was triggered by accelerometer interrupt
        pycom.rgbled(0xFF0000) #red
        # Call accelerometer wakeup method to invoke GPS tracking and continuous location updates to mqtt server
        accelWakeup(mqttClient)
    else:
        # Wakeup call was not triggered from accelerometer interrupt, rather the timer just running out
        pycom.rgbled(0x7f7f00) #yellow

    time.sleep(5)

    sleepWithInterrupt(mqttClient)


# Run the main function implementation
#main()

monitorLocation()
