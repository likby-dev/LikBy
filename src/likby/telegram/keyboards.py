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


def _normalize_mini_app_url(url: Optional[str]) -> Optional[str]:
    """Ensures WebApp URLs point to active likby.onrender.com domain and heals legacy hostnames."""
    if not url:
        return None
    url = url.strip()
    if "likby-app.onrender.com" in url:
        url = url.replace("likby-app.onrender.com", "likby.onrender.com")
    return url


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
    """
    World-class 5-button persistent main menu keyboard for LikBy.
    Row 1: [ 🎲 Find Match ] (Hero CTA)
    Row 2: [ 💬 My Chats ]   [ 👥 Connections ]
    Row 3: [ 🎮 LikBy Play ] [ 👤 Profile & VIP ]
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Find Match")],
            [KeyboardButton(text="💬 My Chats"), KeyboardButton(text="👥 Connections")],
            [KeyboardButton(text="🎮 LikBy Play"), KeyboardButton(text="👤 Profile & VIP")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_connections_hub_keyboard(
    friends_count: int = 0,
    requests_count: int = 0,
    likes_count: int = 0,
) -> InlineKeyboardMarkup:
    """Consolidated Social & Connections Hub interactive dashboard."""
    friends_label = f"👥 Friends ({friends_count})" if friends_count > 0 else "👥 My Friends"
    requests_label = f"📬 Requests ({requests_count}) 🔔" if requests_count > 0 else "📬 Requests"
    likes_label = f"💙 Who Liked Me ({likes_count}) ✨" if likes_count > 0 else "💙 Who Liked Me"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=friends_label, callback_data="conn:friends"),
                InlineKeyboardButton(text=requests_label, callback_data="conn:requests"),
            ],
            [
                InlineKeyboardButton(text=likes_label, callback_data="conn:likes"),
                InlineKeyboardButton(text="🔍 Search ID", callback_data="conn:search"),
            ],
            [
                InlineKeyboardButton(text="🎁 Invite Friends (Free Spark Pass)", callback_data="sub:invite"),
            ],
        ]
    )


def get_profile_vip_keyboard(tier_code: str = "BASE") -> InlineKeyboardMarkup:
    """Consolidated Profile & VIP Membership Hub interactive dashboard."""
    upgrade_btn_text = "👑 VIP Plans & Upgrades" if tier_code.upper() == "BASE" else f"💎 Manage {tier_code.title()} Tier"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Edit Display Name", callback_data="profile:edit_name"),
                InlineKeyboardButton(text="🌟 Karma Reputation", callback_data="vip:karma"),
            ],
            [
                InlineKeyboardButton(text=upgrade_btn_text, callback_data="sub:plans"),
                InlineKeyboardButton(text="📊 Quotas & Usage", callback_data="sub:myplan"),
            ],
            [
                InlineKeyboardButton(text="🛡 Safety & Guidelines", callback_data="vip:safety"),
                InlineKeyboardButton(text="💬 Support & Help", callback_data="sub:paysupport"),
            ],
        ]
    )


def get_chat_hub_keyboard(
    is_active: bool = False,
    session_id: Optional[str] = None,
    mini_app_url: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Conversation Hub interactive controls."""
    mini_app_url = _normalize_mini_app_url(mini_app_url)
    if is_active:
        play_btn = (
            InlineKeyboardButton(text="⚔️ Play Duel with Partner", web_app=WebAppInfo(url=mini_app_url))
            if mini_app_url
            else InlineKeyboardButton(text="⚔️ Play Duel with Partner", callback_data="chat:game")
        )
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    play_btn,
                    InlineKeyboardButton(text="⏭ Next Chat", callback_data="chat:next"),
                ],
                [
                    InlineKeyboardButton(text="📜 Export Transcript", callback_data=f"transcript:export:{session_id}" if session_id else "chat:transcript"),
                    InlineKeyboardButton(text="🚫 End Conversation", callback_data="chat:end"),
                ],
            ]
        )
    play_btn = (
        InlineKeyboardButton(text="🚀 LikBy Play (App)", web_app=WebAppInfo(url=mini_app_url))
        if mini_app_url and mini_app_url.startswith("https://")
        else InlineKeyboardButton(text="🎮 LikBy Play", callback_data="play:hub")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎲 Find a Match Now", callback_data="queue:find_new"),
            ],
            [
                InlineKeyboardButton(text="🧩 Solo Games", callback_data="play:solo_info"),
                play_btn,
            ],
            [
                InlineKeyboardButton(text="👥 My Friends", callback_data="conn:friends"),
            ],
        ]
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
            [
                InlineKeyboardButton(text="« Back to Profile Hub", callback_data="vip:hub"),
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
    buttons.append([
        InlineKeyboardButton(text="« Back to Profile Hub", callback_data="vip:hub"),
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
            [
                InlineKeyboardButton(text="« Back to Connections", callback_data="conn:hub"),
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


def get_queue_cancel_keyboard(mini_app_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Inline keyboard shown while waiting in queue."""
    mini_app_url = _normalize_mini_app_url(mini_app_url)
    play_btn = (
        InlineKeyboardButton(text="🚀 Play While Waiting (App)", web_app=WebAppInfo(url=mini_app_url))
        if mini_app_url
        else InlineKeyboardButton(text="🎮 LikBy Play (App)", callback_data="play:hub")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [play_btn],
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
            [
                InlineKeyboardButton(text="« Back to Games Hub", callback_data="play:hub"),
                InlineKeyboardButton(text="❌ Close", callback_data="solo:close"),
            ],
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
    Consolidated LikBy Play Ecosystem Navigation Keyboard.
    Clean presentation without redundant open mini button or game counts.
    """
    rows = []
    rows.append([
        InlineKeyboardButton(text="⚔️ 2-Player Duels", callback_data="play:duels"),
        InlineKeyboardButton(text="🧩 Solo Games", callback_data="play:solo_info"),
    ])
    rows.append([
        InlineKeyboardButton(text="✨ Games Catalog & Rules", callback_data="play:catalogue"),
        InlineKeyboardButton(text="📊 My Progress & Quotas", callback_data="play:progress"),
    ])
    rows.append([
        InlineKeyboardButton(text="💎 Upgrade Gaming Quota (VIP)", callback_data="sub:plans"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_solo_games_keyboard(mini_app_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Dedicated interactive launcher keyboard for all 6 official LikBy Solo Games.
    Provides direct 1-tap game launch via Telegram WebApp and interactive cards.
    """
    mini_app_url = _normalize_mini_app_url(mini_app_url)
    is_https = bool(mini_app_url and mini_app_url.startswith("https://"))

    def _btn(label: str, game_id: str) -> InlineKeyboardButton:
        if is_https:
            clean_base = mini_app_url.split("?")[0].rstrip("/")
            game_url = f"{clean_base}?game={game_id}"
            return InlineKeyboardButton(text=label, web_app=WebAppInfo(url=game_url))
        return InlineKeyboardButton(text=label, callback_data=f"play:solo_card:{game_id}")

    rows = [
        [
            _btn("🧘 1. Zen Merge", "zen_merge"),
            _btn("🔤 2. Word Hunt", "word_hunt"),
        ],
        [
            _btn("🎨 3. Color Flow", "color_flow"),
            _btn("⛳️ 4. Pocket Golf", "pocket_golf"),
        ],
        [
            _btn("⚡️ 5. Reflex Lab", "reflex_lab"),
            _btn("🔍 6. Daily Mystery", "daily_mystery"),
        ],
    ]

    rows.append([
        InlineKeyboardButton(text="🏠 Gaming Hub", callback_data="play:hub"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_solo_game_card_keyboard(game_id: str, mini_app_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Action keyboard for a specific solo game card."""
    mini_app_url = _normalize_mini_app_url(mini_app_url)
    rows = []
    if mini_app_url and mini_app_url.startswith("https://"):
        clean_base = mini_app_url.split("?")[0].rstrip("/")
        game_url = f"{clean_base}?game={game_id}"
        rows.append([
            InlineKeyboardButton(text="🚀 Play in LikBy Play (Mini App)", web_app=WebAppInfo(url=game_url))
        ])

    rows.append([
        InlineKeyboardButton(text="« Back to Solo Games", callback_data="play:solo_info"),
        InlineKeyboardButton(text="🏠 Gaming Hub", callback_data="play:hub"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_duel_games_keyboard(mini_app_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Dedicated interactive selector keyboard for all 12 official LikBy Multiplayer Duels.
    Provides clickable buttons for every single duel game with detail cards & instant launch.
    """
    mini_app_url = _normalize_mini_app_url(mini_app_url)
    is_https = bool(mini_app_url and mini_app_url.startswith("https://"))

    def _btn(label: str, game_id: str) -> InlineKeyboardButton:
        if is_https:
            clean_base = mini_app_url.split("?")[0].rstrip("/")
            game_url = f"{clean_base}?game={game_id}"
            return InlineKeyboardButton(text=label, web_app=WebAppInfo(url=game_url))
        return InlineKeyboardButton(text=label, callback_data=f"play:duel_card:{game_id}")

    rows = [
        [
            _btn("🔴 1. Connect Four", "connect_four"),
            _btn("🎯 2. Carrom Clash", "carrom_clash"),
        ],
        [
            _btn("🏒 3. Air Rush", "air_rush"),
            _btn("🎱 4. Pocket Pool", "pocket_pool"),
        ],
        [
            _btn("🤺 5. Stick Arena", "stick_arena"),
            _btn("🎨 6. QuickDraw", "quickdraw"),
        ],
        [
            _btn("🔤 7. Word Rush", "word_rush"),
            _btn("🧠 8. Brain Blitz", "brain_blitz"),
        ],
        [
            _btn("⚡️ 9. Reflex Rush", "reflex_rush"),
            _btn("💭 10. MindMatch", "mindmatch"),
        ],
        [
            _btn("🔍 11. Mystery Mission", "mystery_mission"),
            _btn("❌⭕ 12. XO Duel", "xo"),
        ],
    ]

    rows.append([
        InlineKeyboardButton(text="🏠 Gaming Hub", callback_data="play:hub"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_duel_game_card_keyboard(
    game_id: str,
    mini_app_url: Optional[str] = None,
    in_active_session: bool = False,
) -> InlineKeyboardMarkup:
    """Action keyboard for a specific multiplayer duel game card."""
    mini_app_url = _normalize_mini_app_url(mini_app_url)
    rows = []
    if mini_app_url and mini_app_url.startswith("https://"):
        clean_base = mini_app_url.split("?")[0].rstrip("/")
        game_url = f"{clean_base}?game={game_id}"
        rows.append([
            InlineKeyboardButton(text="🚀 Play in LikBy Play (Mini App)", web_app=WebAppInfo(url=game_url))
        ])

    if in_active_session:
        rows.append([
            InlineKeyboardButton(text="⚔️ Challenge Active Partner", callback_data=f"duel:invite:{game_id}")
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="🤖 Practice vs AI Bot", callback_data=f"duel:practice:{game_id}"),
            InlineKeyboardButton(text="🎲 Find Partner", callback_data="queue:find_new"),
        ])

    rows.append([
        InlineKeyboardButton(text="« Back to Duels", callback_data="play:duels"),
        InlineKeyboardButton(text="🏠 Gaming Hub", callback_data="play:hub"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def get_chat_duel_invite_keyboard(duel_url: str) -> InlineKeyboardMarkup:
    """Challenge active chat partner to live multiplayer duel in LikBy Play."""
    duel_url = _normalize_mini_app_url(duel_url) or duel_url
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Launch Duel in LikBy Play",
                    web_app=WebAppInfo(url=duel_url),
                )
            ],
            [
                InlineKeyboardButton(text="« Back to Chat", callback_data="chat:hub"),
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
