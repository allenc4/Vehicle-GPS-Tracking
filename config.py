# Basic configuration class defining static properties used throughout the project
# author: callen
#

import config_auth

_DEVICE_ID = "ChrisGpyMTrack001"

class ConfigNetwork:
    KNOWN_NETWORKS = {
        #config param - IP, Subnet, Gateway, DNS
        'FiOS-DJ8NN': {'pwd': config_auth.NETWORK_1_PASS, 'config': ('192.168.1.185', '255.255.255.0', '192.168.1.1', '192.168.1.1')}
    }

class ConfigMqtt:
    CLIENT_ID = _DEVICE_ID
    SERVER = config_auth.MQTT_SERVER
    PORT = 1883
    USER = config_auth.MQTT_USER
    PASSWORD = config_auth.MQTT_PASSWORD

    TOPIC_HEARTBEAT = "/motorcycle/heartbeat"
    TOPIC_GPS = "/motorcycle/gps"
