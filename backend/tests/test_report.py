def test_weekly_returns_list(client):
    resp = client.get("/api/report/weekly")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_snapshot_creates_row(client):
    resp = client.post("/api/report/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "composite_score" in data
    assert "week_start" in data

    weeks = client.get("/api/report/weekly").json()
    assert len(weeks) >= 1
