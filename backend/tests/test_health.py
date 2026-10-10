def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "timestamp" in data


def test_system_status_endpoint(client):
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["database_connected"] is True
    assert "integrations" in data
    
    # Verify unconfigured integrations are strictly labeled NOT_CONFIGURED
    integrations_map = {item["name"]: item for item in data["integrations"]}
    assert "SEBI Public DRHP/RHP Filings Feed" in integrations_map
    assert integrations_map["SEBI Public DRHP/RHP Filings Feed"]["status"] == "NOT_CONFIGURED"
    assert integrations_map["SEBI Public DRHP/RHP Filings Feed"]["verified"] is False
    assert integrations_map["NSE Circulars & Live Bidding API"]["status"] == "NOT_CONFIGURED"
