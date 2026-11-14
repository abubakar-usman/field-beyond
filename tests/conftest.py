from __future__ import annotations

import pytest

from core.bodies import EARTH, MARS, MOON, Body
from core.config import load_scoring

# One comparison pixel size per body, as used in the app (D-023):
# Earth is checked at both scales; Moon at 60 m; Mars at 200 m.
BODY_SCALES: list[tuple[Body, float]] = [(EARTH, 200.0), (EARTH, 60.0), (MOON, 60.0), (MARS, 200.0)]


@pytest.fixture(params=BODY_SCALES, ids=lambda p: f"{p[0].name.value}-{int(p[1])}m")
def body_scale(request: pytest.FixtureRequest) -> tuple[Body, float]:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture()
def scoring():  # type: ignore[no-untyped-def]
    return load_scoring("terrain-v1")
