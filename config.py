# Basic configuration class defining static properties used throughout the project
# author: callen
#

import config_auth

_DEVICE_ID = "ChrisGpyMTrack001"

# Configurations for network settings
class ConfigNetwork:
    # Wifi Networks
    KNOWN_NETWORKS = {
        #config param - IP, Subnet, Gateway, DNS
        'FiOS-DJ8NN': {'pwd': config_auth.NETWORK_1_PASS, 'config': ('192.168.1.185', '255.255.255.0', '192.168.1.1', '192.168.1.1')}
    }

# Configurations for MQTT Settings
class ConfigMqtt:
    # Client identifier
    CLIENT_ID = _DEVICE_ID
    # Server and port to connect MQTT to
    SERVER = config_auth.MQTT_SERVER
    PORT = 1883
    # User authentication for MQTT server
    USER = config_auth.MQTT_USER
    PASSWORD = config_auth.MQTT_PASSWORD

    # Topics to publish to
    TOPIC_HEARTBEAT = "/motorcycle/heartbeat"
    TOPIC_GPS = "/motorcycle/gps"

# Configurations for Accelerometer Settings
class ConfigAccelerometer:
    # Sets the threshold for triggering accelerometer wake up (WAKE_REASON_ACCELEROMETER)
    INTERRUPT_THRESHOLD = 750  # 750mG (0.75G)
    INTERRUPT_DURATION = 175  # 175 ms time
    