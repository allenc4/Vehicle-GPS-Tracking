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
#from L76GNSS import L76GNSS
from lib.L76GNSV4 import L76GNSS
from pytrack import Pytrack

# Declare global variables and instantiate various modules
py = Pytrack()
accel = LIS2HH12()
wlan = WLAN() #TODO Change to LTE
debug = True

def init():
    '''
    Initialize local variables used within the script. Checks for network connectivity. If not able to connect after
    a timeout, resets the machine in order to try and conenct again. Also initializes MQTTClient
    Return: Object with the initialized variable properties
    {
      'mqttClient': initializedMqttClientInstance
    }
    '''
     # Check if network is connected. If not, attempt to connect
    counter = 0
    while not wlan.isconnected():
        # If we surpass some counter timeout and network is still not connected, reset and attempt to connect again
        if counter > 100000:
            machine.reset()
        machine.idle()
        counter += 1

    # Initialize mqttClient
    mqttClient = _getMqttClient()

    return {
        "mqttClient": mqttClient
    }

def _getMqttClient():
    # Initialize mqttClient
    state = False
    count = 0
    mqttClient = None

    while not state and count < 5:
        try:
            import ussl
            count += 1
            mqttClient = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, port=ConfigMqtt.PORT, user=ConfigMqtt.USER, password=ConfigMqtt.PASSWORD)
            mqttClient.connect()
            state = True
        except Exception as e:
            printDebug("Exception occurred trying to initialize mqtt client")
            time.sleep(0.5)
    return mqttClient


def sendMQTTMessage(topic, msg, mqttClient=None):
    '''
    Sends an MQTT message to the specified topic
    topic - Topic to send to
    msg - Message to send to topic
    mqttClient - MQTT Client used to send the message. If not defined, sends to default configured mqtt client in configuration
    '''
    if mqttClient is None:
        # Instantiate a new MQTTClient
        mqttClient = _getMqttClient()

    try:
        # Instantiate a new MQTTClient
        mqttClient = _getMqttClient()

        # Send the message topic
        mqttClient.publish(topic, msg)
    except:
        printDebug("Exception occurred attempting to connect to MQTT server")


def sleepWithInterrupt(mqttClient=None):
    '''
    Puts the py to deepsleep, enabling accelerometer and timer interrupt for wake
    mqttClient - If defined, sends disconnect request
    '''
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


def _getGpsFix(gps):
    '''
    Attempts to lock on a signal to the gps.
    Returns true if signal is found, false otherwise
    '''
    input("Press any key to continue....")  #TODO - remove
    # Attempt to get the gps lock for X number of attempts (defined in config)
    signalFixTries = max(ConfigGPS.LOCK_FAIL_ATTEMPTS, 1)
    while signalFixTries > 0:
        signalFixTries -= 1
        gps.get_fix(debug=False)
        pycom.heartbeat(False)
        bIsFixed = False

        if gps.fixed():
            # Got the GPS fix, exit out of this while condition
            pycom.rgbled(0x000f00)
            bIsFixed = True
        else:
            # If couldnt get a signal fix, try again
            pycom.rgbled(0x0f0000)

    return bIsFixed


def monitorLocation(bWithMotion=True, mqttClient=None):
    '''
    Sends GPS location to Mqtt topic. Continues sending data as long as motion is detected
    bWithMotion - If true, continues to monitor and send GPS location to topic as long as accelerometer activity is
        detected. If false, only publishes location once
    mqttClient - MQTT Client to use to send messages to. If not defined, uses default client specified in config
    '''
    printDebug("Monitoring Location")
    gps = L76GNSS(py, debug=False)
    gps.setAlwaysOn()

    if not _getGpsFix(gps):
        # Couldnt get a signal so send message to topic for gps not available and exit (go back to sleep)
        printDebug("Couldnt get a GPS signal after {} attempts".format(ConfigGPS.LOCK_FAIL_ATTEMPTS))
        sendMQTTMessage(ConfigMqtt.TOPIC_GPS_NOT_AVAILABLE, "-1", mqttClient)
        return

    # Otherwise we have a gps signal, so get the coordinates and send to topic
    coordinates = gps.coordinates()
    sendMQTTMessage(ConfigMqtt.TOPIC_GPS, coordinates, mqttClient)
    input("Press any key to continue....")  #TODO - remove

    # If we want to monitor with motion (send multiple gps coordinates as long as there is motion), start monitoring
    while bWithMotion & accelInMotion():
        # Go to sleep for a specified amount of time (keeping GPS alive) to conserve some battery
        # TODO - check if this is better than setPeriodicMode
        printDebug("Putting gps in low power and going to sleep")
        py.setup_sleep(ConfigGPS.SLEEP_BETWEEN_READS)
        py.go_to_sleep(gps=False)


def accelInMotion(numReads=5):
    '''
    Takes numReads measurements of accelerometer data to detect if there is motion.
    numReads - Number of measurements to take to detect motion
    Returns true if delta sensor data is above a threshold (meaning there is active motion), false otherwise
    '''
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
    '''
    Logic to handle board wakeup interruption due to accelerometer.
    Sends mqtt messages for wakeup if client is defined
    '''

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
    pycom.heartbeat(False)
    params = init()
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


def printDebug(str):
    if debug:
        print(str)

# Run the main function implementation
#main()

# Test GPS 
#monitorLocation()
