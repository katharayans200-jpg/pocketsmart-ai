"""Recommendation engine for the three planners.

Flow for every planner:
  1. Python decides the categories and splits the budget (deterministic).
  2. Gemini (if configured) suggests items; its JSON is validated with Pydantic.
  3. Python re-checks quantities, caps every category at its allocation and computes all totals.
  4. If Gemini is not configured / fails / returns unusable data, clearly labelled SAMPLE items are used.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Recommendation, User
from app.schemas import ai as ai_schemas
from app.schemas.home import HomeInput
from app.schemas.jewelry import JewelryInput
from app.schemas.party import PartyInput
from app.schemas.plan import OutfitAnalysis, PlanItem, PlanResult, PlanSection, PlanSummary, RecommendationOut
from app.services import prompts, sample_data
from app.services.budget_service import allocate, fit_quantities, fit_to_cap, percent, select_within_budget
from app.services.gemini_service import GeminiError, ImagePart, get_gemini_service
from app.services.product_service import build_links
from app.utils.images import ProcessedImage

log = logging.getLogger("pocketsmart.recommendations")

DEMO_NOTICE = ("Demo mode: these are generic SAMPLE suggestions, not AI-generated. "
               "Add GEMINI_API_KEY and GEMINI_MODEL to your .env file to get live Gemini recommendations.")
FORCED_DEMO_NOTICE = "Demo mode is switched on (DEMO_MODE=true): these are generic SAMPLE suggestions, not AI-generated."
PRICE_NOTE = ("All prices are estimates (AI-generated or sample), not verified live prices. Links are search links - "
              "check real prices, availability and reviews on each platform before buying.")
DEFAULT_TIPS = ["Compare prices on at least two platforms before buying.",
                "Watch for sale seasons on bigger purchases and keep the remaining budget as a safety buffer."]

HOME_RESERVE = 0.05  # 5% of a home budget is deliberately left unallocated as a buffer


# ----------------------------------------------------------------------------- AI plumbing
def _run_ai(prompt: str, schema: type[BaseModel], image: ProcessedImage | None = None):
    """Returns (parsed | None, source, model, notice)."""
    if not settings.gemini_ready:
        return None, "demo", None, (FORCED_DEMO_NOTICE if settings.demo_mode else DEMO_NOTICE)
    part = ImagePart(data=image.data, mime_type=image.mime_type) if image else None
    try:
        raw = get_gemini_service().generate_json(prompt, part)
    except GeminiError as exc:
        return None, "fallback", None, f"{exc.user_message} Showing generic SAMPLE suggestions instead (not AI-generated)."
    try:
        parsed = schema.model_validate(raw)
    except ValidationError:
        log.warning("Gemini JSON failed schema validation")
        return None, "fallback", None, ("Gemini's reply was incomplete or malformed, so it was not used. "
                                        "Showing generic SAMPLE suggestions instead (not AI-generated).")
    return parsed, "gemini", settings.gemini_model, None


def _norm_key(text: str, rules: list[tuple[str, list[str]]]) -> str | None:
    t = text.lower()
    for key, words in rules:
        if any(w in t for w in words):
            return key
    return None


HOME_RULES = [("other", ["other"]), ("dining", ["dining"]), ("lighting", ["light", "lamp"]),
              ("fans", ["fan"]), ("furniture", ["furnit", "sofa", "bed", "seating"])]
PARTY_RULES = [("venue", ["venue", "hall"]), ("catering", ["cater", "food"]), ("decor", ["decor"]),
               ("entertainment", ["entertain", "music"]), ("misc", ["misc", "other", "extra"])]


# ----------------------------------------------------------------------------- shared section builder
def _make_section(planner: str, key: str, name: str, cap: int, raw_items: list[dict[str, Any]], *,
                  required_qty: int | None = None, is_sample: bool = False, location: str = "",
                  max_items: int = 3, extra_note: str | None = None) -> PlanSection:
    limit = min(max_items, required_qty) if required_qty else max_items
    items = [dict(r) for r in raw_items][:limit]
    if required_qty:
        for r, q in zip(items, fit_quantities([r["quantity"] for r in items], required_qty)):
            r["quantity"] = q
    else:
        for r in items:
            r["quantity"] = max(1, min(int(r["quantity"]), 10))
    total_qty = max(1, sum(r["quantity"] for r in items))
    estimated_missing = False
    for r in items:
        if r["unit_price"] <= 0:
            r["unit_price"] = max(1, int(cap * 0.8 / total_qty))
            estimated_missing = True
    adjusted = fit_to_cap(items, cap)
    plan_items = [
        PlanItem(
            name=r["name"], category=r.get("category", name), description=r.get("description", ""),
            quantity=r["quantity"], unit_price=r["unit_price"], total_price=r["unit_price"] * r["quantity"],
            reason=r.get("reason", ""), platform=r.get("platform") or None,
            links=build_links(planner, key, r.get("search_query") or r["name"], r.get("platform", ""), location),
            price_adjusted=adjusted, is_sample=is_sample,
        )
        for r in items
    ]
    subtotal = sum(i.total_price for i in plan_items)
    notes = [extra_note] if extra_note else []
    if adjusted:
        notes.append("The suggested prices were above this category's allocation, so they were scaled down to fit. "
                     "Real prices may be higher - treat the figure as a target.")
    if estimated_missing:
        notes.append("Some items had no usable price, so the planner estimated one from the allocation.")
    return PlanSection(key=key, name=name, allocation=cap, subtotal=subtotal, remaining=cap - subtotal,
                       note=" ".join(notes) or None, items=plan_items)


def _finish(planner: str, title: str, budget: int, sections: list[PlanSection], source: str, model: str | None,
            notice: str | None, warnings: list[str], tips: list[str],
            outfit: OutfitAnalysis | None = None) -> PlanResult:
    planned = sum(s.subtotal for s in sections)
    if planned > budget:  # cannot happen (every section is capped), but never show an over-budget plan
        raise RuntimeError("Planned total exceeded budget")
    return PlanResult(
        planner=planner, source=source, model=model, notice=notice,
        summary=PlanSummary(title=title, total_budget=budget, planned_total=planned,
                            remaining=budget - planned, percent_used=percent(planned, budget)),
        sections=sections, warnings=warnings, tips=tips or DEFAULT_TIPS, outfit_analysis=outfit,
        price_note=PRICE_NOTE, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _sample_rows(templates: list[tuple], cap: int, qty: int | None, fmt: dict[str, Any], price_is_total: bool = False):
    """Turn sample templates into item dicts that use ~90% of `cap`."""
    chosen = templates[:qty] if qty else templates
    share_sum = sum(t[3] for t in chosen) or 1
    qtys = fit_quantities([1] * len(chosen), qty) if qty else [1] * len(chosen)
    rows = []
    for (name, desc, query, share, platform), q in zip(chosen, qtys):
        budget_for_item = cap * (share / share_sum) * sample_data.SAMPLE_PRICE_FACTOR
        rows.append(dict(name=name.format(**fmt), description=desc.format(**fmt), quantity=q,
                         unit_price=int(budget_for_item // q), reason="Generic sample suggestion (not AI-generated).",
                         search_query=query.format(**fmt) or fmt.get("fallback_query", ""), platform=platform))
    return rows


# ----------------------------------------------------------------------------- HOME
HOME_WEIGHTS = {"lighting": 18, "fans": 22, "furniture": 38, "dining": 27, "other": 15}
ROOM_MULT = {"Kitchen": {"lighting": 1.3, "furniture": 0.7}, "Bedroom": {"furniture": 1.2},
             "Dining Room": {"dining": 1.2}, "Living Room": {"lighting": 1.1}}
UNIT_GUIDE = {"lighting": 150, "fans": 1200, "furniture": 1500, "dining": 3500}  # rough lowest typical INR per unit


def home_categories(inp: HomeInput) -> list[dict[str, Any]]:
    spec = [("lighting", "Lighting", inp.num_lights), ("fans", "Ceiling Fans", inp.num_fans),
            ("furniture", "Furniture", inp.num_furniture), ("dining", "Dining Tables", inp.num_dining_tables)]
    cats = [dict(key=k, name=n, qty=q) for k, n, q in spec if q > 0]
    if inp.other_furniture:
        cats.append(dict(key="other", name="Other Furniture", qty=None))
    for c in cats:
        c["weight"] = HOME_WEIGHTS[c["key"]] * ROOM_MULT.get(inp.room_type, {}).get(c["key"], 1.0)
    return cats


def build_home_plan(inp: HomeInput) -> PlanResult:
    budget = int(inp.total_budget)
    cats = home_categories(inp)
    alloc = allocate(int(budget * (1 - HOME_RESERVE)), {c["key"]: c["weight"] for c in cats})
    parsed, source, model, notice = _run_ai(prompts.home_prompt(inp, cats, alloc), ai_schemas.AIHomePlan)

    ai_items: dict[str, list] = {}
    if parsed:
        for c in parsed.categories:
            key = _norm_key(c.category, HOME_RULES)
            if key:
                ai_items.setdefault(key, []).extend(c.items)

    sections, warnings, sample_used = [], [], []
    for c in cats:
        key, cap, qty = c["key"], alloc[c["key"]], c["qty"]
        if ai_items.get(key):
            rows = [dict(name=i.name, description=i.description, quantity=i.quantity, unit_price=i.unit_price,
                         reason=i.reason, search_query=i.search_query, platform=i.platform) for i in ai_items[key]]
            is_sample = False
        else:
            if key == "furniture":
                tpl = sample_data.HOME_FURNITURE_BY_ROOM[inp.room_type]
            elif key == "other":
                tpl = [("Other requested furniture", "Placeholder for: " + inp.other_furniture[:120],
                        inp.other_furniture[:60], 1.0, "Amazon")]
            else:
                tpl = sample_data.HOME[key]
            rows = _sample_rows(tpl, cap, qty, {"fallback_query": c["name"]})
            is_sample = True
            if parsed:
                sample_used.append(c["name"])
        sections.append(_make_section("home", key, c["name"], cap, rows, required_qty=qty, is_sample=is_sample,
                                      max_items=4 if key == "furniture" else 3))
        floor = UNIT_GUIDE.get(key)
        if floor and qty and cap / qty < floor:
            warnings.append(f"{c['name']}: your allocation of ₹{cap:,} works out to about ₹{cap // qty:,} per unit, "
                            f"which is low for this category (rough guide: ₹{floor:,}+). Consider a larger budget or fewer units.")
    if sample_used:
        warnings.append("Gemini returned nothing usable for: " + ", ".join(sample_used) + ". Sample items are shown there.")
    warnings.append(f"{int(HOME_RESERVE * 100)}% of your budget is kept unallocated as a safety buffer.")
    title = f"Home plan - {inp.room_type}" + (f" (x{inp.num_rooms} rooms)" if inp.num_rooms > 1 else "")
    return _finish("home", title, budget, sections, source, model, notice, warnings, parsed.tips if parsed else [])


# ----------------------------------------------------------------------------- PARTY
PARTY_WEIGHTS = {
    "Wedding": {"venue": 30, "catering": 35, "decor": 20, "entertainment": 10, "misc": 5},
    "Birthday": {"venue": 20, "catering": 40, "decor": 15, "entertainment": 15, "misc": 10},
    "Corporate event": {"venue": 30, "catering": 40, "decor": 5, "entertainment": 10, "misc": 15},
    "Anniversary": {"venue": 25, "catering": 40, "decor": 15, "entertainment": 10, "misc": 10},
    "Other": {"venue": 25, "catering": 40, "decor": 12, "entertainment": 13, "misc": 10},
}
PARTY_NAMES = {"venue": "Venue", "catering": "Catering", "decor": "Decorations",
               "entertainment": "Entertainment", "misc": "Miscellaneous"}
MIN_CATERING_PER_GUEST = 150  # rough guide, INR


def party_categories(inp: PartyInput) -> list[str]:
    keys = []
    if inp.venue_preference != "Home / own venue":
        keys.append("venue")
    if inp.needs_catering:
        keys.append("catering")
    if inp.needs_decoration:
        keys.append("decor")
    if inp.needs_entertainment:
        keys.append("entertainment")
    keys.append("misc")
    return keys


def build_party_plan(inp: PartyInput) -> PlanResult:
    budget = int(inp.total_budget)
    keys = party_categories(inp)
    weights = PARTY_WEIGHTS[inp.event_type]
    alloc = allocate(budget, {k: weights[k] for k in keys})
    cats = [dict(key=k, name=PARTY_NAMES[k]) for k in keys]
    parsed, source, model, notice = _run_ai(prompts.party_prompt(inp, cats, alloc), ai_schemas.AIPartyPlan)

    ai_items: dict[str, list] = {}
    if parsed:
        for c in parsed.categories:
            key = _norm_key(c.category, PARTY_RULES)
            if key:
                ai_items.setdefault(key, []).extend(c.items)

    fmt = {"location": inp.location, "guests": inp.guest_count, "event": inp.event_type.lower(), "fallback_query": ""}
    sections, warnings, sample_used = [], [], []
    for k in keys:
        cap = alloc[k]
        if ai_items.get(k):
            rows = [dict(name=i.name, description=i.description, quantity=1, unit_price=i.estimated_cost,
                         reason=i.reason, search_query=i.search_query, platform=i.platform) for i in ai_items[k]]
            is_sample = False
        else:
            rows = _sample_rows(sample_data.PARTY[k], cap, None, fmt)
            is_sample = True
            if parsed and k != "misc":
                sample_used.append(PARTY_NAMES[k])
        extra = None
        if k == "catering":
            per_guest = cap // inp.guest_count
            extra = f"Allocation works out to about ₹{per_guest:,} per guest."
            if per_guest < MIN_CATERING_PER_GUEST:
                warnings.append(f"Catering: about ₹{per_guest:,} per guest is tight (rough guide: ₹{MIN_CATERING_PER_GUEST}+ per head). "
                                "Consider fewer guests, a simpler menu or a bigger budget.")
        sections.append(_make_section("party", k, PARTY_NAMES[k], cap, rows, is_sample=is_sample,
                                      location=inp.location, extra_note=extra))
    if inp.venue_preference == "Home / own venue":
        warnings.append("No venue budget was allocated because you chose a home / own venue.")
    if sample_used:
        warnings.append("Gemini returned nothing usable for: " + ", ".join(sample_used) + ". Sample items are shown there.")
    title = f"{inp.event_type} for {inp.guest_count} guests"
    return _finish("party", title, budget, sections, source, model, notice, warnings, parsed.tips if parsed else [])


# ----------------------------------------------------------------------------- JEWELRY
def _jewelry_samples(inp: JewelryInput) -> list[dict[str, Any]]:
    budget = int(inp.total_budget)
    metal = "" if inp.metal == "No preference" else inp.metal + " "
    style = inp.style or "versatile"
    if inp.jewelry_type == "Any":
        base = [(t, n, s) for t, n, s in sample_data.JEWELRY_MIX]
    elif inp.jewelry_type == "Matching set":
        base = [("Matching set", "Matching jewelry set", 1.0)]
    else:
        base = [(inp.jewelry_type, f"{inp.jewelry_type} (everyday elegance)", 0.6),
                (inp.jewelry_type, f"{inp.jewelry_type} (statement piece)", 0.4)]
    rows = []
    for jtype, name, share in base:
        title = f"{metal}{name}".strip()
        rows.append(dict(
            name=title[:1].upper() + title[1:], category=jtype,
            description=f"A {style} {title.lower()} for a {inp.occasion.lower()}.",
            quantity=1, unit_price=int(budget * share * sample_data.SAMPLE_PRICE_FACTOR),
            reason=f"Generic sample for a {inp.occasion.lower()} - not matched to your outfit.",
            search_query=f"{metal}{jtype} {inp.occasion}".lower(),
            platform=sample_data.JEWELRY_SEARCH_PLATFORM.get(jtype, "Amazon")))
    return rows


def build_jewelry_plan(inp: JewelryInput, image: ProcessedImage | None = None) -> PlanResult:
    budget = int(inp.total_budget)
    parsed, source, model, notice = _run_ai(prompts.jewelry_prompt(inp, image is not None),
                                            ai_schemas.AIJewelryPlan, image)
    warnings: list[str] = []
    outfit = None
    if parsed:
        rows = [dict(name=i.name, category=i.jewelry_type, description=i.description, quantity=1,
                     unit_price=i.estimated_price, reason=i.compatibility, search_query=i.search_query,
                     platform=i.platform) for i in parsed.items][:5]
        rows, dropped = select_within_budget(rows, budget)
        if dropped:
            warnings.append("Some suggested pieces were left out so the total stays within your budget.")
        is_sample = False
        if image is not None and parsed.outfit_analysis:
            o = parsed.outfit_analysis
            outfit = OutfitAnalysis(colors=o.colors, style=o.style, formality=o.formality, notes=o.notes)
    else:
        rows = _jewelry_samples(inp)
        is_sample = True
        if image is not None:
            warnings.append("Your outfit image was NOT analysed because live Gemini results are unavailable right now.")
    section = _make_section("jewelry", "pieces", "Recommended pieces", budget, rows, is_sample=is_sample,
                            max_items=5)
    if image is not None and parsed and outfit is None:
        warnings.append("Gemini did not return an outfit analysis for your image.")
    if image is not None and outfit is not None:
        warnings.append("The outfit analysis is Gemini's visual impression of your photo, not a precise measurement.")
    title = f"Jewelry for {inp.occasion.lower()}"
    return _finish("jewelry", title, budget, [section], source, model, notice, warnings,
                   parsed.styling_tips if parsed else [], outfit)


# ----------------------------------------------------------------------------- persistence
def save_recommendation(db: Session, user: User, planner: str, input_data: dict, result: PlanResult,
                        image_file: str | None = None) -> Recommendation:
    rec = Recommendation(user_id=user.id, planner_type=planner, input_data=input_data,
                         result_data=result.model_dump(mode="json"), image_path=image_file)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def to_out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(id=rec.id, planner_type=rec.planner_type, created_at=_aware(rec.created_at),
                             input=rec.input_data, result=PlanResult.model_validate(rec.result_data),
                             has_image=bool(rec.image_path))


def history_summary(rec: Recommendation) -> dict[str, Any]:
    r, i = rec.result_data, rec.input_data
    s = r.get("summary", {})
    if rec.planner_type == "home":
        details = f"{i.get('room_type', '')} · {i.get('style', '')}"
    elif rec.planner_type == "party":
        details = f"{i.get('event_type', '')} · {i.get('guest_count', '')} guests · {i.get('location', '')}"
    else:
        details = f"{i.get('occasion', '')} · {i.get('jewelry_type', '')}" + (" · with outfit image" if rec.image_path else "")
    return {"id": rec.id, "planner_type": rec.planner_type, "created_at": _aware(rec.created_at).isoformat(),
            "title": s.get("title", "Plan"), "details": details, "source": r.get("source"),
            "total_budget": s.get("total_budget", 0), "planned_total": s.get("planned_total", 0),
            "remaining": s.get("remaining", 0)}
