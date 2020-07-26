from lib.pytrack import Pytrack
import machine
import time
import utime
import gc
import pycom
from network import Bluetooth, WLAN
import binascii
from config import ConfigBluetooth, ConfigMqtt, ConfigAccelerometer
from lib.mqtt import MQTTClient
from lib.LIS2HH12 import LIS2HH12



py = Pytrack()
accel = LIS2HH12()

def _decodeBytes(data):
    '''
    Attempts to decode a byte array to string format. If not a byte type,
    just returns the original data
    '''
    try:
        return data.decode()
    except (UnicodeDecodeError, AttributeError):
        pass
    return data
    
def testGPSLib1():
    from lib.L76GNSS import L76GNSS
    print("Testing GPS using pytrack L76GNSS library")
    L76 = L76GNSS(pytrack=py)

    while True:
        coord = L76.coordinates()
        print("Coordinates: {}, mem: {}".format(coord, gc.mem_free()))


def testGPSLib2():
    from lib.L76GNSV4 import L76GNSS
    print("Testing GPS using L75GNSV4 library")
    py = Pytrack()
    L76 = L76GNSS(pytrack=py)
    L76.setAlwaysOn()

    print("gsv - info about sattelites in view at this moment: ")
    # returns the info about sattelites in view at this moment
    # even without the gps being fixed
    print(L76.gps_message('GSV',debug=True))
    input("Press enter to continue")

    print("gga - number of sattelites in view at this moment: ")
    # returns the number of sattelites in view at this moment
    # even without the gps being fixed
    print(L76.gps_message('GGA',debug=True)['NumberOfSV'])
    input("Press enter to continue")

    print("Attempting to get gps fix... This may take some time...")

    L76.get_fix(debug=False)
    pycom.heartbeat(0)
    if L76.fixed():
        pycom.rgbled(0x000f00)
    else:
        pycom.rgbled(0x0f0000)
    print("coordinates")
    # returns the coordinates
    # with debug true you see the messages parsed by the
    # library until you get a the gps is fixed
    print(L76.coordinates(debug=False))
    print(L76.getUTCDateTime(debug=False))

    # example using the deepsleep mode of the pytrack
    print("Going to deep sleep for 60 seconds (powering down gps)")
    machine.idle()
    py.setup_sleep(60) # sleep 1 minute
    py.go_to_sleep(gps=True)


def scanBluetooth():
    bt = Bluetooth()
    bt.start_scan(-1) # Start scanning indefinitely until stop_scan() is called

    while True:
        adv = bt.get_adv()
        if adv:
            # try to get the complete name
            print("BT Name: {}".format(bt.resolve_adv_data(adv.data, Bluetooth.ADV_NAME_CMPL)))

            # print out mac address of bluetooth device
            print("Mac addr: {}, {}".format(adv.mac, binascii.hexlify(adv.mac)))

        else:
            time.sleep(0.5)
        
        time.sleep(3)

def isBTDeviceNearby():
    bt = Bluetooth()

    while True:
        print("Scanning for owner BT device nearby...")
        bt.start_scan(10)  # Scans for 10 seconds

        while bt.isscanning():
            adv = bt.get_adv()
            if adv and binascii.hexlify(adv.mac) == ConfigBluetooth.MAC_ADDR:
                try:
                    print("Owner device found: {} Mac addr {}".format(bt.resolve_adv_data(adv.data, Bluetooth.ADV_NAME_CMPL), ConfigBluetooth.MAC_ADDR))
                    conn = bt.connect(adv.mac)
                    time.sleep(0.05)
                    conn.disconnect()
                    bt.stop_scan()
                except Exception as e:
                    print("Exception {}".format(e))
                    bt.stop_scan()
                    break
            else:
                time.sleep(0.050)


def testRTC():
    time.sleep(2)
    rtc = machine.RTC()
    print('Current RTC: {}, is synced: {}', rtc.now(), rtc.synced())
    rtc.ntp_sync("pool.ntp.org")
    utime.sleep_ms(750)
    print('Synced time: {}', rtc.now())
    # print('Going to sleep')
    # time.sleep(1);
    # machine.idle()
    # py.setup_sleep(10) # sleep 10 seconds
    # py.go_to_sleep()

def testMQTT():
    mqttClient = None
    mqttClient = MQTTClient(ConfigMqtt.CLIENT_ID, ConfigMqtt.SERVER, port=ConfigMqtt.PORT, user=ConfigMqtt.USER, password=ConfigMqtt.PASSWORD)
    # Set the callback method that will be invoked on subscription to topics
    mqttClient.set_callback(mqttCallback)
    mqttClient.connect()

    #Subscribe to the disable tracking topic
    mqttClient.subscribe(topic=ConfigMqtt.TOPIC_TRACKING_STATE)
    time.sleep(0.5)
    print("Checking MQTT messages")

    mqttClient.check_msg()

    print("Messages checked. Going to sleep")
    time.sleep(15)


def mqttCallback(topic, msg):
    '''
    Method to handle callbacks of any mqtt topics that we subscribe to.
    For now, only subscribes to bypass topic which is used to disable gps monitoring and accelerometer wakeup detection.
    topic - MQTT topic that we are subscribing to and processing the request for 
    msg - Message received from the topic
    '''
    print("In MQTT subscription callback")

    # Attempt to decode the topic and msg if in byte format
    topic = _decodeBytes(topic)
    msg = _decodeBytes(msg)

    print("{}: {}".format(topic, msg))

def testCurrentDraw():
    pycom.heartbeat(False)
    for i in range(10):
        pycom.rgbled(0x00FF00) #green
        time.sleep(1)
        pycom.rgbled(0x000000)
        time.sleep(1)
    
    # Test deepsleep for 10 seconds with accelerometer wakeup
    py.setup_int_wake_up(True, True)
    accel.enable_activity_interrupt(
                ConfigAccelerometer.INTERRUPT_THRESHOLD, ConfigAccelerometer.INTERRUPT_DURATION)
    py.setup_sleep(10)
    py.go_to_sleep()

# Ensure we are connected to network
# Check if network is connected. If not, attempt to connect
counter = 0
wlan = WLAN()
while not wlan.isconnected():
    # If we surpass some counter timeout and network is still not connected, reset and attempt to connect again
    if counter > 100000:
        machine.reset()
    machine.idle()
    counter += 1


#isBTDeviceNearby()
testCurrentDraw()