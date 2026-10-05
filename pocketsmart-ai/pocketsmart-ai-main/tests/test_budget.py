from app.services.budget_service import allocate, fit_quantities, fit_to_cap, select_within_budget
from app.utils.numbers import parse_amount


def test_allocate_sums_exactly():
    for total in (1000, 9999, 123457, 100000001):
        parts = allocate(total, {"a": 18, "b": 22, "c": 38.5, "d": 27})
        assert sum(parts.values()) == total and all(v >= 0 for v in parts.values())


def test_fit_quantities_hits_target():
    assert sum(fit_quantities([3, 3, 3], 5)) == 5
    assert sum(fit_quantities([1, 1], 6)) == 6
    assert all(q >= 1 for q in fit_quantities([5, 1, 1], 4))


def test_fit_to_cap_never_exceeds():
    items = [{"unit_price": 3333, "quantity": 3}, {"unit_price": 777, "quantity": 7}]
    assert fit_to_cap(items, 10000) is True
    assert sum(i["unit_price"] * i["quantity"] for i in items) <= 10000
    ok = [{"unit_price": 100, "quantity": 2}]
    assert fit_to_cap(ok, 1000) is False and ok[0]["unit_price"] == 100


def test_select_within_budget_drops_last_pieces():
    rows = [{"unit_price": 6000, "quantity": 1}, {"unit_price": 5000, "quantity": 1}, {"unit_price": 4000, "quantity": 1}]
    kept, dropped = select_within_budget(rows, 11000)
    assert dropped and len(kept) == 2


def test_parse_amount():
    assert parse_amount("₹1,200") == 1200
    assert parse_amount("1000-2000") == 1500
    assert parse_amount(None) == 0 and parse_amount("n/a") == 0 and parse_amount(float("nan")) == 0
    assert parse_amount(-5) == 0
def test_parse_amount_with_comma_separated_value():
    assert parse_amount("₹25,000") == 25000
