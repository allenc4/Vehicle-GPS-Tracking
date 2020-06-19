from lib.pytrack import Pytrack
from lib.L76GNSV4 import L76GNSS
import machine, time
import pycom

def testGPS():
    print("up")
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

testGPS()
