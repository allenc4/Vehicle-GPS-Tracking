from lib.pytrack import Pytrack
import machine
import time
import utime
import gc
import pycom
from network import Bluetooth
import binascii
from config import ConfigBluetooth

py = Pytrack()

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



isBTDeviceNearby()
