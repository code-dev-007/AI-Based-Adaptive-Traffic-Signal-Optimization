import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend import db, main

client, anonymous = TestClient(main.app), TestClient(main.app)
SIM = {"junction": "JehangirChowk", "duration": 240, "n_seeds": 2}


@pytest.fixture(autouse=True)
def temp_database(monkeypatch, tmp_path):
    """Every test gets its own throw-away SQLite file and a signed-in client."""
    monkeypatch.setattr(db, "engine", create_engine(f"sqlite:///{tmp_path / 'api.db'}"))
    db.Base.metadata.create_all(db.engine)
    token = client.post("/api/v1/auth/register", json={"username": "tester", "password": "secret123"}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"


def test_health_and_dataset_report():
    assert client.get("/api/v1/health").json()["rows"] == 100000
    body = client.get("/api/v1/dataset").json()
    assert body["kind"] == "observed" and body["report"]["matches_expected_100000"] is True
    assert "all" in [p["id"] for p in body["periods"]["RTOChowk"]]


def test_data_endpoints_need_login_but_health_does_not():
    assert anonymous.get("/api/v1/health").status_code == 200
    for url in ("/api/v1/dataset", "/api/v1/peak-analysis", "/api/v1/history", "/api/v1/model-comparison"):
        assert anonymous.get(url).status_code == 401
    assert anonymous.post("/api/v1/optimize", json={"junction": "RTOChowk"}).status_code == 401


def test_register_and_login_rules():
    assert anonymous.post("/api/v1/auth/login", json={"username": "Tester", "password": "secret123"}).status_code == 200
    assert anonymous.post("/api/v1/auth/login", json={"username": "tester", "password": "wrong-pass"}).status_code == 401
    assert anonymous.post("/api/v1/auth/register", json={"username": "tester", "password": "secret123"}).status_code == 409
    assert anonymous.post("/api/v1/auth/register", json={"username": "ab", "password": "secret123"}).status_code == 400


def test_peak_analysis_and_profile_errors():
    assert client.get("/api/v1/peak-analysis").json()["overall_peak"]["time"] == "11:26"
    assert client.get("/api/v1/scenario-profile", params={"junction": "Nowhere"}).status_code == 404
    assert client.get("/api/v1/scenario-profile", params={"junction": "AlankarChowk", "period": "min:11:23"}).status_code == 400


def test_predict_and_model_comparison():
    body = client.get("/api/v1/predict", params={"junction": "AlankarChowk", "direction": "UP", "horizon": 2}).json()
    assert body["kind"] == "predicted" and body["items"] and body["horizon_s"] == 2
    assert client.get("/api/v1/predict", params={"junction": "AlankarChowk", "direction": "SIDEWAYS"}).status_code == 400
    assert client.get("/api/v1/predict", params={"junction": "Nowhere", "direction": "UP"}).status_code == 404
    names = [m["name"] for m in client.get("/api/v1/model-comparison").json()["models"]]
    assert {"XGBoost", "Linear Regression", "Random Forest", "Baseline: recent rate"} <= set(names)


def test_optimize_respects_constraints_and_validates_input():
    body = client.post("/api/v1/optimize", json={"junction": "RTOChowk", "period": "peak", "source": "predicted"}).json()
    assert sum(body["greens"]) == 104 and all(10 <= g <= 60 for g in body["greens"]) and body["constraints"]["violation_s"] == 0
    assert body["fitness"] <= body["fixed_fitness"] and body["explanation"] and body["limitations"]
    assert client.post("/api/v1/optimize", json={"junction": "RTOChowk", "cycle_length": 30}).status_code == 400
    assert client.post("/api/v1/optimize", json={"junction": "RTOChowk", "source": "manual", "manual_vph": [1, 2]}).status_code == 400
    manual = client.post("/api/v1/optimize", json={"junction": "RTOChowk", "source": "manual", "manual_vph": [100, 900, 100, 100]}).json()
    assert manual["greens"][1] == max(manual["greens"]) and "HYPOTHETICAL" in manual["demand_source"]


def test_experiment_is_reproducible_saved_and_listed():
    first = client.post("/api/v1/experiments", json=SIM).json()
    second = client.post("/api/v1/experiments", json=SIM).json()
    assert first["summary"] == second["summary"]                          # same seeds -> identical results
    assert set(first["summary"]) == {"fixed", "adaptive"} and len(first["saved_ids"]) == 2
    items = client.get("/api/v1/history").json()["items"]
    assert len(items) == 4 and {i["result"]["controller"] for i in items} == {"fixed", "adaptive"}
    assert client.get(f"/api/v1/history/{first['saved_ids'][0]}").json()["result"]["junction"] == "JehangirChowk"
    assert client.get("/api/v1/history/9999").status_code == 404
    assert client.delete("/api/v1/history").json()["deleted"] == 4


def test_simulation_lifecycle_saves_finished_run():
    start = client.post("/api/v1/simulation/start", json={**SIM, "controller": "fixed"}).json()
    assert start["running"] and start["signals"].count("GREEN") == 1
    assert client.post("/api/v1/simulation/step", json={"seconds": 30}).json()["metrics"]["time_s"] == 30
    assert client.post("/api/v1/simulation/pause").json()["running"] is False
    assert client.post("/api/v1/simulation/step", json={"seconds": 30}).json()["metrics"]["time_s"] == 30   # paused: no progress
    assert client.post("/api/v1/simulation/resume").json()["running"] is True
    done = client.post("/api/v1/simulation/step", json={"seconds": 600}).json()
    assert done["finished"] and done["metrics"]["time_s"] == 240
    assert [i["kind"] for i in client.get("/api/v1/history").json()["items"]] == ["simulation"]
    assert client.post("/api/v1/simulation/reset").json()["metrics"]["time_s"] == 0


def test_simulation_websocket_streams_state_and_rejects_anonymous():
    client.post("/api/v1/simulation/start", json={**SIM, "controller": "fixed"})
    token = client.headers["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/simulation?token={token}") as socket:
        socket.send_json({"speed": 20})
        first, second = socket.receive_json(), socket.receive_json()
    assert second["metrics"]["time_s"] > first["metrics"]["time_s"] and len(second["signals"]) == 4
    with anonymous.websocket_connect("/ws/simulation") as socket:
        with pytest.raises(Exception):
            socket.receive_json()
