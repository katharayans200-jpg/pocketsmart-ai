"""Deterministic budget maths. Nothing here trusts numbers produced by the AI."""
from typing import Any


def allocate(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Split `total` rupees by weight so the parts add up to exactly `total` (largest remainder)."""
    if not weights or total <= 0:
        return {k: 0 for k in weights}
    s = sum(weights.values())
    raw = {k: total * w / s for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    leftover = total - sum(out.values())
    for k, _ in sorted(raw.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True)[:leftover]:
        out[k] += 1
    return out


def fit_quantities(quantities: list[int], target: int) -> list[int]:
    """Adjust item quantities (each >= 1) so they add up to exactly `target`. len(quantities) must be <= target."""
    q = [max(1, int(x)) for x in quantities]
    if not q or target < len(q):
        return q
    while sum(q) > target:
        i = max(range(len(q)), key=lambda j: q[j])
        q[i] -= 1
    q[0] += target - sum(q)
    return q


def fit_to_cap(items: list[dict[str, Any]], cap: int) -> bool:
    """Make sum(unit_price x quantity) <= cap by scaling unit prices down. Returns True if scaled."""
    total = sum(i["unit_price"] * i["quantity"] for i in items)
    if total <= cap or total <= 0:
        return False
    factor = cap / total
    for i in items:
        i["unit_price"] = int(i["unit_price"] * factor)  # floor => never exceeds cap
    return True


def select_within_budget(items: list[dict[str, Any]], budget: int) -> tuple[list[dict[str, Any]], bool]:
    """Drop trailing (lowest priority) pieces until the rest fit; scale only if a single piece is still too dear."""
    kept = list(items)
    dropped = False
    while len(kept) > 1 and sum(i["unit_price"] * i["quantity"] for i in kept) > budget:
        kept.pop()
        dropped = True
    return kept, dropped


def percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole > 0 else 0.0
