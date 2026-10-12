"""Tests for the SSH layer (no network: connections are faked)."""
from __future__ import annotations

import asyncio

import pytest

from conftest import load
from test_timekpr_data import USERINFO_LOGGED_OUT

ssh_mod = load("ssh")
TimekpraSSH = ssh_mod.TimekpraSSH


def make(**kw) -> TimekpraSSH:
    return TimekpraSSH(host="10.0.0.1", port=22, username="parents", **kw)


def run(coro):
    return asyncio.run(coro)


class Recorder:
    """Replace execute() and record the remote command lines."""

    def __init__(self, ssh: TimekpraSSH, output: str = "", exc: Exception | None = None):
        self.commands: list[tuple[str, bool]] = []
        self.output = output
        self.exc = exc
        ssh.execute = self  # type: ignore[method-assign]

    async def __call__(self, command: str, check: bool = False) -> str:
        self.commands.append((command, check))
        if self.exc is not None:
            raise self.exc
        return self.output


def test_sanitize_never_yields_an_option():
    assert ssh_mod._sanitize("--rf") == "rf"
    assert ssh_mod._sanitize("camille; rm -rf /") == "camillerm-rf"
    assert ssh_mod._sanitize("jean-paul.d") == "jean-paul.d"


def test_connect_kwargs_has_connect_timeout():
    kwargs = make(password="pw")._connect_kwargs()
    assert kwargs["connect_timeout"] == ssh_mod.CONNECT_TIMEOUT
    assert kwargs["password"] == "pw"


def test_sudo_password_is_quoted():
    cmd = make(password="it's")._sudo("cat /x")
    assert cmd == "echo 'it'\\''s' | sudo -S -p '' cat /x"
    assert make(ssh_key="", sudo_password="")._sudo("ls") == "sudo -n ls"


def test_set_allowed_hours_command_and_validation():
    ssh = make()
    rec = Recorder(ssh)
    run(ssh.set_allowed_hours("camille", 8, 20, 30, 45))
    assert rec.commands == [(
        "sudo -n timekpra --setallowedhours 'camille' 'ALL' "
        "'8[30-59];9;10;11;12;13;14;15;16;17;18;19;20[00-45]'",
        True,
    )]
    with pytest.raises(ValueError):
        run(ssh.set_allowed_hours("camille", 21, 20, 0, 59))
    with pytest.raises(ValueError):
        run(ssh.set_allowed_hours("camille", 8, 8, 0, 0))
    assert len(rec.commands) == 1  # nothing sent for the invalid ranges


def test_set_time_left_rejects_unknown_operator():
    ssh = make()
    rec = Recorder(ssh)
    run(ssh.set_time_left("camille", "-", 3600))
    assert rec.commands[0][0] == "sudo -n timekpra --settimeleft 'camille' '-' '3600'"
    with pytest.raises(ValueError):
        run(ssh.set_time_left("camille", "'; reboot; '", 1))


def test_set_allowed_days_filters_values():
    ssh = make()
    rec = Recorder(ssh)
    run(ssh.set_allowed_days("camille", [7, 1, 1, 9, 0]))
    assert rec.commands[0][0] == "sudo -n timekpra --setalloweddays 'camille' '1;7'"


def test_get_user_info():
    ssh = make()
    rec = Recorder(ssh, output=USERINFO_LOGGED_OUT)
    info = run(ssh.get_user_info("camille"))
    assert rec.commands == [("sudo -n timekpra --userinfo 'camille'", True)]
    assert info["TIME_LEFT_DAY"] == "9600"
    Recorder(ssh, output="")
    assert run(ssh.get_user_info("camille")) is None


