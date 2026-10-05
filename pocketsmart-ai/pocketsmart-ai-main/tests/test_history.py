import re
from pathlib import Path

from app.main import app
from tests.conftest import HOME, JEWELRY, PARTY, register

ROOT = Path(__file__).resolve().parent.parent


def test_history_persists_and_orders(auth_client):
    a = auth_client.post("/generate-home", json=HOME).json()["id"]
    b = auth_client.post("/generate-party", json=PARTY).json()["id"]
    c = auth_client.post("/generate-jewelry", data=JEWELRY).json()["id"]
    h = auth_client.get("/recommendations/history").json()
    assert h["count"] == 3 and [i["id"] for i in h["items"]] == [c, b, a]
    assert {i["planner_type"] for i in h["items"]} == {"home", "party", "jewelry"}
    only = auth_client.get("/recommendations/history", params={"planner": "party"}).json()
    assert [i["id"] for i in only["items"]] == [b]
    assert auth_client.get("/recommendations/history", params={"planner": "bogus"}).status_code == 422


def test_detail_returns_saved_input_and_result(auth_client):
    rid = auth_client.post("/generate-home", json=HOME).json()["id"]
    d = auth_client.get(f"/recommendations/{rid}").json()
    assert d["planner_type"] == "home" and d["input"]["total_budget"] == HOME["total_budget"]
    assert d["result"]["summary"]["total_budget"] == 60000
    assert d["created_at"].endswith("Z") or "+00:00" in d["created_at"]


def test_detail_and_history_pages_render(auth_client):
    rid = auth_client.post("/generate-party", json=PARTY).json()["id"]
    assert auth_client.get("/history").status_code == 200
    page = auth_client.get(f"/history/{rid}")
    assert page.status_code == 200 and f'data-rec-id="{rid}"' in page.text
    dash = auth_client.get("/dashboard")
    assert "Birthday for 30 guests" in dash.text


def test_users_cannot_see_each_others_recommendations(client):
    register(client, "alice", "alice@example.com")
    rid = client.post("/generate-home", json=HOME).json()["id"]
    client.post("/logout")
    register(client, "bob", "bob@example.com")
    assert client.get(f"/recommendations/{rid}").status_code == 404
    assert client.get(f"/recommendations/{rid}/image").status_code == 404
    assert client.get(f"/history/{rid}", headers={"accept": "text/html"}).status_code == 404
    assert client.get("/recommendations/history").json()["count"] == 0
    assert "Home plan" not in client.get("/dashboard").text


def test_nonexistent_recommendation_404(auth_client):
    assert auth_client.get("/recommendations/9999").status_code == 404
    assert auth_client.get("/recommendations/abc").status_code == 422


# ---------------- frontend <-> backend wiring
def test_planner_forms_point_to_real_post_routes(auth_client):
    post_routes = {p for p, ops in app.openapi()["paths"].items() if "post" in ops}
    for page, endpoint in [("/home-planner", "/generate-home"), ("/party-planner", "/generate-party"),
                           ("/jewelry-planner", "/generate-jewelry")]:
        html = auth_client.get(page).text
        assert f'data-endpoint="{endpoint}"' in html and endpoint in post_routes


def test_form_field_names_match_backend_schemas(auth_client):
    from app.schemas.home import HomeInput
    from app.schemas.party import PartyInput
    from app.schemas.jewelry import JewelryInput
    for page, model in [("/home-planner", HomeInput), ("/party-planner", PartyInput), ("/jewelry-planner", JewelryInput)]:
        html = auth_client.get(page).text
        names = set(re.findall(r'name="([a-z_]+)"', html))
        assert set(model.model_fields) <= names, (page, set(model.model_fields) - names)


def test_auth_forms_post_to_real_routes(client):
    assert 'action="/login"' in client.get("/login").text
    assert 'action="/register"' in client.get("/register").text


def test_required_routes_exist():
    have = {(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops}
    for m, p in [("POST", "/register"), ("POST", "/login"), ("POST", "/logout"), ("GET", "/"), ("GET", "/dashboard"),
                 ("GET", "/home-planner"), ("GET", "/party-planner"), ("GET", "/jewelry-planner"), ("GET", "/history"),
                 ("POST", "/generate-home"), ("POST", "/generate-party"), ("POST", "/generate-jewelry"),
                 ("GET", "/recommendations/history"), ("GET", "/recommendations/{recommendation_id}"), ("GET", "/health")]:
        assert (m, p) in have, (m, p)


def test_no_secrets_in_project_files():
    assert not (ROOT / ".env").exists()
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".md", ".txt", ".html", ".js", ".example"} and ".venv" not in p.parts:
            assert ("AI" + "za") not in p.read_text(errors="ignore"), p
