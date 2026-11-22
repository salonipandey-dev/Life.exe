from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from lifeexe.core.config import Settings
from lifeexe.core.timeutil import FixedClock
from lifeexe.domain.rewards import GameConfig
from lifeexe.main import create_app
from tests.helpers import DEFAULT_NOW, new_client, register


@pytest.fixture(autouse=True)
def _quiet_logs() -> None:
    logging.getLogger("lifeexe").setLevel(logging.WARNING)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(DEFAULT_NOW)


@pytest.fixture
def make_app(tmp_path: Path, clock: FixedClock) -> Callable[..., Starlette]:
    def factory(game: GameConfig | None = None, **overrides: Any) -> Starlette:
        settings = Settings(
            env="test",
            db_path=str(tmp_path / "lifeexe-test.db"),
            frontend_dist=None,
            log_level="WARNING",
            auth_rate_limit_per_minute=overrides.pop("auth_rate_limit_per_minute", 1000),
            **overrides,
        )
        return create_app(settings, clock=clock, game=game)

    return factory


@pytest.fixture
def app(make_app: Callable[..., Starlette]) -> Starlette:
    return make_app()


@pytest.fixture
def client(app: Starlette) -> Iterator[TestClient]:
    c = new_client(app)
    register(c)
    yield c
