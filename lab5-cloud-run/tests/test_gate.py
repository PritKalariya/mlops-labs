import json

import httpx

from deploy import gate

CASES = [
    {"input": {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2},
     "output": {"species_id": 0, "species": "setosa"}},
    {"input": {"sepal_length": 6.3, "sepal_width": 2.5, "petal_length": 4.9, "petal_width": 1.5},
     "output": {"species_id": 1, "species": "versicolor"}},
]
ANSWERS = {json.dumps(c["input"], sort_keys=True): c["output"] for c in CASES}


def server(version="1.1.0", ready=200, flip_first=False, fail_after=None):
    state = {"predicts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/ready":
            return httpx.Response(ready, json={"status": "ready"})
        state["predicts"] += 1
        if fail_after is not None and state["predicts"] > fail_after:
            return httpx.Response(500, json={"detail": "boom"})
        payload = json.loads(request.content)
        out = dict(ANSWERS.get(json.dumps(payload, sort_keys=True), {"species_id": 0, "species": "setosa"}))
        if flip_first and state["predicts"] == 1:
            out = {"species_id": 2, "species": "virginica"}
        return httpx.Response(200, json={**out, "model_version": version})

    return httpx.MockTransport(handler)


def run(transport, expect="1.1.0", limit=10_000.0, skip_load=False):
    return gate.run_gate("https://svc.example", "tok", CASES, expect, limit, n=30, concurrency=5,
                         skip_load=skip_load, transport=transport)


def test_a_healthy_service_passes():
    result = run(server())
    assert result.ok, result.failures
    assert result.p95_ms is not None


def test_not_ready_fails():
    result = run(server(ready=503))
    assert not result.ok and "readiness" in result.failures[0]


def test_golden_mismatch_fails():
    result = run(server(flip_first=True))
    assert not result.ok and "golden[0] mismatch" in result.failures[0]


def test_version_mismatch_fails():
    result = run(server(version="1.0.0"))
    assert not result.ok and any("model_version" in f for f in result.failures)


def test_non_2xx_in_load_fails():
    # golden uses 2 predict calls, every call after that returns 500
    result = run(server(fail_after=len(CASES)))
    assert not result.ok and any("not 2xx" in f for f in result.failures)


def test_p95_over_threshold_fails():
    result = run(server(), limit=0.0)
    assert not result.ok and any("p95" in f for f in result.failures)


def test_token_is_sent_as_a_bearer_header():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    asyncio_result = gate.run_gate("https://svc.example", "tok", [], None, 1e9, skip_load=True,
                                   transport=httpx.MockTransport(handler))
    assert asyncio_result.ok
    assert seen["auth"] == "Bearer tok"


def test_floats_match_within_tolerance_and_labels_exactly():
    assert gate.values_match({"p": 0.5000004}, {"p": 0.5})
    assert not gate.values_match({"p": 0.51}, {"p": 0.5})
    assert not gate.values_match({"species": "setosa"}, {"species": "virginica"})
    assert not gate.values_match({"species_id": 1.0}, {"species_id": 1})


def test_golden_file_is_well_formed():
    cases = gate.load_golden()
    assert len(cases) == 5
    for case in cases:
        assert set(case["input"]) == {"sepal_length", "sepal_width", "petal_length", "petal_width"}
        assert set(case["output"]) == {"species_id", "species"}
