#!/usr/bin/env python3
"""Bounded German compound generator: prototype for the lexicon experiment.

Reads a frequency word list, proposes `modifier + linking element + head`
compounds that the list does not contain, scores them by the damped minimum of
their parts, and writes the best `--budget` of them as a new word list.

This is deliberately a *generator*, not a splitter: the decoder can only answer
with words that are in the trie, so the question this answers is "how far does a
bounded, high-precision list expansion get us towards the oracle?".

Usage:
    python3 decompound.py de_150k.txt out.txt --budget 50000
"""

import argparse
import heapq
import sys

# Heads people actually build compounds with. Ending-based, because the list
# carries no part of speech: every German noun ends in one of these far more
# often than a verb or an adjective does.
HEAD_SUFFIXES = (
    "e", "en", "er", "ung", "heit", "keit", "schaft", "tät", "ion", "nis", "tum",
    "ling", "chen", "lein", "ment", "ur", "ik", "ie", "ei", "sal", "ist", "ismus",
    "grafie", "logie", "nomie", "thek", "werk", "zeug", "mittel", "gerät", "anlage",
    "bereich", "stelle", "haus", "zimmer", "weg", "zeit", "jahr", "tag", "arbeit",
    "kosten", "preis", "zahl", "rate", "quote", "plan", "liste", "karte", "buch",
    "bild", "kraft", "stoff", "system", "management", "sektor", "gemeinde", "stadt",
    "land", "berg", "straße", "platz", "raum", "feld", "wald", "bach", "brücke",
    "bahn", "hafen", "schule", "universität", "klinik", "amt", "rat", "kammer",
    "verband", "verein", "gruppe", "team", "chef", "leiter", "träger", "geber",
    "nehmer", "weiser", "messer", "prüfung", "rechnung", "ordnung", "vertrag",
    "schutz", "pflicht", "fähigkeit", "möglichkeit", "geschwindigkeit",
    "entwicklung", "forschung", "wissenschaft", "technik", "industrie", "wirtschaft",
    "politik", "geschichte", "literatur", "sprache", "kultur", "musik", "kunst",
    "sport", "spiel", "fest", "feier", "reise", "fahrt", "flug", "zug", "auto",
    "rad", "schiff", "boot", "maschine", "motor", "pumpe", "turbine", "reaktor",
    "kraftwerk", "netz", "leitung", "kabel", "rohr", "tank", "lager", "regal",
    "schrank", "tisch", "stuhl", "bett", "tür", "fenster", "dach", "wand",
    "boden", "decke", "treppe", "garten", "hof", "scheune", "mauer", "brunnen",
)

# Linking elements, with how much of the parts' frequency the compound keeps.
LINKS = (("", 1.0), ("s", 0.9), ("n", 0.85), ("en", 0.85), ("er", 0.8),
         ("e", 0.75), ("es", 0.7), ("ns", 0.6))

MAX_LEN = 24          # GlideBeam's MAX_WORD_LENGTH
DAMPING = 20.0        # frequency of a compound relative to its weakest part
MIN_PART_LEN = 4


def load(path):
    words = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            word, _, freq = line.rpartition(" ")
            if not word:
                continue
            try:
                words[word.lower()] = int(freq)
            except ValueError:
                continue
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wordlist")
    ap.add_argument("out")
    ap.add_argument("--budget", type=int, default=50000)
    ap.add_argument("--modifiers", type=int, default=20000)
    ap.add_argument("--heads", type=int, default=8000)
    ap.add_argument("--min-freq", type=int, default=20)
    ap.add_argument("--report-targets")
    args = ap.parse_args()

    words = load(args.wordlist)
    ranked = sorted(words.items(), key=lambda kv: -kv[1])

    def is_head(w):
        return len(w) >= 3 and w.endswith(HEAD_SUFFIXES)

    heads = [(w, f) for w, f in ranked if is_head(w)][: args.heads]
    modifiers = [
        (w, f) for w, f in ranked
        if len(w) >= MIN_PART_LEN and f >= args.min_freq
    ][: args.modifiers]
    print(f"list {len(words)}  heads {len(heads)}  modifiers {len(modifiers)}",
          file=sys.stderr)

    seen = set()
    heap = []          # min-heap by score, capped at budget * 4
    cap = args.budget * 4
    made = 0
    for mod, fmod in modifiers:
        cutoff = heap[0][0] if len(heap) >= cap else 0.0
        for head, fhead in heads:
            best = min(fmod, fhead) * max(w for _, w in LINKS) / DAMPING
            if heap and len(heap) >= cap and best < heap[0][0]:
                break
            for link, weight in LINKS:
                word = mod + link + head
                if len(word) > MAX_LEN or word in words or word in seen:
                    continue
                score = min(fmod, fhead) * weight / DAMPING
                if score <= 0:
                    continue
                made += 1
                seen.add(word)
                if len(heap) < cap:
                    heapq.heappush(heap, (score, word))
                elif score > heap[0][0]:
                    heapq.heapreplace(heap, (score, word))
    kept = sorted(heap, reverse=True)[: args.budget]
    print(f"generated {made} candidates, keeping {len(kept)} (score >= {kept[-1][0]:.1f})",
          file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as out:
        out.write("".join(f"{w} {max(1, int(s))}\n" for s, w in kept))

    if args.report_targets:
        targets = set()
        with open(args.report_targets, encoding="utf-8") as f:
            for line in f:
                targets.add(line.strip().lower())
        got = targets & {w for _, w in kept}
        print(f"targets {len(targets)}  recovered {len(got)} "
              f"({100 * len(got) / max(1, len(targets)):.1f} %)")
        for w in sorted(got)[:20]:
            print("  +", w)


if __name__ == "__main__":
    main()
