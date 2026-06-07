# Timekpra - Parental Control for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant integration to manage [Timekpr-nExT](https://mjasnik.gitlab.io/timekpr-next/) (Linux parental control) remotely over SSH.

Control your children's screen time directly from your Home Assistant dashboard, even when their computer is turned off.

![Timekpra card](images/screenshot.png)

## Features

- **Predefined profiles**: switch between complete configurations in one click (School, Holidays, At grandparents'...) — instant change in the UI
- **Custom profiles**: create, edit, and delete your own profiles from the Lovelace card
- **Temporary override**: built-in profile to bypass all restrictions in one click
- **Daily limits**: adjustable per day (Mon-Sun), with +/- buttons directly in the card
- **Weekly / monthly limit**: in hours, showing "Unlimited" when disabled
- **Time range**: start and end hour of allowed access
- **Allowed days**: toggle per day of the week
- **Lockout type**: lock / suspend / shutdown (dropdown)
- **Idle time tracking**: on/off
- **Sensors**: time used today and this week
- **Status**: computer online / offline
- **Offline queue**: changes are queued if the computer is off and applied automatically when it comes back online (persistent across HA restarts)
- **Built-in Lovelace card**: custom card installed automatically with interactive controls

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Click **Integrations** > **⋮** (menu) > **Custom repositories**
3. Add the repository URL: `https://github.com/tienou/ha-timekpra`
4. Category: **Integration**
5. Install **Timekpra - Parental Control**
6. Restart Home Assistant

### Manual

Copy the `custom_components/timekpra/` folder into your Home Assistant's `config/custom_components/` directory, then restart.

## Configuration

### Prerequisites on the child's machine (Ubuntu / Linux)

- **Timekpr-nExT** installed (`sudo apt install timekpr-next`)
- **SSH** enabled (`sudo apt install openssh-server`)
- A user account with **sudo** access (e.g. `parents`)

> **Tip**: The SSH password is used automatically for `sudo` commands. No special sudoers configuration needed.

### Adding it in Home Assistant

1. **Settings** > **Devices & services** > **Add integration**
2. Search for **Timekpra**
3. Fill in:
   - **SSH Host**: IP of the child's machine (e.g. `192.168.1.50`)
   - **SSH Host (VPN)**: *(optional)* IP when the child is connected via VPN (e.g. `10.0.0.2`)
   - **SSH Port**: `22` (default)
   - **SSH Username**: account with sudo access (e.g. `parents`)
   - **SSH Password**: account password
   - **Timekpra user**: the child's login (e.g. `camille`)

### Editing the configuration

To change the SSH credentials after installation:
**Settings** > **Devices & services** > **Timekpra** > **Configure**

## Lovelace card

The card is installed automatically. To add it to a dashboard:

1. Dashboard > **Edit** > **Add card**
2. Search for **Timekpra** in the card list
3. The card shows all controls with **+/-** buttons to change values directly

### Card features

- **Profile selector**: dropdown to switch instantly between profiles
- **Profile management**: buttons to create, edit, and delete custom profiles
- **Daily limits**: ±15 min buttons per day, shows "Unlimited" at 1440 min
- **Weekly limit**: ±1h buttons, shows "Unlimited" at 168h
- **Monthly limit**: ±1h buttons, shows "Unlimited" at 744h
- **Time range**: ±1h buttons for start and end
- **Allowed days**: on/off toggles
- **Lockout type**: dropdown (lock/suspend/shutdown)
- **Real-time status**: online/offline + pending commands

## Created entities

| Type | Entities |
|------|----------|
| **Number** | Monday…Sunday limit, Weekly limit, Monthly limit, Start/End hour |
| **Switch** | Allowed day Monday…Sunday, Count idle time, Daily limits on/off, Weekly limit on/off, Monthly limit on/off, Temporary override |
| **Select** | Action when time runs out (lock/suspend/shutdown), Active profile |
| **Sensor** | Time used today, Time used this week, Computer (online/offline), Pending changes |

## How it works

- SSH connection via `asyncssh` with password authentication
- **VPN fallback**: if the local IP is unreachable and a VPN IP is configured, the connection is automatically attempted on the VPN IP
- Reads config from `/var/lib/timekpr/config/timekpr.{user}.conf`
- Writes via the `timekpra` CLI (e.g. `timekpra --settimelimits`)
- Refreshes every 5 minutes (configurable)
- Persistent command queue for when the target machine is offline

## License

MIT
