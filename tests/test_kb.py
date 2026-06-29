from brok.models import ComponentType
from brok.kb import get_capability, CAPABILITY_KB


def test_relational_db_has_cited_conservative_write_ceiling():
    cap = get_capability(ComponentType.RELATIONAL_DB)
    assert cap is not None
    # conservative low end around ~1k writes/sec, with a source
    assert cap.write_low is not None and cap.write_low <= 1000
    assert cap.source  # non-empty citation


def test_cache_read_far_exceeds_db():
    db = get_capability(ComponentType.RELATIONAL_DB)
    cache = get_capability(ComponentType.CACHE)
    assert cache.read_low > db.read_low


def test_cdn_does_not_serve_writes():
    cdn = get_capability(ComponentType.CDN)
    assert cdn.write_low is None and cdn.write_high is None


def test_unknown_has_no_capability():
    assert get_capability(ComponentType.UNKNOWN) is None
