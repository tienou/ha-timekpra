"""Constants for the AdGuard Whitelist integration."""

DOMAIN = "adguard_whitelist"

CONF_ADGUARD_URL = "adguard_url"
CONF_ADGUARD_USER = "adguard_user"
CONF_ADGUARD_PASSWORD = "adguard_password"
CONF_CLIENT_IP = "client_ip"

# SSH Firefox (optionnel)
CONF_SSH_ENABLED = "ssh_enabled"
CONF_SSH_HOST = "ssh_host"
CONF_SSH_PORT = "ssh_port"
CONF_SSH_USER = "ssh_user"
CONF_SSH_PASSWORD = "ssh_password"

FIREFOX_POLICIES_PATH = "/usr/lib/firefox/distribution/policies.json"

SCAN_INTERVAL_SECONDS = 120

SERVICE_ADD_SITE = "add_site"
SERVICE_REMOVE_SITE = "remove_site"
SERVICE_ADD_BOOKMARK = "add_bookmark"

EDUCATIONAL_SITES: dict[str, str] = {
    "lumni.fr": "Éducation",
    "logicieleducatif.fr": "Éducation",
    "calculatice.ac-lille.fr": "Éducation",
    "khanacademy.org": "Éducation",
    "fr.khanacademy.org": "Éducation",
    "bescherelle.com": "Éducation",
    "scratch.mit.edu": "Programmation",
    "mathador.fr": "Éducation",
    "lalilo.com": "Éducation",
}

CDN_PATTERNS: list[str] = [
    "cdn.",
    "static.",
    "assets.",
    "cloudfront.net",
    "googleapis.com",
    "gstatic.com",
    "cloudflare.com",
    "jsdelivr.net",
    "unpkg.com",
    "kastatic.org",
    "s3.amazonaws.com",
]
