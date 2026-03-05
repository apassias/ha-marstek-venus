DOMAIN = "marstek_venus"

CONF_DEVICES = "devices"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_WIFI_MAC = "wifi_mac"

CONF_SCAN_MODE = "scan_mode"
CONF_CIDR = "cidr"
CONF_POLL_INTERVAL = "poll_interval"
CONF_ENERGY_UNITS_PER_WH = "energy_units_per_wh"

DEFAULT_PORT = 30000
DEFAULT_POLL_INTERVAL = 60  # seconds
DEFAULT_ENERGY_UNITS_PER_WH = 10.0  # 10 units = 1 Wh (0.1Wh units)

PLATFORMS = ["sensor", "binary_sensor", "select"]

DATA_CLIENTS = "clients"
DATA_COORDINATORS = "coordinators"

SERVICE_SET_MODE = "set_mode"
SERVICE_SET_PASSIVE = "set_passive"
SERVICE_SET_MANUAL = "set_manual"

ATTR_DEVICE_ID = "device_id"
ATTR_MODE = "mode"
ATTR_POWER = "power"
ATTR_CD_TIME = "cd_time"
ATTR_SLOTS = "slots"
