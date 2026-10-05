from tests.conftest import requires_classifier, requires_regressor


@requires_classifier
@requires_regressor
def test_recommend_returns_ranked_crops_and_soil_targets(client, test_plot):
    response = client.post(f"/api/v1/plots/{test_plot}/recommend")
    assert response.status_code == 200

    body = response.json()
    assert body["recommendation_id"] > 0
    assert body["model_version"]

    assert len(body["crops"]) > 0
    top = body["crops"][0]
    assert 0.0 <= top["confidence"] <= 1.0
    assert isinstance(top["top_factors"], list)
    # crops are ranked by confidence, highest first
    confidences = [c["confidence"] for c in body["crops"]]
    assert confidences == sorted(confidences, reverse=True)

    for key in ("n", "p", "k", "ph"):
        assert key in body["soil_targets"]
        assert key in body["soil_gap"]


@requires_classifier
@requires_regressor
def test_recommend_missing_plot_404s(client):
    response = client.post("/api/v1/plots/999999/recommend")
    assert response.status_code == 404


@requires_classifier
@requires_regressor
def test_recommend_excludes_all_crops_returns_422(client, test_plot):
    from app.db.models import Plot
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user_id = db.get(Plot, test_plot).user_id
    finally:
        db.close()

    # Every standard crop label is excluded, so preference filtering must reject all of them.
    all_names = [
        "rice", "maize", "chickpea", "kidneybeans", "pigeonpeas", "mothbeans", "mungbean",
        "blackgram", "lentil", "pomegranate", "banana", "mango", "grapes", "watermelon",
        "muskmelon", "apple", "orange", "papaya", "coconut", "cotton", "jute", "coffee",
    ]
    put_response = client.put(f"/api/v1/preferences/{user_id}", json={"excluded_crops": all_names})
    assert put_response.status_code == 200

    response = client.post(f"/api/v1/plots/{test_plot}/recommend")
    assert response.status_code == 422
    assert "excluded_by" in response.json()["detail"]
