from brok.nfr import resolve_nfrs, DEFAULT_NFRS


def test_no_input_uses_all_defaults_and_states_them():
    nfrs, assumptions = resolve_nfrs(None)
    assert nfrs == DEFAULT_NFRS
    assert any("100,000" in a or "100000" in a for a in assumptions)
    assert len(assumptions) == 5  # one per defaulted field


def test_provided_field_overrides_and_is_not_assumed():
    nfrs, assumptions = resolve_nfrs({"dau": 5_000_000})
    assert nfrs.dau == 5_000_000
    assert not any("daily" in a.lower() and "assum" in a.lower() for a in assumptions
                   if "5,000,000" not in a)
    # dau was provided, so there is no dau assumption line
    assert all("daily active users" not in a for a in assumptions)


def test_no_em_dash_in_assumptions():
    _, assumptions = resolve_nfrs(None)
    assert all("—" not in a for a in assumptions)
