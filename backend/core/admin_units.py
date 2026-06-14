"""Administrative type for a stored ADM1 name (province vs. city).

Vietnam's ADM1 units are provinces or centrally-governed cities -- never
"districts" (a district is the ADM2 level below them). The data layer keys
everything on ``district_name`` for historical reasons; this maps a name to its
correct type for user-facing labels (the PDF report). Mirrors
``frontend/src/lib/adminUnits.js``.

Of the 63 ADM1 units exactly five are centrally-governed municipalities; every
other unit is a province, so we list the five and default the rest. Names match
the ASCII transliteration the seeder produces (``scripts/seed_districts.py``):
e.g. "Thanh pho Can Tho" -> "Can Tho". Aliases cover alternate spellings.
"""

_CITY_NAMES = frozenset(
    {
        "ha noi",
        "hanoi",
        "hai phong",
        "haiphong",
        "da nang",
        "danang",
        "ho chi minh",
        "ho chi minh city",
        "can tho",
    }
)


def admin_unit_type(name: str) -> str:
    """'City' for the five municipalities, 'Province' for every other unit."""
    normalized = " ".join(str(name or "").split()).lower()
    return "City" if normalized in _CITY_NAMES else "Province"


def admin_unit_noun(name: str) -> str:
    """Lowercase noun for mid-sentence use ('this city', 'city risk')."""
    return admin_unit_type(name).lower()
