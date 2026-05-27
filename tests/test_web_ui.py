def test_web_ui_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "OPlus OTA Monitor" in response.text
    assert "Public OTA archive" in response.text
    assert "Private manual OTA lookup" not in response.text
    assert "<th>Source</th>" not in response.text
    assert "/static/app.js" in response.text
    assert "runtimeStatus" in response.text
    assert "resolverPanel" in response.text


def test_web_ui_static_assets_are_served(client):
    script = client.get("/static/app.js")
    style = client.get("/static/styles.css")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "GET /api/devices" not in script.text
    assert "fetch(path" in script.text
    assert "X-Turnstile-Token" in script.text
    assert 'colspan="5"' in script.text
    assert "release.source ||" not in script.text
    assert "ROW / A7" not in script.text
    assert "${manifestLabel} (${regionCode}) / ${manifestCode}" in script.text
    assert style.status_code == 200
    assert "text/css" in style.headers["content-type"]
    assert "grid-template-columns: 92px minmax(0, 1fr)" in style.text
