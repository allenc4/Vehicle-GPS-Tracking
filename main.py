# main.py
# Main set of functions for the controller
# author: callen
#

import time
import utime
import machine
import pycom
import binascii
from lib.mqtt import MQTTClient
from network import LTE, Bluetooth
from config import ConfigMqtt, ConfigAccelerometer, ConfigGPS, ConfigWakeup, ConfigBluetooth
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
        # Instantiate and hold state for sensors (accelerometer, lte, gps, etc)
        self.accel = LIS2HH12()
        self.lte = LTE()
        self.gps = None
        # Holds the mqtt client to send messages to
        self.mqttClient = None
        # If after wakeup, we are in continuous GPS logging state
        self.continueGPSRead = False
        # Flag for handling wakeup and logging logic differently if owner is nearby
        self.checkOwnerNearby = True

    def init(self, bInitLTE=False):
        '''
        Initialize local variables used within the script. Checks for network connectivity. If not able to connect after
        a timeout, resets the machine in order to try and conenct again. 
        Initializes MQTTClient and checks if we are in a continuous GPS read state after wakeup (saved to self instance variables)
        '''
        # Check if network is connected. If not, attempt to connect
        if bInitLTE:
            self.initLTE()

        # Initialize mqttClient
        self.mqttClient = self._getMqttClient(self.debug)

        # Check to see if we are in continued gps read (went to sleep and want to continue reading GPS data)
        if self._getNVS(ConfigGPS.NVS_SLEEP_CONTINUE_GPS_READ) is not None:
            self.continueGPSRead = True
            # Erase this key from NVS
            pycom.nvs_erase(ConfigGPS.NVS_SLEEP_CONTINUE_GPS_READ)

    @staticmethod
    def _getRTC():
        '''
        Syncs the real time clock with latest time and returns RTC instance
        '''
        rtc = machine.RTC()
        if not rtc.synced():
            # Sync real time clock
            rtc.ntp_sync("pool.ntp.org")
        return rtc


    @staticmethod
    def _getNVS(key):
        '''
        Looks up at the non volatile storage for a specified key. If it exists, returns the value stored
        for that key. Otherwise, returns None
        '''
        try:
            if pycom.nvs_get(key) is not None:
                return pycom.nvs_get(key)
        except Exception:
            # Do nothing, key doesnt exist
            pass
        return None


    @staticmethod
    def _getMqttClient(debug):
        # Initialize mqttClient
        state = False
        count = 0
        mqttClient = None

        while not state and count < 5:
            try:
                count += 1
                mqttClient = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, port=ConfigMqtt.PORT, user=ConfigMqtt.USER, password=ConfigMqtt.PASSWORD)
                mqttClient.connect()
                state = True
            except Exception as e:
                if debug:
                    print("Exception on initialize mqtt client: {}".format(e))
                time.sleep(0.5)
        return mqttClient

    def initLTE(self):
        '''
        If already used, the lte device will have an active connection.
        If not, need to set up a new connection.
        '''
        lte = self.lte
        debug = self.debug

        if lte.isconnected():
            return

        # Modem does not connect successfully without first being reset.
        if debug:
            print("Resetting LTE modem ... ", end='')
        lte.send_at_cmd('AT^RESET')
        if debug:
            print("OK")
        time.sleep(5)
        lte.send_at_cmd('AT+CFUN=0')
        time.sleep(5)

        #send_at_cmd_pretty('AT!="fsm"')
        # While the configuration of the CGDCONT register survives resets,
        # the other configurations don't. So just set them all up every time.
        if debug:
            print("Configuring LTE ", end='')
        lte.send_at_cmd('AT!="clearscanconfig"')

        if debug:
            print(".", end='')
        lte.send_at_cmd('AT!="RRC::addScanBand band=26"')

        if debug:
            print(".", end='')
        lte.send_at_cmd('AT!="RRC::addScanBand band=18"')

        if debug:
            print(".", end='')
        lte.send_at_cmd('AT+CGDCONT=1,"IP","soracom.io"')

        if debug:
            print(".", end='')
        lte.send_at_cmd('AT+CGAUTH=1,1,"sora","sora"')
        print(".", end='')

        if debug:
            lte.send_at_cmd('AT+CFUN=1')
        print(" OK")

        # If correctly configured for carrier network, attach() should succeed.
        if not lte.isattached():
            if debug:
                print("Attaching to LTE network ", end='')
            lte.attach()

            while True:
                if lte.isattached():
                    #send_at_cmd_pretty('AT+COPS?')
                    time.sleep(5)
                    break

                if debug:
                    print('.', end='')
                    pycom.rgbled(0x0f0000)
                time.sleep(0.5)
                if debug:
                    pycom.rgbled(0x000000)
                time.sleep(1.5)

        # Once attached, connect() should succeed.
        if not lte.isconnected():
            if debug:
                print("Connecting on LTE network ", end='')
            lte.connect()
            while True:
                if lte.isconnected():
                    break
                if debug:
                    print('.', end='')
                time.sleep(1)

        # Once connect() succeeds, any call requiring Internet access will
        # use the active LTE connection.
        self.lte = lte

    def isContinueGPSRead(self):
        '''
        Returns true or false - whether or not we are in a continued gps read state after power cycle / deep sleep.
        If true, we should jump right to gps read. False if we should execute normal wakeup flow
        '''
        return self.continueGPSRead

    def getWakeReason(self):
        '''
        Returns the reason why the device was woken up.
        Return values are from the ConfigWakeup scope
        '''
        if self.continueGPSRead:
            return ConfigWakeup.WAKE_CONTINUE_GPS
        elif self.pytrack.get_wake_reason() == WAKE_REASON_ACCELEROMETER:
            return ConfigWakeup.WAKE_REASON_ACCELEROMATER
        else:
            return ConfigWakeup.WAKE_REASON_TIMEOUT


    def setCheckOwnerNearby(self, bOwnerNearby=True):
        '''
        If bOnwerNearby is set to true (defaults to true here and constructor instantiation), we handle
        logic for wakup and actively logging location and pushing mqtt messages differently.
        If checkowner flag is true and owner is detected nearby on device wakeup, we are much less active
        in wakeups and monitoring
        '''
        self.checkOwnerNearby = bOwnerNearby

    def isOwnerNearby(self):
        '''
        Logic here checks if a known BLE device is broadcasting nearby.
        If they are, return true. Else, return false
        '''
        bt = Bluetooth()
        bt.start_scan(ConfigBluetooth.SCAN_ALLOW_TIME)  # Scans for 10 seconds

        while bt.isscanning():
            adv = bt.get_adv()
            if adv and binascii.hexlify(adv.mac) == ConfigBluetooth.MAC_ADDR:
                try:
                    if self.debug:
                        print("Owner device found: {} Mac addr {}".format(bt.resolve_adv_data(adv.data, Bluetooth.ADV_NAME_CMPL), ConfigBluetooth.MAC_ADDR))
                    conn = bt.connect(adv.mac)
                    time.sleep(0.05)
                    conn.disconnect()
                    bt.stop_scan()
                except Exception:
                    bt.stop_scan()

                return True

            time.sleep(0.050)

        return False

    def handleOwnerNearby(self):
        '''
        If owner is determined to be nearby, determines if owner is using vehicle.
        If so, puts device in deep sleep for specified amount of time, without acceleration wakeup
        '''
        # Get last time we wokeup when owner was nearby
        lastOwnerWakupTime = self._getNVS(ConfigWakeup.NVS_OWNER_WAKEUP_LAST_TIME)
        self._getRTC()
        curTime = utime.time()
        # Compare current time with last owner wakeup time
        if lastOwnerWakupTime is not None and (curTime - lastOwnerWakupTime <= ConfigWakeup.MULTIPLE_OWNER_WAKEUP_THRESHOLD):
            # Current time and last time we wokeup with owner nearby was less than 2 minutes apart.
            # Go to deep sleep for specified amount of time without accelerometer wakeup
            self.pytrack.setup_sleep(ConfigWakeup.SLEEP_TIME_OWNER_NEARBY)
            self.pytrack.go_to_sleep()

        # Otherwise if we arent going to sleep, update time in NVS 
        pycom.nvs_set(ConfigWakeup.NVS_OWNER_WAKEUP_LAST_TIME, curTime)

    def mqttCallback(self):
        '''
        Method to handle callbacks of any mqtt topics that we subscribe to.
        For now, only subscribes to bypass topic which is used to disable gps monitoring and accelerometer wakeup detection.
        '''
        # Setup a subscription to mqtt topic to check for retained bypass messages

        return False

    def sendMQTTMessage(self, topic, msg):
        '''
        Sends an MQTT message to the specified topic
        topic - Topic to send to
        msg - Message to send to topic
        mqttClient - MQTT Client used to send the message. If not defined, sends to default configured mqtt client in configuration
        '''
        debug = self.debug

        # If LTE is not setup, initialize it so we can send messages
        self.initLTE()

        if self.mqttClient is None:
            try:
                # Instantiate a new MQTTClient
                self.mqttClient = self._getMqttClient(debug)
            except:
                self.mqttClient = None

        try:
            if self.mqttClient is not None:
                # Send the message topic
                self.mqttClient.publish(topic=topic, msg=msg)
        except:
            if debug:
                print("Exception occurred attempting to connect to MQTT server")


    def goToSleep(self, sleepTime=60, bWithInterrupt=False, bSleepGps=True):
        '''
        Puts the py to deepsleep, turning off lte in order to reduce battery consumption.
        By default, sleeps for 60 seconds and powers down gps.
        sleepTime - specifies the time (in seconds) to put the device in deep sleep before waking up
        bWithInterrupt - if True, will wakeup for both timer timeout as well as acceleration interrupt
        bSleepGps - If True, puts the gps in deepsleep state as well (will take longer to reinitialize and refix gps signal)
        '''
        # Enable wakeup source from INT pin
        self.pytrack.setup_int_pin_wake_up(False)

        # Enable activity and inactivity interrupts with acceleration threshold and min duration
        if bWithInterrupt:
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

        # Disconnect lte
        if self.lte is not None and self.lte.isconnected():
            try:
                self.lte.disconnect()
                time.sleep(1)
                self.lte.dettach()
            except:
                if self.debug:
                    print("Exception disconnecting from lte")

        # Go to sleep for specified amount of time if no accelerometer wakeup
        time.sleep(0.1)
        self.pytrack.setup_sleep(sleepTime)
        self.pytrack.go_to_sleep(gps=bSleepGps)


    def _getGpsFix(self):
        '''
        Attempts to lock on a signal to the gps.
        Returns true if signal is found, false otherwise
        '''
        # Attempt to get the gps lock for X number of attempts (defined in config)
        maxTries = max(ConfigGPS.LOCK_FAIL_ATTEMPTS, 1)
        signalFixTries = maxTries
        while signalFixTries > 0:
            signalFixTries -= 1
            if self.debug:
                print("On GPS fix try number {} of {}".format(maxTries - signalFixTries, maxTries))
            self.gps.get_fix(debug=True)
            pycom.heartbeat(False)
            bIsFixed = False

            if self.gps.fixed():
                # Got the GPS fix, exit out of this while condition
                if self.debug:
                    pycom.rgbled(0x000f00)
                bIsFixed = True
            else:
                # If couldnt get a signal fix, try again
                if self.debug:
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

        if not self._getGpsFix():
            # Couldnt get a signal so send message to topic for gps not available and exit (go back to sleep)
            if self.debug:
                print("Couldnt get a GPS signal after {} attempts".format(ConfigGPS.LOCK_FAIL_ATTEMPTS))
            self.sendMQTTMessage(ConfigMqtt.TOPIC_GPS_NOT_AVAILABLE, "-1")
            return

        # Otherwise we have a gps signal, so get the coordinates and send to topic
        coordinates = self.gps.coordinates()
        self.sendMQTTMessage(ConfigMqtt.TOPIC_GPS, coordinates)

        # Save current timestamp of log time
        self._getRTC()  # Syncs rtc
        pycom.nvs_set(ConfigGPS.NVS_LAST_LOCATION_LOG_TIME, utime.time())

        # If we want to monitor with motion (send multiple gps coordinates as long as there is motion), start monitoring
        if bWithMotion & self.accelInMotion():
            # Go to sleep for a specified amount of time (keeping GPS alive) to conserve some battery
            # TODO - check if this is better than setPeriodicMode
            if self.debug:
                print("Putting gps in low power and going to sleep")
            #Save state to nvs (non volatile storage)
            pycom.nvs_set(ConfigGPS.NVS_SLEEP_CONTINUE_GPS_READ, 1)
            self.goToSleep(sleepTime=ConfigGPS.SLEEP_BETWEEN_READS, bWithInterrupt=False, bSleepGps=False)


    def accelInMotion(self, numReads=10):
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
        if self.debug:
            print("Deltas accel motion {}".format(deltas))
        # If any x, y, or z axis in deltas array have a total delta change past the allowed threshold, return true. Otherwise return false
        return max(deltas) >= ConfigAccelerometer.MOTION_CHECK_MIN_THRESHOLD


    def logRegularCoordinates(self):
        '''
        On regular timed wakeups, we still log our location every so often. Check the last time the location was
        logged and if the time is greater than the surpassed time defined in config, log coordinates again
        '''
        lastLogTime = self._getNVS(ConfigGPS.NVS_LAST_LOCATION_LOG_TIME)
        self._getRTC()  # Updates RTC

        # Compare the last log time with current rtc to see if threshold has passed
        if (lastLogTime is None or (utime.time() - lastLogTime > ConfigGPS.LOCATION_LOG_INTERVAL)):
            # Need to update gps as time has elapsed since last log
            self.monitorLocation(bWithMotion=False)  # Only log once

    def accelWakeup(self):
        '''
        Logic to handle board wakeup interruption due to accelerometer.
        Sends mqtt messages for wakeup if client is defined.
        '''
        debug = self.debug
        if debug:
            print("Accelerometer wakeup")

        # Check if the owner is nearby (owner moving device). If so, handle differently
        if self.checkOwnerNearby and self.isOwnerNearby():
            # Owner is nearby. If last wake is with 2 minutes, we are most likely riding
            # so go to sleep for longer time without wakeup
            self.handleOwnerNearby()
        
        # Check the accelerometer is still active (preventing false negatives for alerting of theft)
        # If we dont ready any new accelerometer motion, exit this function and dont send any accelerometer wakeup or gps msgs
        if not self.accelInMotion():
            if debug:
                print("Not currently in motion, going back to sleep")
            return
        else:
            if debug:
                print("Motion detected after wakeup...")

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
        # Get the wakeup reason
        wakeReason = tracker.getWakeReason()

        # If continueGPS is true, dont send another heartbeat. Jump right to the continue monitoring service
        if wakeReason == ConfigWakeup.WAKE_CONTINUE_GPS:
            tracker.monitorLocation(bWithMotion=True)
        elif wakeReason == ConfigWakeup.WAKE_REASON_ACCELEROMATER:
            # Wakeup was triggered by accelerometer interrupt
            if debug:
                pycom.rgbled(0xFF0000) #red
            # Call accelerometer wakeup method to invoke GPS tracking and continuous location updates to mqtt server
            tracker.accelWakeup()
        else:
            # Wakeup call was not triggered from accelerometer interrupt, rather the timer just running out
            if debug:
                pycom.rgbled(0x7f7f00) #yellow
             # Send mqtt message for heartbeat to let server know we are still connected and alive
            tracker.sendMQTTMessage(ConfigMqtt.TOPIC_HEARTBEAT, "1")
            # Check if we need to log GPS coordinates again
            tracker.logRegularCoordinates()

    except Exception as e:
        if debug:
            print("Exception in main thread '{}'".format(e))

        # Attempt to send mqtt message with exception
        try:
            tracker.sendMQTTMessage(ConfigMqtt.TOPIC_EXCEPTION_ENCOUNTERED, e)
        except:
            if debug:
                print("Exception sending MQTT message on main exception encountered")

    time.sleep(5)

    # Go to deep sleep
    # TODO configure sleep time
    tracker.goToSleep(bWithInterrupt=True)



# Run the main function implementation
main(debug=True)
