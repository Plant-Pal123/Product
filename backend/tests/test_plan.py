from tests.conftest import requires_classifier, requires_regressor


@requires_classifier
@requires_regressor
def test_full_recommend_to_pdf_flow(client, test_plot):
    recommend_response = client.post(f"/api/v1/plots/{test_plot}/recommend")
    assert recommend_response.status_code == 200
    recommendation_id = recommend_response.json()["recommendation_id"]

    plan_response = client.post(f"/api/v1/recommendations/{recommendation_id}/plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["recommendation_id"] == recommendation_id

    content = plan["content"]
    assert len(content["heuristics"]) > 0
    assert content["timeline"]["days_to_harvest"] > 0
    assert content["timeline"]["harvest_date"] > content["timeline"]["sow_date"]
    assert set(content["soil_effect"]["current"]) == {"n", "p", "k", "ph"}
    assert "margin" in content["finances"]

    pdf_response = client.get(f"/api/v1/plans/{plan['id']}/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")


@requires_classifier
@requires_regressor
def test_plan_missing_recommendation_404s(client):
    response = client.post("/api/v1/recommendations/999999/plan")
    assert response.status_code == 404


def test_pdf_missing_plan_404s(client):
    response = client.get("/api/v1/plans/999999/pdf")
    assert response.status_code == 404
