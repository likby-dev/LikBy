"""
tests/unit/test_scorer.py
Unit tests for the deterministic compatibility scoring engine.
"""

from likby.domain.enums import Gender, GenderPreference
from likby.domain.matching.scorer import calculate_match_score


def test_perfect_compatible_pair():
    score, common_ints, common_langs = calculate_match_score(
        user_a_gender=Gender.MALE,
        user_a_pref=[GenderPreference.FEMALE, GenderPreference.ANY],
        user_a_age=25,
        user_a_age_range=(20, 30),
        user_a_languages=["en", "es"],
        user_a_interests=["coding", "gaming", "music"],
        user_b_gender=Gender.FEMALE,
        user_b_pref=[GenderPreference.MALE],
        user_b_age=25,
        user_b_age_range=(20, 30),
        user_b_languages=["en"],
        user_b_interests=["gaming", "coding", "music"],
    )
    assert score >= 0.95
    assert common_ints == {"coding", "gaming", "music"}
    assert common_langs == {"en"}


def test_reciprocal_gender_mismatch_yields_zero():
    # User A wants FEMALE only; User B is MALE
    score, _, _ = calculate_match_score(
        user_a_gender=Gender.MALE,
        user_a_pref=[GenderPreference.FEMALE],
        user_a_age=25,
        user_a_age_range=(20, 30),
        user_a_languages=["en"],
        user_a_interests=["gaming"],
        user_b_gender=Gender.MALE,
        user_b_pref=[GenderPreference.ANY],
        user_b_age=26,
        user_b_age_range=(20, 30),
        user_b_languages=["en"],
        user_b_interests=["gaming"],
    )
    assert score == 0.0


def test_age_out_of_range_yields_zero():
    # User A requires partner age <= 30; User B is 35
    score, _, _ = calculate_match_score(
        user_a_gender=Gender.NON_BINARY,
        user_a_pref=[GenderPreference.ANY],
        user_a_age=25,
        user_a_age_range=(20, 30),
        user_a_languages=["en"],
        user_a_interests=["coffee"],
        user_b_gender=Gender.FEMALE,
        user_b_pref=[GenderPreference.ANY],
        user_b_age=35,
        user_b_age_range=(20, 40),
        user_b_languages=["en"],
        user_b_interests=["coffee"],
    )
    assert score == 0.0


def test_no_common_languages_yields_zero():
    # User A speaks only EN; User B speaks only JA
    score, _, _ = calculate_match_score(
        user_a_gender=Gender.NON_BINARY,
        user_a_pref=[GenderPreference.ANY],
        user_a_age=25,
        user_a_age_range=(20, 30),
        user_a_languages=["en"],
        user_a_interests=["art"],
        user_b_gender=Gender.MALE,
        user_b_pref=[GenderPreference.ANY],
        user_b_age=26,
        user_b_age_range=(20, 30),
        user_b_languages=["ja"],
        user_b_interests=["art"],
    )
    assert score == 0.0
