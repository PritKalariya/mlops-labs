from gate import decide


def test_first_model_becomes_champion():
    assert decide(0.95, None) == "promote"


def test_gate_promotes_keeps_and_blocks():
    assert decide(0.97, 0.96) == "promote"
    assert decide(0.96, 0.96) == "keep"
    assert decide(0.95, 0.96) == "block"
