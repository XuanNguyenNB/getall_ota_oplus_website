def test_web_ui_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<html lang="vi">' in response.text
    assert "OPlus OTA Monitor" in response.text
    assert "Tìm OTA, EDL ROM" in response.text
    assert 'data-i18n="page.subtitle"' in response.text
    assert "search-first-layout" in response.text
    assert "finder-panel" in response.text
    assert "archive-panel" in response.text
    assert "secondary-grid" in response.text
    assert "advancedOtaPanel" in response.text
    assert 'data-i18n="finder.title"' in response.text
    assert 'data-i18n="advanced.title"' in response.text
    assert 'data-language="vi"' in response.text
    assert 'data-language="en"' in response.text
    assert "https://t.me/oplusota" in response.text
    assert (
        "https://1drv.ms/u/c/8CF4C16C05F8CFD6/IQAt-3AgpD--TYNB1il6HWQZAUYY9H7bjLh_xCXRXhvmKMg?e=axjnjx"
        in response.text
    )
    assert (
        "https://1drv.ms/u/c/8CF4C16C05F8CFD6/IQCpaREQxw-wTrcXzvwkebh-AVZqBXmvucmDBWeiHCOAo2s?e=jFwGO5"
        in response.text
    )
    assert (
        "https://1drv.ms/u/c/8CF4C16C05F8CFD6/IQDIixbMZjMETr80OJIAwN_iAYoR_K-yVx5Yb_lObHqGuOM?e=bjUD7t"
        in response.text
    )
    assert "https://developer.android.com/tools/releases/platform-tools" in response.text
    assert response.text.count('target="_blank"') >= 5
    assert response.text.count('rel="noopener noreferrer"') >= 5
    assert 'data-i18n="resolver.infoText"' in response.text
    assert 'data-i18n="tools.title"' in response.text
    assert 'data-package="ota"' in response.text
    assert 'data-package="edl"' in response.text
    assert 'data-i18n="edl.warning"' in response.text
    assert "Private manual OTA lookup" not in response.text
    assert "glowing-bg-elements" not in response.text
    assert "<th>Source</th>" not in response.text
    assert "/static/app.js?v=" in response.text
    assert "/static/styles.css?v=" in response.text
    assert "runtimeStatus" in response.text
    assert "resolverPanel" in response.text
    # Light/dark theme toggle.
    assert "themeToggle" in response.text
    assert 'data-i18n-title="actions.theme"' in response.text
    assert "icon-sun" in response.text
    assert "icon-moon" in response.text
    assert "oplus_ota_theme" in response.text
    assert 'name="color-scheme"' in response.text


