"""Integration tests inside a real Home Assistant (optional).

Run with ``pytest-homeassistant-custom-component`` installed; skipped
otherwise. The SSH layer is replaced by a fake machine that records the
commands it receives.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

import asyncssh  # noqa: E402
import voluptuous as vol  # noqa: E402
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

import custom_components  # noqa: E402

# The plugin ships its own ``custom_components`` package: add this repo's
# folder to it so Home Assistant's loader finds the integration.
_REPO_CC = str(Path(__file__).resolve().parent.parent / "custom_components")
if _REPO_CC not in list(custom_components.__path__):
    custom_components.__path__.append(_REPO_CC)

DOMAIN = "timekpra"

CONF = """
[DOCUMENTATION]
[camille]
ALLOWED_HOURS_ALL = 8;9;10;11;12;13;14;15;16;17;18;19;20
ALLOWED_WEEKDAYS = 1;2;3;4;5;6;7
LIMITS_PER_WEEKDAYS = 5400;5400;5400;5400;5400;5400;5400
LIMIT_PER_WEEK = 604800
LIMIT_PER_MONTH = 2678400
TRACK_INACTIVE = False
LOCKOUT_TYPE = lock
"""

ENTRY_DATA = {
    "ssh_host": "192.168.8.50",
    "ssh_host_vpn": "",
    "ssh_port": 22,
    "ssh_user": "parents",
    "auth_method": "password",
    "ssh_password": "secret-pw",
    "sudo_password": "",
    "target_user": "camille",
}


class FakeSSH:
    """Fake machine: records setter calls, can be offline / refuse auth."""

    instances: list["FakeSSH"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.online = True
        self.auth_failed = False
        self.refuse_auth = False
        self.calls: list[tuple] = []
        self.host_key_saver = None
        self.spent = 1800  # 30 min used today
        self.left = 3600   # 1 h left
        FakeSSH.instances.append(self)

    def set_host_key(self, key):
        pass

    @asynccontextmanager
    async def session(self):
        if self.refuse_auth:
            self.auth_failed = True
        yield self.online and not self.refuse_auth

    def _check(self):
        if self.refuse_auth:
            self.auth_failed = True
            raise asyncssh.PermissionDenied("refused")
        if not self.online:
            raise OSError("unreachable")

    async def get_config(self, user):
        self._check()
        return {
            k.strip(): v.strip()
            for k, _, v in (line.partition("=") for line in CONF.splitlines())
            if _ and not k.startswith("[")
        }

    async def get_user_info(self, user):
        self._check()
        return {
            "TIME_SPENT_DAY": str(self.spent),
            "TIME_SPENT_WEEK": str(self.spent),
            "TIME_LEFT_DAY": str(self.left),
        }

    async def get_time_spent(self, user):
        return None

    def __getattr__(self, name):
        if not name.startswith("set_"):
            raise AttributeError(name)

        async def setter(*args):
            self._check()
            self.calls.append((name, *args[1:]))

        return setter


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def fake_ssh():
    FakeSSH.instances.clear()
    import custom_components.timekpra  # noqa: F401  (patch target must be loaded)

    with patch("custom_components.timekpra.TimekpraSSH", FakeSSH):
        yield FakeSSH


async def _setup(hass: HomeAssistant, entry_id: str = "e1") -> tuple[MockConfigEntry, FakeSSH]:
    entry = MockConfigEntry(
        domain=DOMAIN, data=dict(ENTRY_DATA), entry_id=entry_id,
        unique_id="timekpra_192.168.8.50_camille", title="Timekpra - camille",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, FakeSSH.instances[-1]


async def test_setup_reads_machine(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    coord = entry.runtime_data.coordinator
    assert coord.data["online"] is True
    assert coord.data["hour_end"] == 20 and coord.data["minute_end"] == 59
    assert coord.data["daily_limits"] == [90] * 7


async def test_override_end_gives_back_only_what_was_left(hass, fake_ssh):
    """Bug: ending the override sent '= today's limit' (whole day back)."""
    entry, ssh = await _setup(hass)
    coord = entry.runtime_data.coordinator
    await coord.async_apply_profile("override")
    await hass.async_block_till_done()
    assert ("set_time_left", "=", 86400) in ssh.calls
    # 10 more minutes used during the override.
    ssh.spent += 600
    await coord.async_refresh()
    ssh.calls.clear()
    await coord.async_apply_profile("custom")
    await hass.async_block_till_done()
    sent = [c for c in ssh.calls if c[0] == "set_time_left"]
    # 1 h left before - 10 min used = 50 min (all days allowed: value = left).
    assert sent == [("set_time_left", "=", 3000)]
    assert coord.data["daily_limits"] == [90] * 7


