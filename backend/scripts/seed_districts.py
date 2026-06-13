"""Seed the districts table from an ADM-boundary GeoJSON (run once).

Usage (from backend/):
    python scripts/seed_districts.py ../data/boundaries/geoBoundaries-VNM-ADM1_simplified.geojson
    python scripts/seed_districts.py boundaries.geojson --all   # keep every feature

Boundary source for the pilot: geoBoundaries gbOpen VNM ADM1
(https://www.geoboundaries.org, Public Domain). By default only the 13 Mekong
Delta pilot provinces are kept; names are transliterated to ASCII
("Bạc Liêu" -> "Bac Lieu") because district names are URL path segments and
the dashboard's district keys are ASCII. Re-running upserts geometries in
place (idempotent on the uq_districts_name constraint).
"""

import argparse
import asyncio
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionFactory, engine  # noqa: E402

PILOT_PROVINCES = {
    "An Giang",
    "Bac Lieu",
    "Ben Tre",
    "Ca Mau",
    "Can Tho",
    "Dong Thap",
    "Hau Giang",
    "Kien Giang",
    "Long An",
    "Soc Trang",
    "Tien Giang",
    "Tra Vinh",
    "Vinh Long",
}

# U+0111/U+0110 do not decompose under NFD, unlike the tonal diacritics.
# En/em dashes (e.g. "Bà Rịa – Vũng Tàu") would otherwise be stripped by the
# ASCII encode, gluing the name parts together.
_D_TRANSLATION = str.maketrans({"đ": "d", "Đ": "D", "–": "-", "—": "-"})
_NAME_SUFFIXES = (" province", " city")

_UPSERT_SQL = text("""
    INSERT INTO districts (name, geom)
    VALUES (:name, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326)))
    ON CONFLICT ON CONSTRAINT uq_districts_name
    DO UPDATE SET geom = EXCLUDED.geom
""")


def ascii_name(raw: str) -> str:
    """'Thành phố Cần Thơ' / 'Cần Thơ City' -> 'Can Tho'."""
    value = unicodedata.normalize("NFD", raw.translate(_D_TRANSLATION))
    value = value.encode("ascii", "ignore").decode()
    value = " ".join(value.split())
    value = value.replace(" - ", "-").replace(" -", "-").replace("- ", "-")
    lowered = value.lower()
    for prefix in ("tinh ", "thanh pho "):
        if lowered.startswith(prefix):
            value = value[len(prefix):]
            lowered = value.lower()
    for suffix in _NAME_SUFFIXES:
        if lowered.endswith(suffix):
            value = value[: -len(suffix)]
            lowered = value.lower()
    return value


async def seed(
    geojson_path: Path, include_all: bool
) -> tuple[list[str], list[str], list[str]]:
    collection = json.loads(geojson_path.read_text(encoding="utf-8"))
    seeded: dict[str, str] = {}  # ascii name -> source shapeName
    skipped: list[str] = []
    collisions: list[str] = []
    async with SessionFactory() as session:
        for feature in collection.get("features", []):
            raw_name = feature.get("properties", {}).get("shapeName", "")
            name = ascii_name(raw_name)
            if not name:
                continue
            if not include_all and name not in PILOT_PROVINCES:
                skipped.append(name)
                continue
            # Two source features transliterating to the same ASCII name would
            # silently overwrite each other via the upsert -- keep the first
            # and report the clash instead.
            if name in seeded:
                collisions.append(f"{seeded[name]!r} vs {raw_name!r} -> {name!r}")
                continue
            await session.execute(
                _UPSERT_SQL,
                {"name": name, "geometry": json.dumps(feature["geometry"])},
            )
            seeded[name] = raw_name
        await session.commit()
    await engine.dispose()
    return list(seeded), skipped, collisions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geojson", type=Path, help="Boundary GeoJSON file")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Seed every feature instead of only the pilot provinces.",
    )
    args = parser.parse_args()

    seeded, skipped, collisions = asyncio.run(seed(args.geojson, args.all))
    print(f"Seeded {len(seeded)} district(s): {', '.join(sorted(seeded))}")
    if skipped:
        print(f"Skipped {len(skipped)} non-pilot feature(s)")
    for clash in collisions:
        print(f"WARNING -- name collision, kept the first: {clash}")
    missing = PILOT_PROVINCES - set(seeded)
    if missing and not args.all:
        print(f"WARNING -- pilot provinces not found in input: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
