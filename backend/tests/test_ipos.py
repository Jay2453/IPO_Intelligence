from app.models.ipo import IPO
from app.models.documents import Document
from app.models.events import IPOEvent
from app.models.predictions import Prediction
from app.models.ml_model import ModelVersion


def test_list_ipos_empty(client):
    response = client.get("/api/v1/ipos")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_create_and_query_ipo(client, db_session):
    ipo = IPO(
        symbol="TESTIND",
        company_name="Test Industries India Ltd",
        exchange="NSE_BSE",
        category="MAINBOARD",
        lifecycle_status="PRICE_BAND_AVAILABLE",
        min_price=100.0,
        max_price=110.0,
        issue_size_crores=500.0,
        is_demo=False,
    )
    db_session.add(ipo)
    db_session.commit()

    # List
    response = client.get("/api/v1/ipos")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["company_name"] == "Test Industries India Ltd"
    assert data["items"][0]["is_demo"] is False

    # Search
    search_res = client.get("/api/v1/ipos?search=Test")
    assert search_res.json()["total"] == 1

    no_match = client.get("/api/v1/ipos?search=NonExistent")
    assert no_match.json()["total"] == 0

    # Filter
    cat_match = client.get("/api/v1/ipos?category=MAINBOARD")
    assert cat_match.json()["total"] == 1
    sme_match = client.get("/api/v1/ipos?category=SME")
    assert sme_match.json()["total"] == 0

    # Detail
    detail_res = client.get(f"/api/v1/ipos/{ipo.id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == ipo.id
    assert detail_data["min_price"] == 100.0


def test_get_ipo_not_found(client):
    response = client.get("/api/v1/ipos/invalid-id-000")
    assert response.status_code == 404
