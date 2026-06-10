"""Unit tests for GraphClient Redis caching."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.knowledge.graph_client import GraphClient
from src.shared.models import Demographics, Sex


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.run = AsyncMock()
    driver.session = MagicMock(return_value=session)
    return driver, session


@pytest.mark.asyncio
async def test_nutrient_meta_cache_hit_skips_neo4j(mock_driver):
    driver, session = mock_driver
    redis = AsyncMock()
    redis.get = AsyncMock(return_value='{"nutrient_id":"vitamin_d3","name":"Vitamin D3",'
                        '"form":"cholecalciferol","rda":600,"ear":400,"ul":4000,'
                        '"dose_unit":"IU","bioavailability_factor":1.0,"loinc_codes":["1989-3"]}')
    redis.setex = AsyncMock()

    with patch.object(GraphClient, "__init__", lambda self, *a, **k: None):
        client = GraphClient.__new__(GraphClient)
        client._driver = driver
        client._database = "neo4j"
        client._redis = redis

    meta = await client.get_nutrient_meta("vitamin_d3")
    assert meta is not None
    assert meta.name == "Vitamin D3"
    session.run.assert_not_called()


@pytest.mark.asyncio
async def test_baseline_cache_uses_correct_key(mock_driver):
    driver, session = mock_driver
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    result_mock = MagicMock()
    result_mock.single = AsyncMock(return_value={"prevalence": 0.65})
    session.run = AsyncMock(return_value=result_mock)

    with patch.object(GraphClient, "__init__", lambda self, *a, **k: None):
        client = GraphClient.__new__(GraphClient)
        client._driver = driver
        client._database = "neo4j"
        client._redis = redis

    demo = Demographics(age=40, sex=Sex.F, region_code="SA-01")
    prevalence = await client.get_baseline_prevalence("vitamin_d3", demo)
    assert prevalence == 0.65
    redis.setex.assert_called_once()
    cache_key = redis.setex.call_args[0][0]
    assert cache_key.startswith("baseline:vitamin_d3:")
