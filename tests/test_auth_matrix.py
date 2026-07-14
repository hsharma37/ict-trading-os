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
html_headers = {"Accept": "text/html,application/xhtml+xml"}
json_headers = {"Accept": "application/json"}
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
    # SPA-route/API-prefix collisions (/mt5, /settings, /telegram): a browser
    # navigation (Accept: text/html) must always get the SPA shell, even
    # unauthenticated; a real API/XHR call to the same bare path must stay
    # fully protected regardless of what Accept header it happens to send.
    "mt5_page_no_key_html_accept": client.get("/mt5", headers=html_headers).status_code,
    "telegram_page_no_key_html_accept": client.get("/telegram", headers=html_headers).status_code,
    "settings_page_no_key_html_accept": client.get("/settings", headers=html_headers).status_code,
    "settings_page_content_type": client.get("/settings", headers=html_headers).headers.get("content-type", ""),
    "settings_get_no_key_json_accept": client.get("/settings", headers=json_headers).status_code,
    "settings_get_no_key_no_accept": client.get("/settings").status_code,
    "settings_post_no_key_html_accept": client.post("/settings", json={"theme": "light"}, headers=html_headers).status_code,
    "mt5_status_no_key_html_accept": client.get("/mt5/status", headers=html_headers).status_code,
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


def test_spa_pages_load_unauthenticated_despite_prefix_collision(tmp_path):
    """/mt5, /settings, /telegram are both SPA client routes and protected API
    prefixes. A real browser navigating there (Accept: text/html) must get
    the app shell -- not a raw 401 -- even fully unauthenticated, exactly
    like every other page route."""
    data = probe_json(tmp_path, {
        "APP_ENV": "production",
        "API_KEY": "secret",
        "JWT_SECRET": "jwt-secret",
    })
    assert data["mt5_page_no_key_html_accept"] == 200
    assert data["telegram_page_no_key_html_accept"] == 200
    assert data["settings_page_no_key_html_accept"] == 200
    assert "text/html" in data["settings_page_content_type"]


def test_spa_collision_routes_stay_protected_for_real_api_calls(tmp_path):
    """The Accept-header exemption must never leak the real protected data:
    only requests that look like a browser navigation get the shell; a real
    API/XHR call to the same bare path (no text/html Accept, or a mutation)
    must still enforce the API key exactly as before."""
    data = probe_json(tmp_path, {
        "APP_ENV": "production",
        "API_KEY": "secret",
        "JWT_SECRET": "jwt-secret",
    })
    assert data["settings_get_no_key_json_accept"] == 401
    assert data["settings_get_no_key_no_accept"] == 401
    # A POST must never be treated as a navigation, regardless of Accept.
    assert data["settings_post_no_key_html_accept"] == 401
    # A real API sub-path (not the bare SPA route) must also stay protected.
    assert data["mt5_status_no_key_html_accept"] == 401
