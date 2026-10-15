"""
tikible.telegram.keyboards
Telegram Reply and Inline keyboard builders for Tikible.
"""

from typing import List, Sequence
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def get_age_gate_keyboard() -> InlineKeyboardMarkup:
    """18+ age verification inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ I am 18 or older", callback_data="age_verify:accept"),
                InlineKeyboardButton(text="❌ I am under 18", callback_data="age_verify:reject"),
            ]
        ]
    )


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Gender selection inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Male", callback_data="gender:MALE"),
                InlineKeyboardButton(text="👩 Female", callback_data="gender:FEMALE"),
            ],
            [
                InlineKeyboardButton(text="🧑 Non-Binary", callback_data="gender:NON_BINARY"),
                InlineKeyboardButton(text="⚪ Prefer Not to Say", callback_data="gender:PREFER_NOT_TO_SAY"),
            ],
        ]
    )


AVAILABLE_INTERESTS = [
    ("☕ Coffee", "coffee"),
    ("📚 Books", "books"),
    ("🎮 Gaming", "gaming"),
    ("💻 Tech", "tech"),
    ("🎵 Music", "music"),
    ("✈️ Travel", "travel"),
    ("🎨 Art", "art"),
    ("🍿 Movies", "movies"),
    ("🏋️ Fitness", "fitness"),
]


def get_interests_keyboard(selected: Sequence[str]) -> InlineKeyboardMarkup:
    """Multi-select interest matrix inline keyboard."""
    buttons = []
    row = []
    for label, code in AVAILABLE_INTERESTS:
        prefix = "✅ " if code in selected else ""
        btn_text = f"{prefix}{label}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"interest_toggle:{code}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    count = len(selected)
    done_text = f"✅ Done ({count} Selected)" if count >= 2 else "Select at least 2 interests"
    buttons.append([InlineKeyboardButton(text=done_text, callback_data="interest_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard for Main Menu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Find a Match")],
            [KeyboardButton(text="👤 My Profile"), KeyboardButton(text="⚙️ Preferences")],
            [KeyboardButton(text="📜 Guidelines"), KeyboardButton(text="❓ Help / About")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_active_chat_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard active during an anonymous conversation."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Play Game"), KeyboardButton(text="⏭ Next Chat")],
            [KeyboardButton(text="🚫 End Chat"), KeyboardButton(text="⚠️ Report")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_queue_cancel_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard shown while waiting in queue."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel Search", callback_data="queue:cancel")]
        ]
    )


def get_tictactoe_keyboard(board: List[List[str]], game_id: str) -> InlineKeyboardMarkup:
    """Renders 3x3 grid for Tic-Tac-Toe."""
    rows = []
    for r in range(3):
        row_btns = []
        for c in range(3):
            cell = board[r][c]
            symbol = "⬜" if cell == "" else ("❌" if cell == "X" else "⭕")
            row_btns.append(
                InlineKeyboardButton(
                    text=symbol,
                    callback_data=f"ttt_move:{game_id}:{r}:{c}",
                )
            )
        rows.append(row_btns)
    return InlineKeyboardMarkup(inline_keyboard=rows)
