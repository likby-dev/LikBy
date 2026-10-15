"""
tests/unit/test_user.py
Unit tests for User entity behavior and transitions.
"""

from tikible.domain.entities.user import User
from tikible.domain.enums import UserState, UserStatus


def test_user_initial_state():
    user = User(id="usr_test", telegram_id=99999)
    assert user.state == UserState.ONBOARDING_AGE_GATE
    assert user.status == UserStatus.ACTIVE
    assert user.age_verified is False
    assert user.karma_score == 100
    assert user.is_eligible_for_matching is False


def test_user_verify_age():
    user = User(id="usr_test", telegram_id=99999)
    user.verify_age()
    assert user.age_verified is True
    assert user.terms_accepted_at is not None
    assert user.state == UserState.ONBOARDING_ALIAS


def test_user_report_penalty_and_suspension():
    user = User(id="usr_test", telegram_id=99999, age_verified=True, state=UserState.MAIN_MENU)
    assert user.status == UserStatus.ACTIVE
    
    # 1st report
    user.apply_report_penalty()
    assert user.report_count == 1
    assert user.karma_score == 85
    assert user.status == UserStatus.ACTIVE

    # 2nd report
    user.apply_report_penalty()
    assert user.report_count == 2
    assert user.karma_score == 70
    assert user.status == UserStatus.ACTIVE

    # 3rd report -> Automatic suspension
    user.apply_report_penalty()
    assert user.report_count == 3
    assert user.karma_score == 55
    assert user.status == UserStatus.SUSPENDED
    assert user.is_eligible_for_matching is False


def test_user_ban():
    user = User(id="usr_test", telegram_id=99999)
    user.ban(reason="Coordinated harassment spam")
    assert user.status == UserStatus.BANNED
    assert user.ban_reason == "Coordinated harassment spam"
    assert user.banned_at is not None
    assert user.is_eligible_for_matching is False
