"""Province/city classification for ADM1 names (mirrors adminUnits.js)."""

from core.admin_units import admin_unit_noun, admin_unit_type


def test_classifies_the_five_centrally_governed_cities():
    for city in ["Ha Noi", "Hai Phong", "Da Nang", "Ho Chi Minh", "Can Tho"]:
        assert admin_unit_type(city) == "City"


def test_treats_every_other_adm1_unit_as_a_province():
    for province in ["An Giang", "Nghe An", "Vinh Long", "Kien Giang"]:
        assert admin_unit_type(province) == "Province"


def test_is_case_and_whitespace_insensitive_and_tolerates_aliases():
    assert admin_unit_type("  ho chi minh city ") == "City"
    assert admin_unit_type("HANOI") == "City"
    assert admin_unit_type("") == "Province"
    assert admin_unit_type(None) == "Province"  # type: ignore[arg-type]


def test_noun_is_lowercase_for_mid_sentence_use():
    assert admin_unit_noun("Can Tho") == "city"
    assert admin_unit_noun("An Giang") == "province"
