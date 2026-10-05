from tests.conftest import register


def test_register_login_logout_flow(client):
    r = register(client)
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    assert client.get("/dashboard").status_code == 200
    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert client.get("/dashboard", follow_redirects=False).status_code == 303
    bad = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401 and "Incorrect username/email or password" in bad.text
    ok = client.post("/login", data={"username": "alice", "password": "Passw0rd123"}, follow_redirects=False)
    assert ok.status_code == 303
    assert client.get("/dashboard").status_code == 200


def test_login_with_email(client):
    register(client)
    client.post("/logout")
    r = client.post("/login", data={"username": "ALICE@example.com", "password": "Passw0rd123"}, follow_redirects=False)
    assert r.status_code == 303


def test_register_validation_messages(client):
    r = client.post("/register", data={"username": "a", "email": "nope", "password": "short",
                                       "confirm_password": "x"})
    assert r.status_code == 400
    assert "3-30 letters" in r.text and "at least 8 characters" in r.text


def test_register_password_mismatch_and_duplicate(client):
    r = client.post("/register", data={"username": "bob", "email": "bob@example.com", "password": "Passw0rd123",
                                       "confirm_password": "Passw0rd124"})
    assert r.status_code == 400 and "Passwords do not match" in r.text
    register(client)
    client.post("/logout")
    dup = register(client, email="other@example.com")
    assert dup.status_code == 409


def test_passwords_are_hashed(client):
    from app.database import SessionLocal
    from app.models import User
    register(client)
    with SessionLocal() as db:
        u = db.query(User).one()
        assert u.password_hash != "Passw0rd123" and u.password_hash.startswith("$2")


def test_protected_pages_redirect_and_apis_401(client):
    for path in ["/dashboard", "/home-planner", "/party-planner", "/jewelry-planner", "/history", "/history/1"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", path
    assert client.post("/generate-home", json={}).status_code == 401
    assert client.post("/generate-party", json={}).status_code == 401
    assert client.post("/generate-jewelry", data={"total_budget": "1000", "occasion": "Party"}).status_code == 401
    assert client.get("/recommendations/history").status_code == 401
    assert client.get("/recommendations/1").status_code == 401


def test_public_pages_and_health(client):
    for path in ["/", "/login", "/register"]:
        assert client.get(path).status_code == 200
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["ai_mode"] == "demo"
    assert "fake" not in str(h)

def test_health_does_not_expose_api_key(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert "gemini_api_key" not in data
    assert "api_key" not in data
    assert "key" not in data

def test_unknown_page_shows_friendly_404(client):
    r = client.get("/nope", headers={"accept": "text/html"})
    assert r.status_code == 404 and "find that page" in r.text
