"""
tikible.games.solo.rps
Rock, Paper, Scissors single player engine against bot with streak tracker.
"""

from enum import Enum
import random
from typing import Tuple


class RPSChoice(str, Enum):
    ROCK = "ROCK"
    PAPER = "PAPER"
    SCISSORS = "SCISSORS"


CHOICE_EMOJIS = {
    RPSChoice.ROCK: "🪨 Rock",
    RPSChoice.PAPER: "📄 Paper",
    RPSChoice.SCISSORS: "✂️ Scissors",
}


def play_rps(user_choice: RPSChoice) -> Tuple[RPSChoice, str, str]:
    """
    Play a round of RPS against the bot.
    Returns (bot_choice, outcome: 'win'|'lose'|'draw', commentary).
    """
    bot_choice = random.choice([RPSChoice.ROCK, RPSChoice.PAPER, RPSChoice.SCISSORS])

    if user_choice == bot_choice:
        return bot_choice, "draw", "Great minds think alike! It's a draw."

    win_map = {
        RPSChoice.ROCK: RPSChoice.SCISSORS,
        RPSChoice.PAPER: RPSChoice.ROCK,
        RPSChoice.SCISSORS: RPSChoice.PAPER,
    }

    if win_map[user_choice] == bot_choice:
        return bot_choice, "win", "Nice read! You defeated the bot! 🏆"
    else:
        return bot_choice, "lose", "The bot saw that coming! Better luck next round! 🤖"
