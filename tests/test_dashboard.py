from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings


def test_dashboard_serves_html_and_static_assets(tmp_path):
    settings = Settings(database_path=str(tmp_path / "test.db"))

    with TestClient(create_app(settings=settings, client=object())) as client:
        dashboard = client.get("/")
        stylesheet = client.get("/static/dashboard.css")
        script = client.get("/static/dashboard.js")

    assert dashboard.status_code == 200
    assert dashboard.headers["content-type"].startswith("text/html")
    assert "/static/dashboard.css" in dashboard.text
    assert "/static/dashboard.js" in dashboard.text
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


def test_status_exposes_dry_run_setting(tmp_path):
    settings = Settings(database_path=str(tmp_path / "test.db"), dry_run=True)

    with TestClient(create_app(settings=settings, client=object())) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {"dry_run": True}
