"""Logika Impact Tracker (Modul E).
"""

BADGES = [
    {"name": "Mulai Bener", "min": 1, "icon": "images/badges/thumb-up.svg"},
    {"name": "Makin Bener", "min": 5, "icon": "images/badges/trash-off.svg"},
    {"name": "Paham Bener", "min": 10, "icon": "images/badges/battery-4.svg"},
    {"name": "Bener Banget", "min": 25, "icon": "images/badges/flame.svg"},
]


def get_impact_summary(saved_count):
    """badge progress"""
    badges = [{**b, "unlocked": saved_count >= b["min"]} for b in BADGES]

    current_badge = None
    next_badge = None
    for badge in badges:
        if badge["unlocked"]:
            current_badge = badge
        elif next_badge is None:
            next_badge = badge

    if next_badge is None:
        progress_percent = 100
        remaining = 0
    else:
        progress_percent = int(saved_count / next_badge["min"] * 100)
        remaining = next_badge["min"] - saved_count

    return {
        "saved_count": saved_count,
        "badges": badges,
        "current_badge": current_badge,
        "next_badge": next_badge,
        "progress_percent": progress_percent,
        "remaining": remaining,
    }