"""SPA serving: missing assets must 404, HTML must be no-store."""


def test_missing_asset_returns_404_not_html(client):
    # A stale index.html would request an old hashed bundle; it must 404, not
    # receive the SPA HTML (which the browser would try to run as JS -> blank).
    r = client.get("/assets/index-doesnotexist123.js")
    assert r.status_code == 404


def test_asset_extension_paths_404_when_missing(client):
    for path in ("/foo.js", "/bar.css", "/nested/thing.map"):
        assert client.get(path).status_code == 404


def test_spa_route_serves_index_html_no_store(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert r.headers.get("cache-control") == "no-store, must-revalidate"
