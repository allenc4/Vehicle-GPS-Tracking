# main.py
# Main set of functions for the controller
# author: callen
#

import time
import machine
import pycom
from lib.mqtt import MQTTClient
from network import WLAN
from config import ConfigMqtt, ConfigAccelerometer, ConfigGPS
from lib.pycoproc import WAKE_REASON_ACCELEROMETER
from lib.LIS2HH12 import LIS2HH12
#from L76GNSS import L76GNSS
from lib.L76GNSV4 import L76GNSS
from lib.pytrack import Pytrack

class Tracker:
    def __init__(self, pytrack=None, debug=False):
        if pytrack is not None:
            self.pytrack = pytrack
        else:
            self.pytrack = Pytrack()

        self.debug = debug
        # Instantiate accelerometer
        self.accel = LIS2HH12()
        self.wlan = WLAN()  #TODO change to LTE
        self.gps = None
        self.mqtt = None
        self.continueGPSRead = False

    def init(self):
        '''
        Initialize local variables used within the script. Checks for network connectivity. If not able to connect after
        a timeout, resets the machine in order to try and conenct again. 
        Initializes MQTTClient and checks if we are in a continuous GPS read state after wakeup (saved to self instance variables)
        '''
        # Check if network is connected. If not, attempt to connect
        counter = 0
        while not self.wlan.isconnected():
            # If we surpass some counter timeout and network is still not connected, reset and attempt to connect again
            if counter > 100000:
                machine.reset()
            machine.idle()
            counter += 1

        # Initialize mqttClient
        self.mqttClient = _getMqttClient(self.debug)

        # Check to see if we are in continued gps read (went to sleep and want to continue reading GPS data)
        if self.pycom.nvs_get(ConfigGPS.SLEEP_CONTINUE_GPS_READ) == 1:
            self.continueGPSRead = True
        # Erase this key from NVS
        self.pycom.nvs_erase(ConfigGPS.SLEEP_CONTINUE_GPS_READ)

    @staticmethod
    def _getMqttClient(debug):
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
                if debug:
                    print("Exception occurred trying to initialize mqtt client")
                time.sleep(0.5)
        return mqttClient


    def sendMQTTMessage(self, topic, msg):
        '''
        Sends an MQTT message to the specified topic
        topic - Topic to send to
        msg - Message to send to topic
        mqttClient - MQTT Client used to send the message. If not defined, sends to default configured mqtt client in configuration
        '''
        debug = self.debug

        if self.mqttClient is None:
            try:
                # Instantiate a new MQTTClient
                self.mqttClient = _getMqttClient(debug)
            except:
                self.mqttClient = None
        
        try:
            if self.mqttClient is not None:
                # Send the message topic
                mqttClient.publish(topic, msg)
        except:
            if debug:
                print("Exception occurred attempting to connect to MQTT server")

    def isContinueGPSRead(self):
        '''
        Returns true or false - whether or not we are in a continued gps read state after power cycle / deep sleep.
        If true, we should jump right to gps read. False if we should execute normal wakeup flow
        '''
        return self.continueGPSRead

    def sleepWithInterrupt(self, sleepGps=True):
        '''
        Puts the py to deepsleep, enabling accelerometer and timer interrupt for wake. Puts GPS to sleep
        by default (unless changed in params). This puts device in lowest power consumption mode
        mqttClient - If defined, sends disconnect request
        '''
        # Enable wakeup source from INT pin
        self.pytrack.setup_int_pin_wake_up(False)

        # Enable activity and inactivity interrupts with acceleration threshold and min duration
        self.pytrack.setup_int_wake_up(True, True)
        self.accel.enable_activity_interrupt(
            ConfigAccelerometer.INTERRUPT_THRESHOLD, ConfigAccelerometer.INTERRUPT_DURATION)

        # If mqttClient is defined, disconnect
        if self.mqttClient is not None:
            try:
                self.mqttClient.disconnect()
            except:
                if self.debug:
                    print("Exception occurred disconnecting from mqtt client")

        # Go to sleep for specified amount of time if no accelerometer wakeup
        #TODO config sleep time
        time.sleep(0.1)
        self.pytrack.setup_sleep(60)
        self.pytrack.go_to_sleep(gps=sleepGps)


    def _getGpsFix(self):
        '''
        Attempts to lock on a signal to the gps.
        Returns true if signal is found, false otherwise
        '''
        input("Press any key to continue....")  #TODO - remove
        # Attempt to get the gps lock for X number of attempts (defined in config)
        maxTries = max(ConfigGPS.LOCK_FAIL_ATTEMPTS, 1)
        signalFixTries = maxTries
        while signalFixTries > 0:
            signalFixTries -= 1
            if self.debug:
                print("On GPS fix try number {} of {}".format(maxTries - signalFixTries, maxTries))
            self.gps.get_fix(debug=False)
            pycom.heartbeat(False)
            bIsFixed = False

            if self.gps.fixed():
                # Got the GPS fix, exit out of this while condition
                pycom.rgbled(0x000f00)
                bIsFixed = True
            else:
                # If couldnt get a signal fix, try again
                pycom.rgbled(0x0f0000)

        return bIsFixed


    def monitorLocation(self, bWithMotion=True):
        '''
        Sends GPS location to Mqtt topic. Continues sending data as long as motion is detected
        bWithMotion - If true, continues to monitor and send GPS location to topic as long as accelerometer activity is
            detected. If false, only publishes location once
        '''
        if self.debug:
            print("Monitoring Location")
        self.gps = L76GNSS(self.pytrack, timeout=ConfigGPS.LOCK_TIMEOUT, debug=False)
        self.gps.setAlwaysOn()

        if not self._getGpsFix(self.gps):
            # Couldnt get a signal so send message to topic for gps not available and exit (go back to sleep)
            if self.debug:
                print("Couldnt get a GPS signal after {} attempts".format(ConfigGPS.LOCK_FAIL_ATTEMPTS))
            self.sendMQTTMessage(ConfigMqtt.TOPIC_GPS_NOT_AVAILABLE, "-1")
            return

        # Otherwise we have a gps signal, so get the coordinates and send to topic
        coordinates = self.gps.coordinates()
        self.sendMQTTMessage(ConfigMqtt.TOPIC_GPS, coordinates)
        input("Press any key to continue monitoring location with motion....")  #TODO - remove

        # If we want to monitor with motion (send multiple gps coordinates as long as there is motion), start monitoring
        if bWithMotion & self.accelInMotion():
            # Go to sleep for a specified amount of time (keeping GPS alive) to conserve some battery
            # TODO - check if this is better than setPeriodicMode
            if debug:
                print("Putting gps in low power and going to sleep")
            #Save state to nvs (non volatile storage)
            pycom.nvs_set(ConfigGPS.SLEEP_CONTINUE_GPS_READ, 1)
            self.pytrack.setup_sleep(ConfigGPS.SLEEP_BETWEEN_READS)
            self.pytrack.go_to_sleep(gps=False)


    def accelInMotion(self, numReads=5):
        '''
        Takes numReads measurements of accelerometer data to detect if there is motion.
        numReads - Number of measurements to take to detect motion
        Returns true if delta sensor data is above a threshold (meaning there is active motion), false otherwise
        '''
        accel = self.accel
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


    def accelWakeup(self):
        '''
        Logic to handle board wakeup interruption due to accelerometer.
        Sends mqtt messages for wakeup if client is defined
        '''
        if self.debug:
            print("Accelerometer wakeup")

        # Check the accelerometer is still active (preventing false negatives for alerting of theft)
        # If we dont ready any new accelerometer motion, exit this function and dont send any accelerometer wakeup or gps msgs
        if not self.accelInMotion():
            return

        # Not a false wakeup, so send a message to the initial accelerometer wakeup topic
        self.sendMQTTMessage(ConfigMqtt.TOPIC_ACCEL_WAKEUP, "1")

        # Send GPS updates while there has been continued motion for some time
        self.monitorLocation(True)