def test_get_config_failed_or_empty_read_is_not_a_config():
    ssh = make()
    ssh._config_path = "/var/lib/timekpr/config/timekpr.camille.conf"
    Recorder(ssh, exc=ssh_mod.TimekpraCommandError("exit 1: sudo: a password is required"))
    assert run(ssh.get_config("camille")) is None
    assert ssh._config_path is None  # re-located next time

    ssh._config_path = "/var/lib/timekpr/config/timekpr.camille.conf"
    rec = Recorder(ssh, output="")
    assert run(ssh.get_config("camille")) is None
    assert rec.commands[0] == (
        "sudo -n cat /var/lib/timekpr/config/timekpr.camille.conf", True
    )

    Recorder(ssh, output="[DOCUMENTATION]\n#x\n[camille]\nLIMITS_PER_WEEKDAYS = 3600\n")
    assert run(ssh.get_config("camille")) == {"LIMITS_PER_WEEKDAYS": "3600"}


def test_found_path_is_shell_quoted():
    ssh = make()
    ssh._time_path = "/var/lib/odd dir/camille.time"
    rec = Recorder(ssh, output="TIME_SPENT_DAY = 5\n")
    assert run(ssh.get_time_spent("camille")) == {"TIME_SPENT_DAY": "5"}
    assert rec.commands[0][0] == "sudo -n cat '/var/lib/odd dir/camille.time'"


def test_find_fallback_uses_exact_names():
    ssh = make()
    rec = Recorder(ssh, output="")
    run(ssh._find_path("ana", ssh_mod.TIME_PATHS))
    find_cmd = rec.commands[-1][0]
    assert "-name 'ana.time'" in find_cmd
    assert "-name '*.ana.time'" in find_cmd
    assert "*ana*" not in find_cmd  # would also match "anabelle"


class FakeConn:
    def __init__(self, name: str):
        self.name = name
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


def test_sessions_in_concurrent_tasks_do_not_share_connections():
    """Two overlapping sessions (refresh + profile push) keep their own conn."""

    async def scenario():
        ssh = make()
        conns = iter([FakeConn("A"), FakeConn("B")])
        used: list[tuple[str, str]] = []

        async def fake_open():
            return next(conns)

        async def fake_run(conn, command, check):
            assert not conn.closed, f"{command} ran on a closed connection"
            used.append((command, conn.name))
            return ""

        async def fake_one_shot(host, command, check=False):
            used.append((command, "one-shot"))
            return ""

        ssh._open_session_conn = fake_open
        ssh._run_on_conn = fake_run
        ssh._execute_on_host = fake_one_shot

        a_opened = asyncio.Event()
        b_done = asyncio.Event()

        async def task_a():
            async with ssh.session() as ok:
                assert ok
                await ssh.execute("a1")
                a_opened.set()
                await b_done.wait()
                await ssh.execute("a2")  # B's session is closed by now

        async def task_b():
            await a_opened.wait()
            async with ssh.session():
                await ssh.execute("b1")
                async with ssh.session():  # nested: reuses B
                    await ssh.execute("b2")
            b_done.set()

        await asyncio.gather(task_a(), task_b())
        await ssh.execute("outside")
        return used

    used = run(scenario())
    assert used == [
        ("a1", "A"), ("b1", "B"), ("b2", "B"), ("a2", "A"), ("outside", "one-shot")
    ]


def test_session_without_connection_yields_false():
    async def scenario():
        ssh = make()

        async def fake_open():
            return None

        ssh._open_session_conn = fake_open
        async with ssh.session() as ok:
            return ok

    assert run(scenario()) is False


def test_hung_remote_command_times_out(monkeypatch):
    monkeypatch.setattr(ssh_mod, "COMMAND_TIMEOUT", 0.05)

    class Stream:
        async def read(self):
            await asyncio.sleep(10)

    class Proc:
        stdout = Stream()
        stderr = Stream()
        returncode = None
        closed = False

        def close(self):
            Proc.closed = True

        async def wait_closed(self):
            return None

    class Conn:
        async def create_process(self, command):
            return Proc()

    with pytest.raises(TimeoutError):
        run(make()._run_on_conn(Conn(), "timekpra --userinfo 'x'", False))
    assert Proc.closed
    assert issubclass(TimeoutError, OSError)  # → queued as "offline"
