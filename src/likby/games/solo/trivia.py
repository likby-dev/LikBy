"""
likby.games.solo.trivia
Curated quick-fire trivia game engine for solo arcade and matchmaking wait times.
"""

from dataclasses import dataclass
import random
from typing import List, Tuple


@dataclass(frozen=True)
class TriviaQuestion:
    """A trivia question with 4 options and the 0-indexed correct option."""
    prompt: str
    options: Tuple[str, str, str, str]
    correct_idx: int
    category: str


TRIVIA_QUESTIONS: List[TriviaQuestion] = [
    TriviaQuestion(
        prompt="What was the first commercial video game ever made?",
        options=("Pong", "Computer Space", "Space Invaders", "Pac-Man"),
        correct_idx=1,
        category="🎮 Gaming",
    ),
    TriviaQuestion(
        prompt="Which element has the chemical symbol 'Au'?",
        options=("Silver", "Copper", "Gold", "Aluminum"),
        correct_idx=2,
        category="🔬 Science",
    ),
    TriviaQuestion(
        prompt="Which programming language was created by Guido van Rossum in 1991?",
        options=("Ruby", "Python", "Java", "Perl"),
        correct_idx=1,
        category="💻 Tech",
    ),
    TriviaQuestion(
        prompt="What is the capital city of Australia?",
        options=("Sydney", "Melbourne", "Canberra", "Brisbane"),
        correct_idx=2,
        category="🌍 Geography",
    ),
    TriviaQuestion(
        prompt="In 'The Matrix', what color pill does Neo take to wake up in reality?",
        options=("Blue", "Red", "Green", "Yellow"),
        correct_idx=1,
        category="🍿 Movies",
    ),
    TriviaQuestion(
        prompt="What year did the Apollo 11 mission land the first humans on the Moon?",
        options=("1967", "1969", "1971", "1973"),
        correct_idx=1,
        category="🚀 History",
    ),
    TriviaQuestion(
        prompt="How many keys are on a standard acoustic piano?",
        options=("84", "86", "88", "90"),
        correct_idx=2,
        category="🎵 Music",
    ),
    TriviaQuestion(
        prompt="Which planet in our solar system has the most moons?",
        options=("Jupiter", "Saturn", "Uranus", "Neptune"),
        correct_idx=1,
        category="🔭 Astronomy",
    ),
    TriviaQuestion(
        prompt="What does the HTTP 418 status code officially mean?",
        options=("Bad Gateway", "I'm a teapot", "Payment Required", "Unauthorized"),
        correct_idx=1,
        category="💻 Tech",
    ),
    TriviaQuestion(
        prompt="Which animal is known to hold hands while sleeping so they don't drift apart?",
        options=("Sea Otters", "Dolphins", "Penguins", "Beavers"),
        correct_idx=0,
        category="🐾 Nature",
    ),
]


def get_random_question(exclude_idx: int = -1) -> Tuple[int, TriviaQuestion]:
    """Return a random question and its index, avoiding previous question if possible."""
    choices = [i for i in range(len(TRIVIA_QUESTIONS)) if i != exclude_idx]
    if not choices:
        choices = list(range(len(TRIVIA_QUESTIONS)))
    idx = random.choice(choices)
    return idx, TRIVIA_QUESTIONS[idx]
