"""Generic SAMPLE suggestions used in demo mode, or when Gemini is unavailable / returns unusable data.
They are deliberately generic (no fake brands) and always flagged `is_sample` in the result."""

SAMPLE_PRICE_FACTOR = 0.9  # sample items use ~90% of the category allocation

HOME = {
    "lighting": [
        ("LED ceiling panel light", "Flush-mount LED panel for even, energy-efficient room lighting.", "led ceiling panel light warm white", 0.6, "Amazon"),
        ("Warm-white LED bulbs / battens", "Efficient LED bulbs or battens for task and accent lighting.", "led bulb warm white 9w", 0.4, "Flipkart"),
    ],
    "fans": [
        ("Energy-saving ceiling fan (1200 mm)", "5-star rated or BLDC ceiling fan sized for a medium room.", "bldc ceiling fan 1200mm", 1.0, "Amazon"),
    ],
    "dining": [
        ("Dining table set", "Dining table with chairs, sized for your household.", "4 seater dining table set", 1.0, "IKEA"),
    ],
    "other": [
        ("Other requested furniture", "Placeholder for the furniture you described.", "", 1.0, "Amazon"),
    ],
}
HOME_FURNITURE_BY_ROOM = {
    "Living Room": [("3-seater sofa", "Comfortable fabric sofa that suits a living room.", "3 seater fabric sofa", 0.55, "IKEA"),
                    ("TV unit / storage cabinet", "Storage-friendly unit for a tidy living space.", "tv unit cabinet", 0.30, "Amazon"),
                    ("Coffee / side table", "Compact table for the seating area.", "coffee table", 0.15, "Flipkart")],
    "Bedroom": [("Bed with storage", "Queen-size bed frame, ideally with under-bed storage.", "queen bed with storage", 0.55, "IKEA"),
                ("Wardrobe", "Sliding or hinged wardrobe sized to the room.", "wardrobe 2 door", 0.30, "Amazon"),
                ("Bedside table", "Small table for the bed side.", "bedside table", 0.15, "Flipkart")],
    "Kitchen": [("Kitchen storage rack / trolley", "Space-saving storage for the kitchen.", "kitchen storage trolley", 0.6, "Amazon"),
                ("Utility cabinet", "Cabinet for appliances and containers.", "kitchen utility cabinet", 0.4, "Flipkart")],
    "Dining Room": [("Dining chairs", "Comfortable matching dining chairs.", "dining chairs set", 0.6, "IKEA"),
                    ("Crockery / sideboard unit", "Storage unit for the dining area.", "crockery cabinet sideboard", 0.4, "Amazon")],
    "Other": [("Multi-purpose storage unit", "Flexible storage furniture.", "storage cabinet", 0.5, "Amazon"),
              ("Accent chair", "Comfortable accent seating.", "accent chair", 0.5, "Flipkart")],
}

PARTY = {
    "venue": [("Party hall / banquet booking", "A hall sized for your guest count; compare quotes from a few venues.", "party hall banquet {location}", 1.0, "Google Maps")],
    "catering": [("Catering for {guests} guests", "Buffet or packaged meals for all guests; confirm the per-plate price in writing.", "catering services {location}", 1.0, "Swiggy")],
    "decor": [("Decoration kit and flowers", "Balloons, banners, lights and simple floral decor for the {event}.", "party decoration kit", 1.0, "Amazon")],
    "entertainment": [("Music / DJ or speaker setup", "Playlist and sound system suited to the event.", "dj sound system rental {location}", 0.6, "Google"),
                      ("Games and activities", "Group games or activities for your guests.", "party games for adults and kids", 0.4, "Amazon")],
    "misc": [("Invitations, return gifts and extras", "Small extras plus a buffer for last-minute needs.", "return gifts party", 1.0, "Amazon")],
}

JEWELRY_MIX = [("Earrings", "Earrings", 0.35), ("Necklace", "Necklace or pendant", 0.45), ("Bracelet", "Bracelet or bangle", 0.20)]
JEWELRY_SEARCH_PLATFORM = {"Earrings": "Amazon", "Necklace": "Tanishq", "Bracelet": "Flipkart"}
