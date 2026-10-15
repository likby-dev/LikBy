"""
tests/unit/test_chat_session.py
Unit tests for ChatSession entity.
"""

import pytest
from pydantic import ValidationError
from tikible.domain.entities.chat_session import ChatSession
from tikible.domain.enums import SessionStatus, TerminationReason


def test_chat_session_partner_resolution(sample_chat_session: ChatSession):
    assert sample_chat_session.get_partner_id("usr_0001") == "usr_0002"
    assert sample_chat_session.get_partner_id("usr_0002") == "usr_0001"
    with pytest.raises(ValueError):
        sample_chat_session.get_partner_id("usr_stranger")


def test_same_user_chat_session_rejected():
    with pytest.raises(ValidationError):
        ChatSession(
            id="ses_invalid",
            user_a_id="usr_same",
            user_b_id="usr_same",
        )


def test_record_message(sample_chat_session: ChatSession):
    assert sample_chat_session.message_count == 0
    sample_chat_session.record_message()
    assert sample_chat_session.message_count == 1


def test_end_chat_session(sample_chat_session: ChatSession):
    sample_chat_session.end(ended_by="usr_0001", reason=TerminationReason.USER_STOPPED)
    assert sample_chat_session.status == SessionStatus.ENDED
    assert sample_chat_session.ended_by_user_id == "usr_0001"
    assert sample_chat_session.termination_reason == TerminationReason.USER_STOPPED
    assert sample_chat_session.ended_at is not None
