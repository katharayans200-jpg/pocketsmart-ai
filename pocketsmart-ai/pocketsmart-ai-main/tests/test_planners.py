import json

import pytest

from app.services import gemini_service
from app.services.gemini_service import GeminiRateLimit, GeminiService
from tests.conftest import HOME, JEWELRY, PARTY, png_bytes


def _check_invariants(result):
    s = result["summary"]
    assert s["planned_total"] <= s["total_budget"]
    assert s["remaining"] == s["total_budget"] - s["planned_total"]
    assert sum(sec["subtotal"] for sec in result["sections"]) == s["planned_total"]
    assert sum(sec["allocation"] for sec in result["sections"]) <= s["total_budget"]
    for sec in result["sections"]:
        assert sec["subtotal"] <= sec["allocation"]
        assert sec["subtotal"] == sum(i["total_price"] for i in sec["items"])
        for i in sec["items"]:
            assert i["total_price"] == i["quantity"] * i["unit_price"]
            assert i["links"] and all(l["url"].startswith("https://") for l in i["links"])


# ------------------------------------------------------------------ demo mode (no key configured)
def test_home_demo_mode(auth_client):
    r = auth_client.post("/generate-home", json=HOME)
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["source"] == "demo" and "SAMPLE" in res["notice"] and res["model"] is None
    _check_invariants(res)
    names = {s["key"]: s for s in res["sections"]}
    assert set(names) == {"lighting", "fans", "furniture", "dining", "other"}
    assert sum(i["quantity"] for i in names["lighting"]["items"]) == 6
    assert sum(i["quantity"] for i in names["fans"]["items"]) == 2
    assert all(i["is_sample"] for s in res["sections"] for i in s["items"])


def test_party_demo_mode(auth_client):
    r = auth_client.post("/generate-party", json=PARTY)
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["source"] == "demo"
    _check_invariants(res)
    assert [s["key"] for s in res["sections"]] == ["venue", "catering", "decor", "entertainment", "misc"]
    cat = next(s for s in res["sections"] if s["key"] == "catering")
    assert any(l["label"] in ("Swiggy", "Zomato") for l in cat["items"][0]["links"])


def test_party_own_venue_skips_venue(auth_client):
    body = dict(PARTY, venue_preference="Home / own venue", needs_decoration=False)
    res = auth_client.post("/generate-party", json=body).json()["result"]
    assert [s["key"] for s in res["sections"]] == ["catering", "entertainment", "misc"]
    _check_invariants(res)


def test_jewelry_demo_mode_without_image(auth_client):
    r = auth_client.post("/generate-jewelry", data=JEWELRY)
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["source"] == "demo" and res["outfit_analysis"] is None
    _check_invariants(res)


