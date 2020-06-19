# boot file for the gpy. Runs once on startup before executing main.py.
# Functionality here initializes WiFi network with known network if found.
# Otherwise, sets wifi in Access Point mode
# author: callen
#

import os
import machine
from config import ConfigNetwork

uart = machine.UART(0, baudrate=115200)
os.dupterm(uart)

if machine.reset_cause() != machine.SOFT_RESET:
    from network import WLAN
    wl = WLAN()
    wl.mode(WLAN.STA)
    def_ssid = 'chris-gpy'
    def_auth = (WLAN.WPA2, 'micropython')

    print("Scanning for known wifi networks")
    available_networks = wl.scan()
    networks = frozenset([e.ssid for e in available_networks])

    known_network_names = frozenset([key for key in ConfigNetwork.KNOWN_NETWORKS])
    network_to_use = list(networks & known_network_names)

    try:
        network_to_use = network_to_use[0]
        network_props = ConfigNetwork.KNOWN_NETWORKS[network_to_use]
        pwd = network_props['pwd']
        sec = [e.sec for e in available_networks if e.ssid == network_to_use][0]
        if 'config' in network_props:
            wl.ifconfig(config=network_props['config'])
        wl.connect(network_to_use, (sec, pwd), timeout=10000)
        while not wl.isconnected():
            machine.idle()  # save power while waiting for connection to succeed
        print("Connected to " + network_to_use + " with IP address: " + wl.ifconfig()[0])

    except Exception as e:
        print("Failed to connect to any known network... Exception: {}".format(e))
        print("Going into AP mode")

        print("Setting with default ssid: {0} and default auth {1}".format(def_ssid, def_auth))
        wl.init(mode=WLAN.AP, ssid=def_ssid, auth=def_auth, channel=6, antenna=WLAN.INT_ANT, hidden=False)

#TODO For now going to tests module. Remove this
machine.main('tests.py')