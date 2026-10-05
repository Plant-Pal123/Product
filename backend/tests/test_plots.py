def test_create_plot(client):
    response = client.post(
        "/api/v1/plots",
        json={"name": "New plot", "boundary": {"type": "Point", "coordinates": [174.77, -41.29]}},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "New plot"
    assert body["boundary"]["type"] == "Point"


def test_get_plot_data_returns_seeded_readings(client, test_plot):
    response = client.get(f"/api/v1/plots/{test_plot}/data")
    assert response.status_code == 200
    body = response.json()

    assert body["soil"]["ph"] == 6.5
    assert body["soil"]["n"] == 90.0
    assert body["weather"]["temp"] == 20.9
    assert body["satellite"]["ndvi_mean"] == 0.62
    assert body["as_of"]["soil"] is not None


def test_get_plot_data_missing_plot_404s(client):
    response = client.get("/api/v1/plots/999999/data")
    assert response.status_code == 404
