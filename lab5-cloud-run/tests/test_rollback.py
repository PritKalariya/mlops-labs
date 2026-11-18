import subprocess

import pytest

from deploy import rollback
from deploy.gcloud import Revision

from .fakes import FakeGcloud

R1, R2, R3, R4 = (f"lab5-forecast-0000{i}" for i in range(1, 5))


def fleet(**kwargs):
    gc = FakeGcloud(traffic={R4: 100}, **kwargs)
    gc.revisions = [
        Revision(R1, True, "2026-11-18T00:00:01Z"),
        Revision(R2, True, "2026-11-18T00:00:02Z"),
        Revision(R3, False, "2026-11-18T00:00:03Z"),
        Revision(R4, True, "2026-11-18T00:00:04Z"),
    ]
    return gc


def test_refuses_a_revision_that_is_not_ready():
    gc = fleet()
    lines = []
    code = rollback.run(gc, to=R3, out=lines.append, ready_check=lambda url, token: 200)
    assert code == rollback.EXIT_REFUSED
    assert gc.pct == {R4: 100}
    assert gc.set_traffic_calls == []
    assert any("not Ready" in line for line in lines)


def test_refuses_an_unknown_revision():
    gc = fleet()
    assert rollback.run(gc, to="nope", out=lambda _: None, ready_check=lambda u, t: 200) == rollback.EXIT_REFUSED
    assert gc.set_traffic_calls == []


def test_without_to_exits_nonzero_and_makes_no_gcloud_calls(monkeypatch, capsys):
    constructed, spawned = [], []
    monkeypatch.setattr(rollback, "Gcloud", lambda *a, **k: constructed.append(1))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: spawned.append(a))
    with pytest.raises(SystemExit) as exc:
        rollback.main([])
    assert exc.value.code != 0
    assert constructed == [] and spawned == []
    assert "--to" in capsys.readouterr().err


def test_to_moves_all_traffic_and_checks_readiness():
    gc = fleet()
    seen = []
    code = rollback.run(gc, to=R1, out=lambda _: None, ready_check=lambda url, token: seen.append((url, token)) or 200)
    assert code == rollback.EXIT_OK
    assert gc.pct == {R1: 100}
    assert seen == [("https://lab5-forecast-fake.run.app", "fake-token")]


def test_readiness_failure_after_shift_exits_2():
    gc = fleet()
    code = rollback.run(gc, to=R1, out=lambda _: None, ready_check=lambda url, token: 503)
    assert code == rollback.EXIT_NOT_READY
