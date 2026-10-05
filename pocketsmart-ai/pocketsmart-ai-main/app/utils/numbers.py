import math
import re

MAX_AMOUNT = 10**9


def parse_amount(value, default: int = 0) -> int:
    """Turn 1200, 1200.7, '₹1,200' or '1200-1500' (midpoint) into a whole number of rupees."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return default
        return max(0, min(int(value), MAX_AMOUNT))
    nums = re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    if not nums:
        return default
    vals = [float(n) for n in nums[:2]]
    return max(0, min(int(sum(vals) / len(vals)), MAX_AMOUNT))
