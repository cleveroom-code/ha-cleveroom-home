DOMAIN = "cleveroom"
# 配置项
CONF_GATEWAY_ID = "gateway_id"
CONF_GATEWAY_TYPE = "gateway_type"
CONF_DISCOVERED_DEVICES = "discovered_devices"
CONF_SYSTEM_LEVEL = "system_level"
CONF_AUTO_CREATE_AREA = "auto_create_area"
CONF_SECURE_CODE = "secure_code"
# gateway.py work mode
GATEWAY_TYPE_SERVER = 0
GATEWAY_TYPE_CLIENT = 1

GATEWAY_TYPES = {
    GATEWAY_TYPE_CLIENT: "Client Mode",
    GATEWAY_TYPE_SERVER: "Server Mode",
}

MANUAL_CREATE_AREA = 0
AUTO_CREATE_AREA = 1
CREATE_AREA_OPTIONS = {
    AUTO_CREATE_AREA: "Yes",
    MANUAL_CREATE_AREA: "No",
}

SYSTEM_LEVEL_OPTIONS = {
    0: "≤50 ",
    1: "≤100 ",
    2: "≤200 ",
    3: ">200 ",
}

# default port
DEFAULT_PORT = 4196
DEFAULT_SCAN_INTERVAL = 30

CLIENTS_REGISTRY = {}
GATEWAY_ID_TO_ENTRY_ID = {}