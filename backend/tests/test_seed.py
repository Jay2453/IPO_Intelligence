from app.core.config import settings
from app.models.ipo import IPO


def test_seed_demo_data_endpoint(client, db_session):
    response = client.post("/api/v1/seed/demo?force=true")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Query database and verify all seeded records have is_demo = True
    seeded_ipos = db_session.query(IPO).all()
    assert len(seeded_ipos) >= 5
    for ipo in seeded_ipos:
        assert ipo.is_demo is True


def test_seed_demo_production_block(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = client.post("/api/v1/seed/demo")
    assert response.status_code == 403
    assert "strictly disabled in production" in response.json()["detail"]
