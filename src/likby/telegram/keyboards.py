"""
likby.telegram.keyboards
Telegram Reply and Inline keyboard builders for LikBy.
"""

from typing import List, Optional, Sequence
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
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
    """Persistent reply keyboard for LikBy Main Menu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Find Someone"), KeyboardButton(text="💬 My Chats")],
            [KeyboardButton(text="💙 Who Liked Me"), KeyboardButton(text="👥 My Friends")],
            [KeyboardButton(text="🔍 Search ID"), KeyboardButton(text="📬 Requests")],
            [KeyboardButton(text="👤 My Profile"), KeyboardButton(text="🌟 My Karma")],
            [KeyboardButton(text="💎 Subscription"), KeyboardButton(text="🎮 LikBy Play")],
            [KeyboardButton(text="🕹 Solo Arcade"), KeyboardButton(text="🛡 Help & Safety")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_post_session_keyboard(session_id: str, partner_id: str) -> InlineKeyboardMarkup:
    """Post-session evaluation and actions keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Good Chat (+1)", callback_data=f"rate:{session_id}:like"),
                InlineKeyboardButton(text="👎 Poor (-1)", callback_data=f"rate:{session_id}:dislike"),
            ],
            [
                InlineKeyboardButton(text="💙 Express Like (Friendship)", callback_data=f"social_like:{session_id}:{partner_id}"),
            ],
            [
                InlineKeyboardButton(text="📜 Export Transcript (.txt)", callback_data=f"transcript:export:{session_id}"),
            ],
            [
                InlineKeyboardButton(text="🎲 Find New Match", callback_data="queue:find_new"),
            ],
        ]
    )


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Authoritative subscription and tier upgrade keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ LikBy Spark — 15 ⭐️ (24h)", callback_data="sub:buy:SPARK"),
            ],
            [
                InlineKeyboardButton(text="🌟 LikBy Premium — 60 ⭐️ (30d)", callback_data="sub:buy:PREMIUM"),
            ],
            [
                InlineKeyboardButton(text="👑 LikBy Diamond — 120 ⭐️ (30d)", callback_data="sub:buy:DIAMOND"),
            ],
            [
                InlineKeyboardButton(text="🎁 Earn Free Spark (Invite Friends)", callback_data="sub:invite"),
            ],
            [
                InlineKeyboardButton(text="📊 My Plan & Quotas", callback_data="sub:myplan"),
                InlineKeyboardButton(text="🧾 History", callback_data="sub:history"),
            ],
            [
                InlineKeyboardButton(text="📜 Terms & Refunds", callback_data="sub:terms"),
                InlineKeyboardButton(text="💬 Pay Support", callback_data="sub:paysupport"),
            ],
        ]
    )


def get_plan_card_keyboard(plan_code: str) -> InlineKeyboardMarkup:
    """Action button for a specific plan card."""
    buttons = []
    if plan_code.upper() != "BASE":
        buttons.append([InlineKeyboardButton(text=f"⭐️ Get {plan_code.title()}", callback_data=f"sub:buy:{plan_code.upper()}")])
    buttons.append([
        InlineKeyboardButton(text="📋 All Plans", callback_data="sub:plans"),
        InlineKeyboardButton(text="📊 My Plan", callback_data="sub:myplan"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_referral_keyboard() -> InlineKeyboardMarkup:
    """Invite & referral sharing keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Buy Spark Pass (15 ⭐️)", callback_data="sub:buy:SPARK"),
            ],
            [
                InlineKeyboardButton(text="💎 View All Plans", callback_data="sub:plans"),
                InlineKeyboardButton(text="📊 My Plan", callback_data="sub:myplan"),
            ],
        ]
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
            [InlineKeyboardButton(text="🕹 Play While Waiting", callback_data="solo:hub")],
            [InlineKeyboardButton(text="❌ Cancel Search", callback_data="queue:cancel")],
        ]
    )


def get_solo_hub_keyboard() -> InlineKeyboardMarkup:
    """Arcade selector for single-player casual mini-games."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Trivia Blitz", callback_data="solo:trivia:new")],
            [InlineKeyboardButton(text="💎 Gem Hunter (Mini Mines)", callback_data="solo:gem:new")],
            [InlineKeyboardButton(text="🪨 Rock Paper Scissors", callback_data="solo:rps:new")],
            [InlineKeyboardButton(text="❌ Close Arcade", callback_data="solo:close")],
        ]
    )


