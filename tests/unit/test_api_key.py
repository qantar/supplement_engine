"""Unit tests for API key middleware (M1)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.api_key import ApiKeyMiddleware, is_exempt_path, load_api_keys


def _test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/v1/recommendations")
    def recommendations():
        return {"ok": True}

    return app


def test_load_api_keys_splits_comma_list(monkeypatch):
    monkeypatch.setenv("API_KEYS", " key-a , key-b ")
    assert load_api_keys() == frozenset({"key-a", "key-b"})


def test_is_exempt_path():
    assert is_exempt_path("/health")
    assert is_exempt_path("/docs")
    assert is_exempt_path("/openapi.json")
    assert not is_exempt_path("/v1/recommendations")


def test_middleware_allows_v1_with_valid_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEYS", "test-key")
    client = TestClient(_test_app())
    resp = client.post("/v1/recommendations", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200


def test_middleware_rejects_missing_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEYS", "test-key")
    client = TestClient(_test_app())
    resp = client.post("/v1/recommendations")
    assert resp.status_code == 401


def test_middleware_skips_health(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEYS", "test-key")
    client = TestClient(_test_app())
    resp = client.get("/health")
    assert resp.status_code == 200


def test_middleware_disabled_when_env_off(monkeypatch):
    monkeypatch.delenv("REQUIRE_API_KEY", raising=False)
    client = TestClient(_test_app())
    resp = client.post("/v1/recommendations")
    assert resp.status_code == 200
