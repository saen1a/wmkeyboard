"""German piece inventory v2 for the student rebuild.

Keeps `common.Pieces` semantics (start `▁`, continuation `##`, MAX_PIECE=5)
and the same 2,048-slot budget. Adds a curated German morpheme/affix/digraph
seed set so the greedy parser produces fewer, more meaningful pieces, then
fills the rest with the corpus's frequent OOV substrings. Word IDs are not
touched here; `prep_v2.py` keeps the old 22,512-word list and appends this
piece inventory after it.
"""
from __future__ import annotations

import collections
from common import MAX_PIECE, Pieces

# Prefixes, suffixes and German digraphs/trigraphs. Only entries of length
# 1..MAX_PIECE are used; longer forms are filtered.
SEED_PIECES = {
    # prefixes
    "ver", "vor", "nach", "aus", "ein", "auf", "ab", "an", "bei", "mit",
    "über", "unter", "durch", "gegen", "zurück", "zusammen", "auseinander",
    "ent", "er", "ge", "miss", "un", "wieder", "zwischen",
    # suffixes
    "ung", "heit", "keit", "lich", "isch", "bar", "sam", "tion", "tät",
    "ieren", "los", "voll", "haft", "frei", "arm", "reich", "ig", "in",
    "chen", "lein", "schaft", "tum", "nis", "sal", "ung",
    # common German digraphs/trigraphs
    "sch", "ch", "ei", "ie", "au", "eu", "äu", "st", "ng", "pf", "tz",
    "ck", "qu", "sp", "tr", "br", "fr", "gr", "kr", "pr", "dr", "bl",
    "fl", "gl", "kl", "pl", "str", "spr", "schr", "tsch",
}


def _add(cur: set[str], piece: str, slots: int) -> None:
    if len(cur) >= slots:
        return
    if 1 <= len(piece) <= MAX_PIECE:
        cur.add(piece)


def build_v2(oov_counts: dict[str, int], n: int = 2048) -> Pieces:
    """Build a German-oriented piece inventory with exactly `n` tokens when
    the substring pool is large enough."""
    starts: collections.Counter = collections.Counter()
    conts: collections.Counter = collections.Counter()
    letters: set[str] = set()
    for w, c in oov_counts.items():
        letters.update(w)
        for i in range(len(w)):
            for j in range(i + 1, min(len(w), i + MAX_PIECE) + 1):
                (starts if i == 0 else conts)[w[i:j]] += c

    chosen_s: set[str] = set(letters)
    chosen_c: set[str] = set(letters)

    # Curated seeds first, in both tables; the greedy parser can then use
    # them at word start or after the first piece.
    for p in sorted(SEED_PIECES):
        if len(chosen_s) + len(chosen_c) >= n:
            break
        _add(chosen_s, p, n)
        _add(chosen_c, p, n)

    # Fill the remainder by frequency, as the original builder does.
    pool = [(c, "s", p) for p, c in starts.items() if len(p) > 1]
    pool += [(c, "c", p) for p, c in conts.items() if len(p) > 1]
    pool.sort(reverse=True)
    for _, kind, piece in pool:
        if len(chosen_s) + len(chosen_c) >= n:
            break
        if kind == "s":
            _add(chosen_s, piece, n)
        else:
            _add(chosen_c, piece, n)

    # If the pool was too small, fill with single characters from both tables.
    for ch in sorted(letters):
        if len(chosen_s) + len(chosen_c) >= n:
            break
        _add(chosen_s, ch, n)
        _add(chosen_c, ch, n)

    if len(chosen_s) + len(chosen_c) != n:
        raise ValueError(
            f"piece inventory has {len(chosen_s) + len(chosen_c)} != {n}"
        )
    return Pieces(chosen_s, chosen_c)
