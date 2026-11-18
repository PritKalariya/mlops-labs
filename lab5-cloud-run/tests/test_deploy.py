from deploy.deploy import EXIT_CANARY, EXIT_ERROR, EXIT_GATE, EXIT_OK, EXIT_REFUSED, EXIT_START, Deployer, main
from deploy.gate import GateResult

from .fakes import FakeGcloud

PREV = "lab5-forecast-00001"
IMAGE = "us-east1-docker.pkg.dev/p/lab5/forecast@sha256:" + "a" * 64


def make(gc, gate_ok=True, canary_bad=()):
    lines = []
    gate_calls = []

    def gate_fn(url, version):
        gate_calls.append((url, version))
        return GateResult(gate_ok, [] if gate_ok else ["golden[0] mismatch"], 12.0)

    deployer = Deployer(gc, gate_fn, lambda url: list(canary_bad), out=lines.append)
    return deployer, lines, gate_calls


def existing(**kwargs):
    gc = FakeGcloud(traffic={PREV: 100}, revisions=[], **kwargs)
    from deploy.gcloud import Revision
    gc.revisions.append(Revision(PREV, True, "2026-11-18T00:00:00Z"))
    gc._n = 1
    return gc


def test_startup_refusal_leaves_traffic_and_exits_2():
    gc = existing(refuse_deploy=True)
    deployer, lines, gate_calls = make(gc)
    assert deployer.run(IMAGE, "1.1.0") == EXIT_REFUSED
    assert gc.pct == {PREV: 100}
    assert gc.set_traffic_calls == []
    assert gc.tags == {}
    assert gate_calls == []
    assert any("refused by Cloud Run" in line for line in lines)
    assert lines[-1].startswith("RESULT outcome=refused-by-cloud-run")


def test_gate_failure_removes_tag_keeps_traffic_and_exits_3():
    gc = existing()
    deployer, lines, gate_calls = make(gc, gate_ok=False)
    assert deployer.run(IMAGE, "1.1.0") == EXIT_GATE
    assert gc.pct == {PREV: 100}
    assert gc.set_traffic_calls == []
    assert gc.tags == {} and gc.removed_tags == ["cand"]
    assert gate_calls and gate_calls[0][0].startswith("https://cand---")
    assert lines[-1].startswith("RESULT outcome=refused-by-gate")


def test_canary_failure_restores_previous_and_exits_4():
    gc = existing()
    deployer, lines, _ = make(gc, canary_bad=["HTTP 500"])
    assert deployer.run(IMAGE, "1.1.0") == EXIT_CANARY
    new = gc.latest_created
    assert gc.set_traffic_calls == [{PREV: 90, new: 10}, {PREV: 100}]
    assert gc.pct == {PREV: 100}
    assert gc.tags == {}
    assert lines[-1].startswith("RESULT outcome=canary-failed")


def test_split_traffic_at_start_changes_nothing_and_exits_1():
    gc = FakeGcloud(traffic={PREV: 60, "lab5-forecast-00002": 40})
    deployer, lines, _ = make(gc)
    assert deployer.run(IMAGE, "1.1.0") == EXIT_START
    assert gc.deploys == []
    assert gc.set_traffic_calls == []
    assert gc.pct == {PREV: 60, "lab5-forecast-00002": 40}


def test_exception_mid_promote_restores_start_traffic():
    # call 1 = canary split, call 2 = promote (raises), call 3 = restore
    gc = existing(fail_set_traffic_call=2)
    deployer, lines, _ = make(gc)
    assert deployer.run(IMAGE, "1.1.0") == EXIT_ERROR
    assert gc.pct == {PREV: 100}
    assert gc.tags == {}
    assert gc.set_traffic_calls[-1] == {PREV: 100}
    assert lines[-1].startswith("RESULT outcome=error-restored")


def test_good_release_promotes_and_exits_0():
    gc = existing()
    deployer, lines, _ = make(gc)
    assert deployer.run(IMAGE, "1.1.0") == EXIT_OK
    new = gc.latest_created
    assert new != PREV
    assert gc.pct == {new: 100}
    assert gc.tags == {}
    assert gc.deploys[0]["no_traffic"] is True and gc.deploys[0]["tag"] == "cand"
    assert lines[-1].startswith("RESULT outcome=promoted")


def test_first_release_goes_to_100_and_pins_revision():
    gc = FakeGcloud()
    deployer, lines, gate_calls = make(gc)
    assert deployer.run(IMAGE, "1.0.0") == EXIT_OK
    assert gc.deploys[0]["no_traffic"] is False
    assert list(gc.pct.values()) == [100]
    assert gate_calls[0][0] == "https://lab5-forecast-fake.run.app"


def test_first_release_gate_failure_exits_1():
    gc = FakeGcloud()
    deployer, lines, _ = make(gc, gate_ok=False)
    assert deployer.run(IMAGE, "1.0.0") == EXIT_START


def test_main_refuses_a_tag_reference():
    assert main(["--image", "us-east1-docker.pkg.dev/p/lab5/forecast:v1", "--expect-version", "1.0.0"]) == EXIT_START
