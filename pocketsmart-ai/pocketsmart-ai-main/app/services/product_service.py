"""Product & service sourcing.

IMPORTANT: this module does NOT call retailer APIs and has no live prices, stock, ratings or
reviews. It only builds *search links* to shopping/service platforms for an item's search query.
To plug in a real API later, implement a function with the same signature as `build_links`
(or add a provider that returns real listings) - nothing else in the app needs to change.
"""
from urllib.parse import quote_plus

from app.schemas.plan import Link

# platform -> (label, URL template with {q} and optional {loc})
PLATFORMS: dict[str, tuple[str, str]] = {
    "amazon": ("Amazon", "https://www.amazon.in/s?k={q}"),
    "flipkart": ("Flipkart", "https://www.flipkart.com/search?q={q}"),
    "ikea": ("IKEA", "https://www.ikea.com/in/en/search/?q={q}"),
    "swiggy": ("Swiggy", "https://www.swiggy.com/search?query={q}"),
    "zomato": ("Zomato", "https://www.google.com/search?q={q}+site%3Azomato.com"),  # Zomato search URLs are city specific
    "oyo": ("OYO", "https://www.oyorooms.com/search/?location={loc}"),
    "google maps": ("Google Maps", "https://www.google.com/maps/search/?api=1&query={q}"),
    "google": ("Google", "https://www.google.com/search?q={q}"),
    "tanishq": ("Tanishq", "https://www.tanishq.co.in/search?q={q}"),
    "caratlane": ("CaratLane", "https://www.caratlane.com/search?q={q}"),
    "bluestone": ("BlueStone", "https://www.bluestone.com/search.html?query={q}"),
}

DEFAULT_PLATFORMS: dict[str, list[str]] = {
    "home:lighting": ["amazon", "flipkart", "ikea"],
    "home:fans": ["amazon", "flipkart"],
    "home:furniture": ["ikea", "amazon", "flipkart"],
    "home:dining": ["ikea", "amazon", "flipkart"],
    "home:other": ["amazon", "flipkart", "ikea"],
    "party:venue": ["google maps", "oyo"],
    "party:catering": ["swiggy", "zomato"],
    "party:decor": ["amazon", "flipkart"],
    "party:entertainment": ["google", "amazon"],
    "party:misc": ["amazon", "flipkart"],
    "jewelry:pieces": ["amazon", "flipkart", "tanishq", "caratlane", "bluestone"],
}

MAX_LINKS = 5


def _clean_query(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())[:100]


def build_links(planner: str, category_key: str, query: str, preferred: str = "", location: str = "") -> list[Link]:
    """Return search links for `query`. The platform suggested by the AI (if we know it) goes first."""
    q = _clean_query(query) or category_key
    loc = _clean_query(location) or q
    order: list[str] = []
    pref = (preferred or "").strip().lower()
    if pref in PLATFORMS:
        order.append(pref)
    for p in DEFAULT_PLATFORMS.get(f"{planner}:{category_key}", ["google"]):
        if p not in order:
            order.append(p)
    links = []
    for key in order[:MAX_LINKS]:
        label, template = PLATFORMS[key]
        links.append(Link(label=label, url=template.format(q=quote_plus(q), loc=quote_plus(loc))))
    return links
