import pytest

from app.core.submit_rules import DEFAULT_SPORT, MAX_TITLE_LENGTH, SPORTS, check_sport, clean_title
from app.errors import InvalidSportError, ValidationError


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Derby   highlights \n", "Derby highlights"),
        ("Semi-final, 2nd half", "Semi-final, 2nd half"),
        ("", None),
        ("   \t ", None),
        (None, None),
    ],
)
def test_clean_title_tidies_whitespace_and_drops_empty(raw, expected):
    assert clean_title(raw) == expected


def test_clean_title_rejects_titles_over_the_limit():
    assert clean_title("x" * MAX_TITLE_LENGTH) == "x" * MAX_TITLE_LENGTH
    with pytest.raises(ValidationError) as e:
        clean_title("x" * (MAX_TITLE_LENGTH + 1))
    assert e.value.status_code == 422 and "120" in str(e.value)


def test_clean_title_strips_control_characters():
    # Each control character becomes a space (then collapsed), so words never get glued.
    assert clean_title("Match\x00 one\x1b[31m") == "Match one [31m"


@pytest.mark.parametrize("sport", SPORTS)
def test_check_sport_accepts_supported_sports(sport):
    assert check_sport(sport) == sport


def test_check_sport_is_case_insensitive_and_defaults():
    assert check_sport(" Basketball ") == "basketball"
    assert check_sport(None) == DEFAULT_SPORT == "football"
    assert check_sport("") == DEFAULT_SPORT


def test_sports_match_the_database_check_constraint():
    from app.adapters import db_tables

    assert db_tables.SPORTS == SPORTS


def test_check_sport_rejects_others():
    with pytest.raises(InvalidSportError) as e:
        check_sport("cricket")
    assert e.value.code == "INVALID_SPORT" and e.value.status_code == 422