def main(debug=False):
    pycom.heartbeat(False)
    py = Pytrack()
    
    #Initialize new instance of Tracker class and initialize
    tracker = Tracker(pytrack=py, debug=debug)
    tracker.init()
    time.sleep(2)

    try:
        # If continueGPS is true, dont send another heartbeat. Jump right to the continue monitoring method
        if tracker.isContinueGPSRead():
            tracker.monitorLocation(bWithMotion=True)
        else:
            # Send mqtt message for heartbeat to let server know we are still connected and alive
            tracker.sendMQTTMessage(ConfigMqtt.TOPIC_HEARTBEAT, "1")

            if py.get_wake_reason() == WAKE_REASON_ACCELEROMETER:
                # Wakeup was triggered by accelerometer interrupt
                pycom.rgbled(0xFF0000) #red
                # Call accelerometer wakeup method to invoke GPS tracking and continuous location updates to mqtt server
                tracker.accelWakeup()
            else:
                # Wakeup call was not triggered from accelerometer interrupt, rather the timer just running out
                pycom.rgbled(0x7f7f00) #yellow
        
    except Exception as e:
        if debug:
            print("Exception in main thread '{}'".format(e))

        # Attempt to send mqtt message with exception
        try :
            tracker.sendMQTTMessage(ConfigMqtt.TOPIC_EXCEPTION_ENCOUNTERED, e)
        except:
            if debug:
                print("Exception sending MQTT message on main exception encountered")

    time.sleep(5)

    # Go to deep sleep
    tracker.sleepWithInterrupt()



# Run the main function implementation

main(debug=True)

# Test GPS 
#monitorLocation()

#monitorAccel()

