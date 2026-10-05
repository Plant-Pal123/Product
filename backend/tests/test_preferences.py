def test_update_then_get_preferences_roundtrip(client, test_plot):
    # test_plot's fixture user id happens to be whatever the DB just assigned;
    # PUT with the same id it created preferences for confirms the upsert path.
    from app.db.models import Plot
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user_id = db.get(Plot, test_plot).user_id
    finally:
        db.close()

    put_response = client.put(
        f"/api/v1/preferences/{user_id}",
        json={"budget": 3000, "timeframe_days": 90, "excluded_crops": ["coffee", "grapes"]},
    )
    assert put_response.status_code == 200
    assert put_response.json() == {"budget": 3000.0, "timeframe_days": 90, "excluded_crops": ["coffee", "grapes"]}

    get_response = client.get(f"/api/v1/preferences/{user_id}")
    assert get_response.status_code == 200
    assert get_response.json() == {"budget": 3000.0, "timeframe_days": 90, "excluded_crops": ["coffee", "grapes"]}


def test_get_preferences_missing_user_404s(client):
    response = client.get("/api/v1/preferences/999999")
    assert response.status_code == 404
