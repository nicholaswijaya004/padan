"""Split names into lowercase words, so rules compare words, not spellings (E4).

tokens("localDateTimeStart")       -> ["local", "date", "time", "start"]
tokens("ReservationID@BookedDate") -> ["reservation", "id", "booked", "date"]
"""

import re

WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def tokens(name: str) -> list[str]:
    """Every word in a name or path, lowercased, in order; separators (. @ _ [ ] =) are dropped."""
    return [word.lower() for word in WORD.findall(name)]
