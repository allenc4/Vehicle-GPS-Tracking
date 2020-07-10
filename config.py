# Basic configuration class defining static properties used throughout the project
# author: callen
#

import config_auth
import ussl

_DEVICE_ID = "ChrisGpyMTrack001"

# Configurations for network settings
class ConfigNetwork:
    # Wifi Networks
    KNOWN_NETWORKS = {
        #config param - IP, Subnet, Gateway, DNS
        'TP-LINK_89F7': {'pwd': config_auth.NETWORK_1_PASS, 'config': ('192.168.0.185', '255.255.255.0', '192.168.0.1', '192.168.0.1')},
        'Nuthouse': {'pwd': config_auth.NETWORK_2_PASS}
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
    # Sending heartbeat message to record timestamp (sent on both timer wakeup and accelerometer wakeup)
    TOPIC_HEARTBEAT = "/motorcycle/heartbeat"
    # Topic to handle initial accelerometer wakeup interruption
    TOPIC_ACCEL_WAKEUP = "/motorcycle/accelWakeup"
    # Topic to handle continuous accelerometer motion after initial accelerometer wakeup
    TOPIC_ACCEL_CONTINUOUS_MOTION = "/motorcycle/accelMotion"
    # Topic to send GPS coordinates 
    TOPIC_GPS = "/motorcycle/location"
    TOPIC_GPS_NOT_AVAILABLE = "/motorcycle/locationunavailable"
    # Topic to send error info to
    TOPIC_EXCEPTION_ENCOUNTERED = "/motorcycle/exception"
    # Topic to subscribe to for disabling the tracker
    TOPIC_DISABLE_TRACKING = "/motorcycle/disableMonitor"

# Configurations for Accelerometer Settings
class ConfigAccelerometer:
    # Sets the threshold for triggering accelerometer wake up (WAKE_REASON_ACCELEROMETER)
    INTERRUPT_THRESHOLD = 750  # 750mG (0.75G)
    INTERRUPT_DURATION = 1000  # Over 1000 ms time
    # MAX number of seconds to sleep before waking up (if not interrupted by accelerometer wake)
    SLEEP_TIME_SEC = 28800  # 8 HOURS
    MOTION_CHECK_MIN_THRESHOLD = 0.2  # Tilt acceleration change threshold to prevent false wakeups 

class ConfigGPS:
    # Sets the timeout for a GPS to get a lock on the location
    LOCK_TIMEOUT = 360  # 10 minutes
    # Defines max number of attempts of trying to get a GPS lock and failing before stopping to try GPS connection
    LOCK_FAIL_ATTEMPTS = 2  # Try at least 2 times to aquire a GPS signal before exiting
    SLEEP_BETWEEN_READS = 60  # If we are actively reading gps location, send every 60 seconds
    NVS_SLEEP_CONTINUE_GPS_READ = "sleepgpsread"  # Key to save to NVS for continuing to read GPS after deep sleep
    NVS_LAST_LOCATION_LOG_TIME = "locationlogts"  # Key to save to NVS the timestamp of the last time GPS coordinates were logged.
    LOCATION_LOG_INTERVAL = 86400  # Log location at least once a day (in seconds)

class ConfigWakeup:
    WAKE_REASON_ACCELEROMATER = 100
    WAKE_CONTINUE_GPS = 200
    WAKE_REASON_TIMEOUT = 300
    NVS_OWNER_WAKEUP_LAST_TIME = "ownerlastwakeupts"  # Key to save to NVS for the timestamp of the last time device was woken up with owner nearby
    MULTIPLE_OWNER_WAKEUP_THRESHOLD = 120  # 120 seconds 
    SLEEP_TIME_OWNER_NEARBY = 1200  # 20 minutes

class ConfigBluetooth:
    SCAN_ALLOW_TIME = 10  # Allow 10 seconds to scan to see if owner is nearby (bluetooth tracker)
    MAC_ADDR = config_auth.BLUETOOTH_MAC_ADDR
