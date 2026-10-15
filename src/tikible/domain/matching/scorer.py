"""
tikible.domain.matching.scorer
Deterministic compatibility scoring engine for matchmaking tickets.
"""

from typing import List, Optional, Sequence, Set, Tuple
from tikible.domain.enums import Gender, GenderPreference


def check_reciprocal_gender(
    gender_a: Gender,
    pref_a: Sequence[GenderPreference],
    gender_b: Gender,
    pref_b: Sequence[GenderPreference],
) -> bool:
    """Verify mutual gender compatibility."""
    def accepts(prefs: Sequence[GenderPreference], target: Gender) -> bool:
        if GenderPreference.ANY in prefs:
            return True
        return target.value in [p.value for p in prefs]

    return accepts(pref_a, gender_b) and accepts(pref_b, gender_a)


def check_reciprocal_age(
    age_a: int,
    range_a: Tuple[int, int],
    age_b: int,
    range_b: Tuple[int, int],
) -> bool:
    """Verify mutual age range constraints."""
    min_a, max_a = range_a
    min_b, max_b = range_b
    return (min_a <= age_b <= max_a) and (min_b <= age_a <= max_b)


def calculate_match_score(
    user_a_gender: Gender,
    user_a_pref: Sequence[GenderPreference],
    user_a_age: int,
    user_a_age_range: Tuple[int, int],
    user_a_languages: Sequence[str],
    user_a_interests: Sequence[str],
    user_b_gender: Gender,
    user_b_pref: Sequence[GenderPreference],
    user_b_age: int,
    user_b_age_range: Tuple[int, int],
    user_b_languages: Sequence[str],
    user_b_interests: Sequence[str],
) -> Tuple[float, Set[str], Set[str]]:
    """
    Calculate compatibility score between two users.
    Returns (score, common_interests, common_languages).
    If hard filters fail, score is 0.0.
    """
    # 1. Hard Filter: Reciprocal Gender
    if not check_reciprocal_gender(user_a_gender, user_a_pref, user_b_gender, user_b_pref):
        return 0.0, set(), set()

    # 2. Hard Filter: Reciprocal Age
    if not check_reciprocal_age(user_a_age, user_a_age_range, user_b_age, user_b_age_range):
        return 0.0, set(), set()

    # 3. Hard Filter: Language overlap
    langs_a = {l.strip().lower() for l in user_a_languages}
    langs_b = {l.strip().lower() for l in user_b_languages}
    common_langs = langs_a & langs_b
    if not common_langs:
        return 0.0, set(), set()

    # 4. Interest Jaccard Index (Weight: 0.60)
    ints_a = {i.strip().lower() for i in user_a_interests}
    ints_b = {i.strip().lower() for i in user_b_interests}
    common_ints = ints_a & ints_b
    total_ints = ints_a | ints_b

    interest_score = len(common_ints) / len(total_ints) if total_ints else 0.5

    # 5. Age Proximity Score (Weight: 0.20)
    age_diff = abs(user_a_age - user_b_age)
    age_score = max(0.0, 1.0 - (age_diff / 25.0))

    # 6. Language Score (Weight: 0.20)
    lang_score = min(1.0, len(common_langs) / max(1, min(len(langs_a), len(langs_b))))

    final_score = (0.60 * interest_score) + (0.20 * age_score) + (0.20 * lang_score)
    return round(final_score, 4), common_ints, common_langs
