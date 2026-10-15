"""
tikible.telegram.states
FSM states for user onboarding and conversational flows.
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """User onboarding state machine."""
    waiting_for_age_gate = State()
    waiting_for_alias = State()
    waiting_for_unique_id = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_interests = State()


class EditProfileStates(StatesGroup):
    """Profile editing state machine."""
    waiting_for_new_name = State()


class ReportStates(StatesGroup):
    """Reporting flow state machine."""
    waiting_for_reason = State()
