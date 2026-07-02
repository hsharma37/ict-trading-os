import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import json
import sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
checks = {
    "health": client.get("/health").status_code,
    "docs": client.get("/docs").status_code,
    "openapi": client.get("/openapi.json").status_code,
    "settings_get_no_key": client.get("/settings").status_code,
    "settings_get_valid_key": client.get("/settings", headers={"X-Api-Key": "secret"}).status_code,
    "settings_post_no_key": client.post("/settings", json={"theme": "light"}).status_code,
    "settings_post_bad_key": client.post("/settings", json={"theme": "light"}, headers={"X-Api-Key": "bad"}).status_code,
    "settings_post_valid_key": client.post("/settings", json={"theme": "light"}, headers={"X-Api-Key": "secret"}).status_code,
    "delete_no_key": client.delete("/market/manual-price/EURUSD").status_code,
    "delete_bad_key": client.delete("/market/manual-price/EURUSD", headers={"X-Api-Key": "bad"}).status_code,
    "delete_valid_key": client.delete("/market/manual-price/EURUSD", headers={"X-Api-Key": "secret"}).status_code,
}
sys.stdout.write(json.dumps(checks))
"""


def run_probe(tmp_path, overrides, check=True):
    env = os.environ.copy()
    for key in (
        "APP_ENV",
        "PYTHON_ENV",
        "VERCEL_ENV",
        "VERCEL",
        "TRADINGOS_RUNTIME",
        "AUTH_ENABLED",
        "REQUIRE_API_AUTH",
        "ALLOW_PUBLIC_API_MUTATIONS",
        "API_KEY",
        "JWT_SECRET",
        "DATABASE_URL",
    ):
        env.pop(key, None)
    env.update({
        "DATABASE_PATH": str(tmp_path / "auth.db"),
        "PRICE_CACHE_DIR": str(tmp_path),
        "ALLOW_SQLITE_RUNTIME": "true",
        **overrides,
    })
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def probe_json(tmp_path, overrides):
    result = run_probe(tmp_path, overrides)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_public_routes_stay_public_when_auth_enabled(tmp_path):
    data = probe_json(tmp_path, {
        "AUTH_ENABLED": "true",
        "API_KEY": "secret",
        "JWT_SECRET": "jwt-secret",
    })
    assert data["health"] == 200
    assert data["docs"] == 200
    assert data["openapi"] == 200


def test_production_defaults_require_auth_when_auth_enabled_unset(tmp_path):
    data = probe_json(tmp_path, {
        "APP_ENV": "production",
        "API_KEY": "secret",
        "JWT_SECRET": "jwt-secret",
    })
    assert data["settings_get_no_key"] == 401
    assert data["settings_post_no_key"] == 401
    assert data["delete_no_key"] == 401


def test_valid_api_key_allows_protected_routes(tmp_path):
    data = probe_json(tmp_path, {
        "AUTH_ENABLED": "true",
        "API_KEY": "secret",
        "JWT_SECRET": "jwt-secret",
    })
    assert data["settings_post_no_key"] == 401
    assert data["settings_post_bad_key"] == 401
    assert data["settings_post_valid_key"] != 401
    assert data["delete_no_key"] == 401
    assert data["delete_bad_key"] == 401
    assert data["delete_valid_key"] != 401


def test_local_defaults_remain_usable(tmp_path):
    data = probe_json(tmp_path, {})
    assert data["settings_get_no_key"] == 200
    assert data["settings_post_no_key"] == 200
    assert data["delete_no_key"] == 200


def test_production_missing_api_key_fails_startup(tmp_path):
    result = run_probe(tmp_path, {
        "APP_ENV": "production",
        "JWT_SECRET": "jwt-secret",
    }, check=False)
    assert result.returncode != 0
    assert "API_KEY" in result.stderr
