"""Constants for the Timekpra integration."""

DOMAIN = "timekpra"

CONF_SSH_HOST = "ssh_host"
CONF_SSH_PORT = "ssh_port"
CONF_SSH_USER = "ssh_user"
CONF_SSH_PASSWORD = "ssh_password"
CONF_TARGET_USER = "target_user"

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

# Values that effectively mean "unlimited" in timekpr-next
UNLIMITED_DAILY = 1440     # 24h in minutes
UNLIMITED_WEEKLY = 168     # 7 * 24h
UNLIMITED_MONTHLY = 744    # 31 * 24h

# Defaults when re-enabling limits
DEFAULT_DAILY_LIMITS = [60, 60, 60, 60, 60, 120, 120]  # 1h lun-ven, 2h sam-dim
DEFAULT_WEEKLY_LIMIT = 9
DEFAULT_MONTHLY_LIMIT = 40
DEFAULT_NOTIFICATION_THRESHOLD = 15  # minutes avant verrouillage

# ── Profils prédéfinis ─────────────────────────────────────────────
PROFILE_CUSTOM = "Personnalisé"
PROFILE_OVERRIDE = "Déblocage temporaire"

DEFAULT_PROFILES = {
    "École": {
        "allowed_days": [1, 2, 3, 4, 5, 6, 7],
        "hour_start": 8,
        "hour_end": 20,
        "minute_start": 0,
        "minute_end": 30,
        "daily_limits": [90, 90, 120, 90, 90, 90, 180],
        "weekly_limit": 9,
        "monthly_limit": 40,
        "track_inactive": False,
        "lockout_type": "lock",
    },
    "Vacances": {
        "allowed_days": [1, 2, 3, 4, 5, 6, 7],
        "hour_start": 9,
        "hour_end": 21,
        "minute_start": 0,
        "minute_end": 0,
        "daily_limits": [150, 150, 150, 150, 150, 180, 180],
        "weekly_limit": 18,
        "monthly_limit": 80,
        "track_inactive": False,
        "lockout_type": "lock",
    },
    "Chez Papi Mamie": {
        "allowed_days": [1, 2, 3, 4, 5, 6, 7],
        "hour_start": 9,
        "hour_end": 20,
        "minute_start": 0,
        "minute_end": 0,
        "daily_limits": [120, 120, 120, 120, 120, 120, 120],
        "weekly_limit": 14,
        "monthly_limit": 60,
        "track_inactive": False,
        "lockout_type": "lock",
    },
}
