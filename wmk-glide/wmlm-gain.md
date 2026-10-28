# Wie viel bringt ein deutsches `.wmlm`?

Stand: 27.10.2026. Ein deutsches `.wmlm` existiert noch nicht, also lässt sich
der Gewinn nicht direkt auf Deutsch messen. Der beste verfügbare Beleg ist das
**veröffentlichte englische `.wmlm`** auf echten englischen FUTO-Wischern mit
genau dem Blend, den `SuggestionEngine.blendGlideContextModel` fährt:

```
score + clamp(weight * (lnP(c) - lnP(leader)), -cap, +cap)
```

Das misst denselben Mechanismus, dieselbe Engine und dieselbe Poolgröße; nur
die Sprache des Modells ist eine andere. Der Prototyp steht in
[`experiments/glide_lm_blend_eval.rs`](experiments/glide_lm_blend_eval.rs).

## Messung (Englisch, echtes `.wmlm`)

Daten: FUTO `swipe5.jsonl`, gefiltert auf `language = "en"`,
`layout = "qwerty"`, `dual_finger = 0`; die ersten 2.129 Züge, davon 1.875
Ziele in der gebündelten `en.txt`. Layout `qwerty.json`, Modell
`en_context.wmlm` (10,8 MB, `d=256, layers=6, ff=768, ctx=40, vocab=24576,
step=28000`), Pool 8.

| Züge | Blend | top-1 | top-4 |
|---|---|---|---|
| alle 2.059 (Filter: ≥2 Buchstaben) | nein | 65,03 | 74,65 |
| | **0,7 / 3,0** | **69,40 (+4,37)** | **75,23 (+0,58)** |
| nur 1.824 bekannte Ziele | nein | 73,41 | 84,27 |
| | **0,7 / 3,0** | **78,34 (+4,93)** | **84,92 (+0,65)** |
| | 0,5 / 4,0 | 79,06 (+5,65) | 85,09 (+0,82) |
| | 0,7 / ohne Deckel | **79,17 (+5,76)** | 84,98 (+0,71) |

Der Blend verschiebt in allen 1.513 bekannten Zügen mit Vorgängerwort etwas;
der Gewinn ist also nicht ein paar Ausreißer. Der **3-Nat-Deckel kostet mit dem
echten Modell ~0,8 Punkte** gegenüber ohne Deckel; mit dem Korpus-Bigramm waren
es ~2,3. Ein Deckel 4,0 oder ein etwas kleineres Gewicht (0,5) ist die bessere
Ecke, wenn ein echtes Modell da ist.

Die absolute Basis (73,41) ist niedriger als die 81,49 aus dem Issue, weil die
ersten 2.129 `swipe5`-Züge ein anderer, härterer Ausschnitt sind als der
dortige Test-Split. Für die Frage zählt der **relative** Gewinn auf denselben
Zügen: **+4,4 bis +5,8 top-1**, **+0,6 bis +0,8 top-4**.

## Was das für Deutsch heißt

Ein deutsches `.wmlm`, auf Tatoeba/Leipzig in vergleichbarer Größe trainiert
(10M Parameter, 24k Vokabular, 4k Pieces, 28k Schritte), sollte einen
ähnlichen Mechanismus bringen. Realistische Erwartung für den Glide-Pfad:

| | Erwartung |
|---|---|
| deutsche Glide-Basis (deutsches Profil) | 74,15 |
| **deutsches `.wmlm`, Blend 0,7/3,0** | **~77–79 top-1** (+3 bis +5) |
| mit Deckel 4 / ohne Deckel | eher +4 bis +6 |
| top-4 | +0,5 bis +1,0 |

Das ist eine **Schätzung am englischen Modell**, keine deutsche Messung. Sie
ist deutlich über dem, was der deutsche n-gram-Pack im Glide-Pfad schafft
(+0,45), und deutlich unter der in-sample-Korpus-Bigramm-Zahl (+10). Ein
deutsches Modell muss auf einem gehaltenen deutschen Satz-Split nachgemessen
werden; der Beispiel-Harness ist sprachunabhängig (Records, Layout, Wortliste,
Modell).