def get_trivia_keyboard(q_idx: int, options: Sequence[str]) -> InlineKeyboardMarkup:
    """Multiple choice options for Trivia Blitz."""
    buttons = []
    for opt_idx, opt_text in enumerate(options):
        buttons.append(
            [InlineKeyboardButton(text=opt_text, callback_data=f"trivia_ans:{q_idx}:{opt_idx}")]
        )
    buttons.append([InlineKeyboardButton(text="🏠 Solo Arcade", callback_data="solo:hub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_gem_hunter_keyboard(game, show_all: bool = False) -> InlineKeyboardMarkup:
    """Renders 3x3 grid for Gem Hunter."""
    rows = []
    for r in range(3):
        row_btns = []
        for c in range(3):
            if game.revealed[r][c] or show_all:
                if r == game.bomb_row and c == game.bomb_col:
                    symbol = "💥 Bomb!"
                else:
                    symbol = "💎 +10"
            else:
                symbol = "❓ Tile"
            row_btns.append(
                InlineKeyboardButton(
                    text=symbol,
                    callback_data=f"gem_pick:{r}:{c}",
                )
            )
        rows.append(row_btns)

    controls = []
    if not game.is_over and game.score > 0:
        controls.append(InlineKeyboardButton(text=f"💰 Cash Out ({game.score} pts)", callback_data="gem:cashout"))
    controls.append(InlineKeyboardButton(text="🔄 New Game", callback_data="solo:gem:new"))
    controls.append(InlineKeyboardButton(text="🏠 Arcade", callback_data="solo:hub"))
    rows.append(controls)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_play_hub_keyboard(mini_app_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    LikBy Play Ecosystem Navigation Keyboard.
    Uses WebAppInfo when mini_app_url is provided, with fallback inline actions.
    """
    if mini_app_url:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚔️ Play Together (11 Duels)",
                        web_app=WebAppInfo(url=f"{mini_app_url}#duels"),
                    ),
                    InlineKeyboardButton(
                        text="🧩 Play Solo (6 Games)",
                        web_app=WebAppInfo(url=f"{mini_app_url}#solo"),
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="✨ Game Collection",
                        web_app=WebAppInfo(url=f"{mini_app_url}#catalogue"),
                    ),
                    InlineKeyboardButton(
                        text="📊 My Progress",
                        web_app=WebAppInfo(url=f"{mini_app_url}#progress"),
                    ),
                ],
                [
                    InlineKeyboardButton(text="💎 My Plan & Quota", callback_data="sub:myplan"),
                ],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ Play Together (11 Duels)", callback_data="play:duels"),
                InlineKeyboardButton(text="🧩 Play Solo (6 Games)", callback_data="play:solo"),
            ],
            [
                InlineKeyboardButton(text="✨ Game Collection", callback_data="play:catalogue"),
                InlineKeyboardButton(text="📊 My Progress", callback_data="play:progress"),
            ],
            [
                InlineKeyboardButton(text="💎 My Plan & Quota", callback_data="sub:myplan"),
            ],
        ]
    )


def get_rps_keyboard() -> InlineKeyboardMarkup:
    """Action buttons for Rock Paper Scissors."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🪨 Rock", callback_data="rps_play:ROCK"),
                InlineKeyboardButton(text="📄 Paper", callback_data="rps_play:PAPER"),
                InlineKeyboardButton(text="✂️ Scissors", callback_data="rps_play:SCISSORS"),
            ],
            [InlineKeyboardButton(text="🏠 Solo Arcade", callback_data="solo:hub")],
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
