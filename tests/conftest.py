import pytest

import app.analyze_contract as ac
import app.generate_contract as gc


@pytest.fixture(autouse=True)
def _clear_idempotency_caches():
    """Both agents cache a successful result keyed on their inputs (see
    generate_contract._draft_cache / analyze_contract._analysis_cache) so a
    live re-run of the same contract can't silently return a different
    result. Several tests reuse the same fixed inputs across cases, so the
    cache must not survive past the test that populated it."""
    ac._analysis_cache.clear()
    gc._draft_cache.clear()
    yield
    ac._analysis_cache.clear()
    gc._draft_cache.clear()