def test_jewelry_image_in_demo_mode_is_not_analysed(auth_client):
    r = auth_client.post("/generate-jewelry", data=JEWELRY, files={"outfit_image": ("o.png", png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["has_image"] is True and body["result"]["outfit_analysis"] is None
    assert any("NOT analysed" in w for w in body["result"]["warnings"])


# ------------------------------------------------------------------ validation
@pytest.mark.parametrize("patch", [{"total_budget": 10}, {"room_type": "Garage"}, {"num_fans": -1},
                                   {"num_lights": 0, "num_fans": 0, "num_furniture": 0, "num_dining_tables": 0, "other_furniture": ""}])
def test_home_validation(auth_client, patch):
    r = auth_client.post("/generate-home", json=dict(HOME, **patch))
    assert r.status_code == 422 and r.json()["detail"]


def test_party_validation(auth_client):
    assert auth_client.post("/generate-party", json=dict(PARTY, guest_count=0)).status_code == 422
    assert auth_client.post("/generate-party", json=dict(PARTY, event_type="Funeral")).status_code == 422
    r = auth_client.post("/generate-party", json=dict(PARTY, location=""))
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "location"


def test_jewelry_validation(auth_client):
    r = auth_client.post("/generate-jewelry", data=dict(JEWELRY, total_budget="50"))
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "total_budget"
    assert auth_client.post("/generate-jewelry", data=dict(JEWELRY, occasion="Nope")).status_code == 422
    assert auth_client.post("/generate-jewelry", data=dict(JEWELRY, total_budget="abc")).status_code == 422


# ------------------------------------------------------------------ image upload
def test_image_wrong_type_rejected(auth_client):
    r = auth_client.post("/generate-jewelry", data=JEWELRY, files={"outfit_image": ("x.gif", png_bytes(), "image/gif")})
    assert r.status_code == 400 and "JPG" in r.json()["detail"]


def test_image_not_really_an_image(auth_client):
    r = auth_client.post("/generate-jewelry", data=JEWELRY, files={"outfit_image": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 400 and "could not be read" in r.json()["detail"]


def test_image_too_large(auth_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 0)  # anything non-empty is too large
    r = auth_client.post("/generate-jewelry", data=JEWELRY, files={"outfit_image": ("x.png", png_bytes(), "image/png")})
    assert r.status_code == 413


def test_empty_file_field_is_treated_as_no_image(auth_client):
    r = auth_client.post("/generate-jewelry", data=JEWELRY, files={"outfit_image": ("", b"", "application/octet-stream")})
    assert r.status_code == 200 and r.json()["has_image"] is False


def test_jpeg_accepted_and_served_back_to_owner(auth_client):
    r = auth_client.post("/generate-jewelry", data=JEWELRY,
                         files={"outfit_image": ("o.jpg", png_bytes(fmt="JPEG"), "image/jpeg")})
    assert r.status_code == 200
    rid = r.json()["id"]
    img = auth_client.get(f"/recommendations/{rid}/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


# ------------------------------------------------------------------ live Gemini path (mocked - no network)
def _fake_generate(payload):
    def f(self, prompt, image=None):
        f.calls.append((prompt, image))
        return payload() if callable(payload) else payload
    f.calls = []
    return f


def test_home_live_over_budget_output_is_capped(auth_client, live, monkeypatch):
    greedy = {"categories": [
        {"category": "lighting", "items": [{"name": "Designer chandelier", "quantity": 6, "unit_price": "₹90,000", "reason": "x", "search_query": "chandelier", "platform": "IKEA"}]},
        {"category": "fans", "items": [{"name": "Fan", "quantity": 2, "unit_price": 1000000}]},
        {"category": "furniture", "items": [{"name": "Sofa", "quantity": 3, "unit_price": 500000}]},
        {"category": "dining", "items": [{"name": "Table", "quantity": 1, "unit_price": 500000}]},
        {"category": "other furniture", "items": [{"name": "Shelf", "quantity": 1, "unit_price": 500000}]}],
        "tips": ["Buy during sales"]}
    fake = _fake_generate(greedy)
    monkeypatch.setattr(GeminiService, "generate_json", fake)
    r = auth_client.post("/generate-home", json=HOME)
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["source"] == "gemini" and res["model"] == "fake-model" and res["tips"] == ["Buy during sales"]
    _check_invariants(res)
    assert any(i["price_adjusted"] for s in res["sections"] for i in s["items"])
    assert not any(i["is_sample"] for s in res["sections"] for i in s["items"])
    assert "USER_INPUT" in fake.calls[0][0] and "hard budget cap" in fake.calls[0][0]


def test_home_live_quantities_corrected(auth_client, live, monkeypatch):
    payload = {"categories": [{"category": "Lighting", "items": [
        {"name": "Panel", "quantity": 1, "unit_price": 500}, {"name": "Bulb", "quantity": 1, "unit_price": 100}]}]}
    monkeypatch.setattr(GeminiService, "generate_json", _fake_generate(payload))
    res = auth_client.post("/generate-home", json=HOME).json()["result"]
    lighting = next(s for s in res["sections"] if s["key"] == "lighting")
    assert sum(i["quantity"] for i in lighting["items"]) == 6 and not lighting["items"][0]["is_sample"]
    fans = next(s for s in res["sections"] if s["key"] == "fans")  # missing from AI reply -> sample + warning
    assert all(i["is_sample"] for i in fans["items"])
    assert any("nothing usable" in w for w in res["warnings"])
    _check_invariants(res)


def test_party_live(auth_client, live, monkeypatch):
    payload = {"categories": [
        {"category": "Venue", "items": [{"name": "Hall", "estimated_cost": "₹5,00,000"}]},
        {"category": "Food & catering", "items": [{"name": "Buffet", "estimated_cost": 12000, "platform": "Zomato"}]},
        {"category": "Decor", "items": [{"name": "Balloons", "estimated_cost": 3000}]},
        {"category": "Entertainment", "items": [{"name": "DJ", "estimated_cost": 5000}]},
        {"category": "Misc", "items": [{"name": "Gifts", "estimated_cost": 2000}]}]}
    monkeypatch.setattr(GeminiService, "generate_json", _fake_generate(payload))
    res = auth_client.post("/generate-party", json=PARTY).json()["result"]
    assert res["source"] == "gemini"
    _check_invariants(res)
    venue = res["sections"][0]
    assert venue["items"][0]["price_adjusted"] and venue["items"][0]["total_price"] <= venue["allocation"]


def test_jewelry_live_with_image_and_budget_cap(auth_client, live, monkeypatch):
    payload = {"outfit_analysis": {"colors": ["red", "gold"], "style": "ethnic", "formality": "formal", "notes": "silk saree"},
               "items": [{"jewelry_type": "Necklace", "name": "Temple necklace", "estimated_price": 15000, "compatibility": "Matches red", "platform": "Tanishq"},
                         {"jewelry_type": "Earrings", "name": "Jhumkas", "estimated_price": "₹9,000"},
                         {"jewelry_type": "Bangles", "name": "Gold bangles", "estimated_price": 20000}],
               "styling_tips": ["Keep it simple"]}
    fake = _fake_generate(payload)
    monkeypatch.setattr(GeminiService, "generate_json", fake)
    r = auth_client.post("/generate-jewelry", data=JEWELRY, files={"outfit_image": ("o.png", png_bytes(), "image/png")})
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["source"] == "gemini" and res["outfit_analysis"]["colors"] == ["red", "gold"]
    _check_invariants(res)
    assert len(res["sections"][0]["items"]) == 2  # third piece dropped to stay within ₹25,000
    assert fake.calls[0][1] is not None and fake.calls[0][1].mime_type == "image/jpeg"


@pytest.mark.parametrize("bad", [{"unexpected": "shape"}, {"categories": []}, {"categories": "oops"}])
def test_invalid_gemini_json_falls_back(auth_client, live, monkeypatch, bad):
    monkeypatch.setattr(GeminiService, "generate_json", _fake_generate(bad))
    res = auth_client.post("/generate-home", json=HOME).json()["result"]
    assert res["source"] == "fallback" and "malformed" in res["notice"]
    _check_invariants(res)


def test_gemini_rate_limit_falls_back_with_message(auth_client, live, monkeypatch):
    def boom(self, prompt, image=None):
        raise GeminiRateLimit("Gemini's rate limit or quota was reached. Wait a minute and try again.")
    monkeypatch.setattr(GeminiService, "generate_json", boom)
    res = auth_client.post("/generate-party", json=PARTY).json()["result"]
    assert res["source"] == "fallback" and "rate limit" in res["notice"]
    assert res["model"] is None
    _check_invariants(res)


def test_demo_mode_flag_forces_demo(auth_client, live, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(GeminiService, "generate_json", lambda *a, **k: pytest.fail("Gemini must not be called"))
    res = auth_client.post("/generate-home", json=HOME).json()["result"]
    assert res["source"] == "demo"