## Was das Modell sonst noch bringt

Der Glide-Blend ist nur ein Verbraucher. Das englische Modell zeigt die
anderen:

- **Next-Word:** top-1 14 % → 20 %, top-3 23 % → 34 %.
- **Strip-Ranking:** erster Vorschlag +0,3 (careful), +3,2 (fast), +3,9
  (sloppy) Punkte.
- **Autocorrect-Gate:** mit Modell 84 % der echten Tippfehler bei 99,7 %
  Präzision (careful), 72 %/99,4 % (fast), 58 %/97,5 % (sloppy); keine
  fälschlich umgeschriebenen neuen Wörter.
- **Phrase/Re-check:** die Zwei-/Drei-Wort-Chips und die Rückprüfung des
  vorherigen Wortes werden erst mit Modell möglich.

Für Deutsch fällt damit nicht nur der Glide-Blend an, sondern die ganze
Kontextschicht. Die **+4,9 Glide-top-1** sind der konservativste Teil.

## Kosten und Voraussetzungen

- **Modell:** ~10 MB Download, Int8, auf dem Gerät; `ContextModelCatalog`-
  Eintrag (`de_context`), keine Engine-Änderung.
- **Training:** `tools/wmlm`; Tatoeba Deutsch (12 MB) + Leipzig
  `deu_news_2023_1M` (1M Sätze), optional OpenSubtitles; `de_aosp` als
  `seed_words`; `vocab=24576 pieces=2048 ctx=40`; d256/6/768; 28k Schritte;
  Qwen2.5-1.5B-Destillation. Auf einer RTX 3090/4090 unter zwei Stunden; die
  kleine Variante geht auch auf CPU/MPS, dauert aber.
- **Datenlizenzen:** Tatoeba (CC BY 2.0 FR / CC0), Leipzig/OpenSubtitles je
  eigene; im Datenrepo attribuieren.
- **Additiv:** Die echte Komposita-Liste (+1,55) bleibt unabhängig; ein
  deutsches `.wmlm` obendrauf ist der nächste Kontextschritt.

## Reproduktion

```sh
# Englischer Proxy
curl -L -o data/swipe5.jsonl \
  https://huggingface.co/datasets/futo-org/swipe.futo.org/resolve/main/swipe-5/swipe5.jsonl
curl -L -o data/en_context.wmlm \
  https://raw.githubusercontent.com/wasi-master/wmkeyboard-data/master/data/en/en_context.wmlm
# Filter: language=en, layout=qwerty, dual_finger=0; en.txt + qwerty.json aus dem Repo
cd native/wm-engine
cargo build --release --example glide_lm_blend_eval
COLS=10 THREADS=8 RESULTS=8 WEIGHT=0.7 CAP=3 \
  ./target/release/examples/glide_lm_blend_eval \
  en_swipes_2129_known.jsonl qwerty.json en.txt en_context.wmlm
```

Für Deutsch denselben Harness mit `de_swipes_2129.jsonl`, `german.json`,
`de_aosp.txt` und `de_context.wmlm` fahren, sobald das Modell existiert.

## Fazit

**Ein deutsches `.wmlm` ist der größte verbleibende Kontexthebel: nach dem
englischen Referenzmodell +4,9 top-1 im Glide-Pfad (0,7/3,0), bis +5,8 ohne
Deckel, plus die Next-Word-/Autocorrect-Gewinne.** Die Schätzung für Deutsch
liegt bei **+3 bis +5 top-1** auf der 74,15-Basis, also ~77–79. Der Pack bringt
+0,45, die echte Komposita-Liste +1,55; beides ist additiv, aber das Modell ist
der Hebel, der die Kontextschicht erst aktiviert.

Wie man es auf einer RX 9060 XT trainiert (WSL2, Lehrerwahl, Token-Abdeckung)
und was lokal, in der Cloud oder über eine API kostet:
[`wmlm-training-windows.md`](wmlm-training-windows.md).
