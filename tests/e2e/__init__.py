"""Playwright headless smoke tests for the public site.

These are skipped automatically when the optional ``playwright`` /
``pytest-playwright`` packages are not installed (see
``pytest.importorskip`` calls in the individual test modules), so the
regular pytest suite keeps working without extra setup.
"""
