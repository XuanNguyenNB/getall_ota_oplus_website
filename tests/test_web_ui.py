def test_web_ui_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<html lang="vi">' in response.text
    assert "OPlus OTA Monitor" in response.text
    assert "Kho OTA công khai" in response.text
    assert "data-i18n=\"page.subtitle\"" in response.text
    assert "data-language=\"vi\"" in response.text
    assert "data-language=\"en\"" in response.text
    assert "https://t.me/oplusota" in response.text
    assert "https://1drv.ms/u/c/8CF4C16C05F8CFD6/IQAt-3AgpD--TYNB1il6HWQZAUYY9H7bjLh_xCXRXhvmKMg?e=axjnjx" in response.text
    assert "https://1drv.ms/u/c/8CF4C16C05F8CFD6/IQCpaREQxw-wTrcXzvwkebh-AVZqBXmvucmDBWeiHCOAo2s?e=jFwGO5" in response.text
    assert "https://1drv.ms/u/c/8CF4C16C05F8CFD6/IQDIixbMZjMETr80OJIAwN_iAYoR_K-yVx5Yb_lObHqGuOM?e=bjUD7t" in response.text
    assert "https://developer.android.com/tools/releases/platform-tools" in response.text
    assert response.text.count('target="_blank"') >= 5
    assert response.text.count('rel="noopener noreferrer"') >= 5
    assert 'target="_blank"' in response.text
    assert 'rel="noopener noreferrer"' in response.text
    assert "data-i18n=\"resolver.infoText\"" in response.text
    assert "data-i18n=\"tools.title\"" in response.text
    assert "Private manual OTA lookup" not in response.text
    assert "<th>Source</th>" not in response.text
    assert "/static/app.js?v=" in response.text
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
    assert "function isResolvableDownloadUrl" in script.text
    assert "function isBrowserBlockedDownloadUrl" in script.text
    assert "function releaseSortTimestamp" in script.text
    assert "function releasePublishedLabel" in script.text
    assert "const translations = {" in script.text
    assert 'vi: {' in script.text
    assert 'en: {' in script.text
    assert 'LANGUAGE_STORAGE_KEY = "oplus_ota_language"' in script.text
    assert "function setLanguage" in script.text
    assert "document.documentElement.lang = state.language" in script.text
    assert 't("actions.findOta")' in script.text
    assert "archive.summary" in script.text
    assert 't("resolver.resolvedUrl")' in script.text
    assert "resolver.infoText" in script.text
    assert "tools.title" in script.text
    assert "tools.fastboot" in script.text
    assert "tools.resolverDownloader" in script.text
    assert "tools.driver" in script.text
    assert "tools.platformTools" in script.text
    assert "component-ota|ota" in script.text
    assert "gauss-componentotacostmanual-cn." in script.text
    assert "gauss-compotacostauto-cn." in script.text
    assert "release.resolveTitle" in script.text
    assert "isBrowserBlockedDownloadUrl(downloadUrl)" in script.text
    assert 'resolve: "resolverChallenge"' in script.text
    assert '["ota", "resolve"]' in script.text
    assert '["ota", "resolver"]' not in script.text
    assert 'activeHeaders("resolve")' in script.text
    assert 'execution: "execute"' in script.text
    assert 'appearance: "interaction-only"' in script.text
    assert "requestChallengeToken(action)" in script.text
    assert "Complete human verification first" not in script.text
    assert "`#${action}Challenge`" not in script.text
    assert style.status_code == 200
    assert "text/css" in style.headers["content-type"]
    assert "grid-template-columns: 92px minmax(0, 1fr)" in style.text
    assert ".language-switch" in style.text
    assert ".language-button.active" in style.text
    assert ".info-popover" in style.text
    assert ".support-tools" in style.text
    assert ".tool-link" in style.text
    assert ".silent-challenge-panel" in style.text
    assert "position: absolute" in style.text
