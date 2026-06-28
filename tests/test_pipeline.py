from sindri.pipeline import review

COMPOSE = """
services:
  api:
    build: .
  db:
    image: postgres:16
"""


def test_review_end_to_end_flags_db_at_scale():
    out = review(COMPOSE, nfrs={"dau": 50_000_000})
    assert "BOTTLENECK: db" in out
    assert "daily users" in out


def test_review_states_assumptions_when_nfrs_missing():
    out = review(COMPOSE, nfrs=None)
    assert "Assumptions" in out
    assert "Confidence: low" in out


def test_review_empty_compose_is_friendly_not_crash():
    out = review("::: not yaml :::")
    assert "Sindri" in out
    assert "couldn't" in out.lower() or "no components" in out.lower()