def test_web_ui_static_assets_are_served(client):
    script = client.get("/static/app.js")
    style = client.get("/static/styles.css")
    api_module = client.get("/static/modules/api.js")
    state_module = client.get("/static/modules/state.js")
    i18n_module = client.get("/static/modules/i18n.js")
    format_module = client.get("/static/modules/format.js")
    theme_module = client.get("/static/modules/theme.js")
    url_safety_module = client.get("/static/modules/url-safety.js")
    challenge_module = client.get("/static/modules/challenge.js")
    vi_translations = client.get("/static/i18n/vi.json")
    en_translations = client.get("/static/i18n/en.json")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert all(
        response.status_code == 200
        for response in (
            api_module,
            state_module,
            i18n_module,
            format_module,
            theme_module,
            url_safety_module,
            challenge_module,
            vi_translations,
            en_translations,
        )
    )
    assert "GET /api/devices" not in script.text
    assert "fetch(path" in api_module.text
    assert "X-Turnstile-Token" in challenge_module.text
    assert 'colspan="5"' in script.text
    assert "release.source ||" not in script.text
    assert "ROW / A7" not in format_module.text
    assert "${manifestLabel} (${regionCode}) / ${manifestCode}" in format_module.text
    assert "export function isResolvableDownloadUrl" in url_safety_module.text
    assert "export function isBrowserBlockedDownloadUrl" in url_safety_module.text
    assert "export function releaseSortTimestamp" in format_module.text
    assert "export function releasePublishedLabel" in format_module.text
    # Translation dictionaries now live in JSON, fetched at runtime.
    assert "page.title" in vi_translations.text
    assert "page.title" in en_translations.text
    assert "Tìm OTA" in vi_translations.text
    assert "Find OTA" in en_translations.text
    assert "loadLanguage" in i18n_module.text
    assert 'LANGUAGE_STORAGE_KEY = "oplus_ota_language"' in state_module.text
    assert "function setLanguage" in script.text
    assert "document.documentElement.lang = state.language" in i18n_module.text
    assert 't("actions.findOta")' in script.text
    assert "flow.stepSearch" not in vi_translations.text
    assert "flow.stepArchive" not in vi_translations.text
    assert "finder.title" in vi_translations.text
    assert "advanced.title" in vi_translations.text
    assert "archive.summary" in vi_translations.text
    assert 't("resolver.resolvedUrl")' in script.text
    assert "resolver.infoText" in vi_translations.text
    assert "tools.title" in vi_translations.text
    assert "tools.fastboot" in vi_translations.text
    assert "tools.resolverDownloader" in vi_translations.text
    assert "tools.driver" in vi_translations.text
    assert "tools.platformTools" in vi_translations.text
    assert "package.edl" in vi_translations.text
    assert "edl.warning" in vi_translations.text
    assert "edl.summary" in vi_translations.text
    assert 'state.packageMode === "edl"' in script.text
    assert "/api/edl-roms" in script.text
    assert "function renderEdlRoms" in script.text
    assert "function renderEdlActions" in script.text
    assert "data-copy-edl" in script.text
    assert "data-open-edl" in script.text
    assert "data-resolve-edl" not in script.text
    assert "component-ota|ota" in format_module.text
    assert "gauss-componentotacostmanual-cn." in url_safety_module.text
    assert "gauss-compotacostauto-cn." in url_safety_module.text
    assert "release.resolveTitle" in vi_translations.text
    assert "function releaseGroupKey" in script.text
    assert "function buildReleaseGroups" in script.text
    assert "function renderReleaseVariantLinks" in script.text
    assert "release.summaryGrouped" not in script.text
    assert "archive.summaryGrouped" in vi_translations.text
    assert "release.duplicateBadge" in vi_translations.text
    assert "release.showVariants" in vi_translations.text
    assert "release.primaryLink" in vi_translations.text
    assert "release.alternateLink" in vi_translations.text
    assert 'release.product_model || ""' in script.text
    assert 'release.real_ota_version || release.real_version_name || ""' in script.text
    assert 'release.release_type || "official"' in script.text
    assert "releaseGroups.length < state.releases.length" in script.text
    assert "renderReleaseVariantLinks(group)" in script.text
    assert "group.primary" in script.text
    assert "group.variants.length <= 1" in script.text
    assert "release-variant-badge" in script.text
    assert "isBrowserBlockedDownloadUrl(downloadUrl)" in script.text
    assert 'resolve: "resolverChallenge"' in state_module.text
    assert '["ota", "resolve"]' in challenge_module.text
    assert '["ota", "resolver"]' not in challenge_module.text
    assert 'activeHeaders("resolve")' in script.text
    assert 'execution: "execute"' in challenge_module.text
    assert 'appearance: "interaction-only"' in challenge_module.text
    assert "requestChallengeToken(action)" in challenge_module.text
    assert "Complete human verification first" not in script.text
    assert "`#${action}Challenge`" not in script.text
    # Light/dark theme toggle wiring.
    assert 'THEME_STORAGE_KEY = "oplus_ota_theme"' in state_module.text
    assert "function toggleTheme" in theme_module.text
    assert "function applyTheme" in theme_module.text
    assert "function currentThemeIsDark" in theme_module.text
    assert "actions.theme" in vi_translations.text
    assert 'classList.toggle("dark"' in theme_module.text

    assert style.status_code == 200
    assert "text/css" in style.headers["content-type"]
    # Built by the Tailwind v4 standalone CLI; assert stable component classes
    # and theme tokens rather than hand-authored declarations.
    assert "tailwindcss v4" in style.text
    assert ".search-first-layout" in style.text
    assert ".finder-panel" in style.text
    assert ".archive-panel" in style.text
    assert ".secondary-grid" in style.text
    assert ".release-table" in style.text
    assert ".language-switch" in style.text
    assert ".package-switch" in style.text
    assert ".package-tab.active" in style.text
    assert ".notice" in style.text
    assert ".language-button.active" in style.text
    assert ".info-popover" in style.text
    assert ".support-tools" in style.text
    assert ".tool-link" in style.text
    assert ".release-variants" in style.text
    assert ".release-variant-row" in style.text
    assert ".release-variant-actions" in style.text
    assert ".silent-challenge-panel" in style.text
    assert ".theme-toggle" in style.text
    # Class-based dark mode is compiled in.
    assert ".dark" in style.text
    assert "--app-bg:" in style.text
    assert "glow-circle" not in style.text
    assert "float-glow" not in style.text
