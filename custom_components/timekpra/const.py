"""Constants for the Timekpra integration."""

DOMAIN = "timekpra"

CONF_SSH_HOST = "ssh_host"
CONF_SSH_PORT = "ssh_port"
CONF_SSH_USER = "ssh_user"
CONF_SSH_PASSWORD = "ssh_password"
CONF_TARGET_USER = "target_user"
CONF_ADMIN_USER = "admin_user"
CONF_ADMIN_PASSWORD = "admin_password"

SCAN_INTERVAL_SECONDS = 300

DAYS = [
    {"key": "monday", "name": "Lundi", "number": 1},
    {"key": "tuesday", "name": "Mardi", "number": 2},
    {"key": "wednesday", "name": "Mercredi", "number": 3},
    {"key": "thursday", "name": "Jeudi", "number": 4},
    {"key": "friday", "name": "Vendredi", "number": 5},
    {"key": "saturday", "name": "Samedi", "number": 6},
    {"key": "sunday", "name": "Dimanche", "number": 7},
]

LOCKOUT_TYPES = ["lock", "suspend", "shutdown"]
