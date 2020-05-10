# Motorcycle GPS Monitoring System

The goal of this project is to define a simple GPS tracking system for a vehicle (or really any asset median). The main motivation behind this was for reactive theft applications; triggering notifications of motion on a motorcycle and GPS coordinates for live feed of where the vehicle is in case of theft. Other appliations are mainly for proactive measures (chain locks, disc locks, motion and sensor alarms, etc). The aim here is to provide further peace of mind to provide instant notifications if movement is detected on the bike and coordinates pushed to the owner so they can attempt to recover in case the other proactive anti-theft devices were bypassed.

## Getting Started

This specific implementation is based off of the Pycom Gpy and Pytrack microcontrollers, and will need to be modified for other microcontroller interfaces. The core modules are implemented with MicroPython, so this should be easily tranferable to other micropython interfaced microcontrollers, with the specific libraries for GPS, LTE, Accelerometer, etc replaced with the proper implementations.

The main microcontroller board used in the GPy from Pycom, along with the PyTrack expansion shield for providing GPS, Accelerometer, and serial interface. 
The GPy can be found [here](https://pycom.io/product/gpy/) and the PyTrack [here](https://pycom.io/product/pytrack/)

### Prerequisites

The first step is to download and install Pymakr for Atom or Visual Studio Code IDEs. This makes interfacing with the board extremely simple and allows for fast development ( [Pycom Pymakr](https://docs.pycom.io/gettingstarted/installation/pymakr/) ). Follow the Getting Started guide to ensure board firmware is up to date and all drivers and extensions are installed.

An MQTT broker is required in order to push information around coordinates, heartbeat, battery info, etc to the client. I personally set up a [Mosquitto MQTT](https://mosquitto.org/) image from Docker. You can use any broker however.

The other external interface used is a Node-Red for defining the data flow and wiring together the logic. Similarly, I ran a docker image hosted on an external VPC for easy access. More information can be found on the [Node-Red site](https://nodered.org/#get-started)


If using Node-Red and Mosquitto, you can use a Docker Compose file defining the images for both. A sample can be seen below 
'''
version: '3'
services:
    ############### Node Red
    node-red:
        container_name: node-red
        image: nodered/node-red
        restart: always
        volumes:
            - "/home/chris/pycom/node-red:/data"
        ports:
            - "1880:1880"
    
    ############### Mosquitto MQTT
    mqtt:
        container_name: mqtt
        image: eclipse-mosquitto
        restart: always
        volumes:
            - "/home/chris/pycom/mosquitto/config:/mosquitto/config"
            - "/home/chris/pycom/mosquitto/data:/mosquitto/data"
            - "/home/chris/pycom/mosquitto/log:/mosquitto/log"
        ports:
            - "1883:1883"
            - "9001:9001"
'''


Moving on to the code, there was one file ommitted from the repository which is needed to define configuration details. Create a new file in the base work directory named config_auth.py. Here is where all of your personal credentials are stored for network connection, MQTT server, etc. Fill in the applicable constant variables matching your network and MQTT settings:
'''
########## config_auth.py:
########## Secret keys and authentication information for networks, mqtt servers, etc

#Network credentials
NETWORK_1_PASS = "XXXX"

#MQTT credentials
MQTT_SERVER = "XXXX"
MQTT_USER = "XXXX"
MQTT_PASSWORD = "XXXX"

'''

## Installing


## Functionality

Main functionality is to detect motorcycle movement using the onboard accelerometer. On acceleration detection past threshold, we trigger the first message to publish to the wakeup topic, then continuously send gps coordinates to the location topic. Once a message is sent to the wakeup topic, we need to have a way to send a notification directly to a smartphone, either app notification or text. This is WIP.

Once motion is detected (past a threshold) to wake up the accelerometer, we continuously log GPS data until we have stopped receiving accelerometer updates for a specified time period. On accelerometer wakeup, the idea is to check if the owner is riding by attempting to check for a known bluetooth network nearby. If bluetooth access point is found, we do not trigger a message to be sent to the wakeup topic (or have config option to disable/enable this) so we dont trigger any false alarms.

Additional functionality to check would be to send the battery life and maybe monitor some other motorcycle components or data logging the actual ride.

### Accelerometer

TODO

### GPS

TODO

### Bluetooth

TODO

### Monitoring

TODO


## Authors

* **Chris Allen** *


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