async def test_profile_after_override_also_restores_time(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    coord = entry.runtime_data.coordinator
    await coord.async_apply_profile("override")
    await hass.async_block_till_done()
    ssh.calls.clear()
    await coord.async_apply_profile("school")
    await hass.async_block_till_done()
    assert ("set_time_left", "=", 3600) in ssh.calls


async def test_offline_batch_queues_without_retry_and_counts(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    coord = entry.runtime_data.coordinator
    ssh.online = False
    await coord.async_apply_profile("school")
    await hass.async_block_till_done()
    assert coord.pending_count == 7
    # Pending sensor is live, not refreshed only every 5 minutes.
    pending = [
        s for s in hass.states.async_all("sensor") if s.entity_id.endswith("pending")
        or "attente" in s.entity_id or "pending" in (s.attributes.get("friendly_name") or "").lower()
    ]
    assert any(p.state == "7" for p in pending)
    ssh.online = True
    await coord.async_refresh()
    await hass.async_block_till_done()
    assert coord.pending_count == 0
    assert ("set_lockout_type", "lock") in ssh.calls


async def test_stale_time_left_dropped_next_day(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    coord = entry.runtime_data.coordinator
    ssh.online = False
    await coord.async_apply("set_time_left", "=", 1200)
    assert coord.pending_count == 1
    coord._pending_day["set_time_left"] = "2000-01-01"
    ssh.online = True
    await coord.async_refresh()
    assert coord.pending_count == 0
    assert not [c for c in ssh.calls if c[0] == "set_time_left"]


async def test_manual_change_leaves_profile(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    coord = entry.runtime_data.coordinator
    await coord.async_apply_profile("school")
    await hass.async_block_till_done()
    assert coord.active_profile == "school"
    number = next(
        s.entity_id for s in hass.states.async_all("number")
        if s.entity_id.endswith("_lundi") or s.entity_id.endswith("_monday")
        or "monday" in s.entity_id or "lundi" in s.entity_id
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": 180}, blocking=True
    )
    assert coord.active_profile == "custom"


async def test_minute_end_accepts_59(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    ent = next(
        s.entity_id for s in hass.states.async_all("number")
        if "minute" in s.entity_id and ("end" in s.entity_id or "fin" in s.entity_id)
    )
    assert hass.states.get(ent).attributes["max"] == 59
    await hass.services.async_call(
        "number", "set_value", {"entity_id": ent, "value": 59}, blocking=True
    )


async def test_auth_failure_starts_reauth(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    ssh.refuse_auth = True
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"].get("source") == SOURCE_REAUTH for f in flows)


async def test_reauth_flow_updates_password(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ssh_password": "new-pw"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["ssh_password"] == "new-pw"


async def test_options_never_prefill_secrets_and_keep_them(hass, fake_ssh):
    entry, ssh = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    for key in schema:
        if str(key) in ("ssh_password", "sudo_password", "ssh_key", "ssh_key_passphrase"):
            assert key.default is vol.UNDEFINED  # never pre-filled
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "ssh_host": " 192.168.8.51 ", "ssh_host_vpn": "", "ssh_port": 22,
            "ssh_user": "parents", "auth_method": "password", "target_user": "camille",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["ssh_password"] == "secret-pw"
    assert entry.data["ssh_host"] == "192.168.8.51"


async def test_state_survives_host_change(hass, fake_ssh, hass_storage):
    """Store keyed by host+user: changing the IP lost profiles + queue."""
    hass_storage["timekpra_state_192.168.8.50_camille"] = {
        "version": 2, "key": "timekpra_state_192.168.8.50_camille",
        "data": {"pending": {}, "saved_values": {"profiles": {"Mine": {"hour_start": 9}}}},
    }
    entry, ssh = await _setup(hass)
    assert "Mine" in entry.runtime_data.coordinator.profiles
    assert "timekpra_state_e1" in hass_storage


async def test_user_flow_validates_port_and_trims_host(hass, fake_ssh):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**ENTRY_DATA, "ssh_host": " PC.local "},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["ssh_host"] == "PC.local"
    assert result["result"].unique_id == "timekpra_pc.local_camille"
