# WM Keyboard: Glide-Typing Deutsch – Analyse und Tuning

Stand: 24.10.2026

Untersuchung der Wisch-Einstellungen von WM Keyboard (wasi-master/wmkeyboard) für
schnelles, ungenaues Wischen mit Deutsch als Hauptsprache. Grundlage sind drei
Quellen: der Einstellungs-Export des Geräts, die Projekt-Dokumentation und der
Quellcode.

> **Nachtrag 26.10.2026.** Dies ist der erste Durchgang. Die späteren Messungen am echten
> Decoder (siehe [`issue-tuning-per-language.md`](issue-tuning-per-language.md)) haben zwei
> Empfehlungen korrigiert: der **Endfehler-Radius** bleibt auf dem ausgelieferten **2,0**
> (größere Werte kosten 0,6–2,5 Punkte; die Doku-Tabelle mit „1,6" ist veraltet), und der
> **Vokabeldeckel** ist Latenzsteuerung, keine Genauigkeitsverbesserung (auf „Erfolg pro
> Wisch" neutral bis leicht negativ). Der eigentliche Hebel ist ein **Sprachprofil** über
> `freq_weight` und `gap_weight`. Die Datei bleibt als Verlaufsstand stehen.

## Rahmenbedingungen

- App: WM Keyboard 0.6.3 (versionCode 380)
- Export: `wmkeyboard-backup-20261024-113244.wmconfig.json`
- Quellcode: `wasi-master/wmkeyboard`, Commit `8d81058` (23.10.2026)
- Layout bleibt unverändert: QWERTZ++ mit `ä ö ü ß` als Long-Press-Alternativen
- Englisch bleibt bewusst Zweitsprache
- Glide-Engine: nur die eingebaute (`BUILT_IN`), kein FUTO, keine Google-Bibliothek

## Datenbasis aus dem Export

| Kennzahl | Wert |
|---|---|
| Gewischte Wörter | 6.718 |
| Wischstrecke | 589.160 mm (ca. 88 mm pro Wort) |
| Getippte Wörter gesamt | 14.547 (46 % davon gewischt) |
| Gelernte Wörter | 2.296, davon 181 mit Umlaut (7,9 %) |
| Wörter mit gelernten Formen | 1.620 (5.927 Formen, max. 10 pro Wort) |
| Handmodell | 1.353 Proben über 49 Zellen |
| Korrekturpaare | 63 (61 davon mit genau einer Korrektur) |
| Sofort-Undos | 43 |
| Korrekturquote | 108 / 6.718 = **1,6 %** |

Das Handmodell zeigt eine systematische Abweichung von **−0,11 Keybreiten**
(Spitze −0,23): Die Wischer landen im Mittel etwas oberhalb der Key-Mitte. Das
ist gelernt und wird kompensiert; „Meinen Wischstil lernen“ darf nicht
zurückgesetzt werden.

## Befunde

### 1. Die Trefferquote ist bereits hoch

108 Korrekturen auf 6.718 Wischer sind rund 1,6 %. Es gibt keinen
systematischen Fehler, den ein einzelner Regler beheben könnte.

### 2. Fehlerklassen der deutschen Wischer

Von den 63 Paaren sind grob 20 rein englisch, 10 gemischt und 33 rein deutsch.

| Muster | Beispiele | Anteil |
|---|---|---|
| Ende daneben / zu früh abgehoben | `großer→große`, `sehe→sehr`, `vom→von`, `laden→lassen` | ca. 7 |
| Mitte daneben | `werde→werfe`, `bus→bis`, `mich→noch`, `passt→post` | ca. 8 |
| Anfang daneben | `sie→die`, `kauft→läuft`, `es→was`, `von→bin` | ca. 5 |
| Kurzer Zug, langes Wort gelesen | `iau→ist`, `alpes→kamel`, `euchre→woche` | ca. 8 |

Etwa die Hälfte der deutschen Korrekturen betrifft Wörter mit höchstens vier
Buchstaben. Bei einem Drei-Buchstaben-Wort ist der gesamte Wisch rund 30 mm lang;
die Forminformation ist dort von Natur aus dünn.

### 3. Umlaute sind nicht der Hauptfehler

`ä ö ü ß` liegen als Long-Press auf `a o u s` und teilen sich damit dieselbe
Key-Mitte. In `GlideKeyMap.of()` werden Zeichen mit identischer Position zu einem
Key zusammengefasst (`putIfAbsent`, Reihenfolge Basislabel → Shift → Long-Press),
das Dekodieren kann `a` und `ä` also nicht geometrisch unterscheiden.

Von den sechs Korrekturpaaren mit Umlaut ist aber nur **`waren`/`wären`** ein
echter Zwilling. Bei den übrigen unterscheiden sich die Züge in mehr als dem
Umlaut (`kauft`/`läuft`: k und l liegen nebeneinander, `wies`/`weiß`: andere
Buchstabenreihenfolge, `aus`/`süß`: anderer Pfad).

Entscheidend ist das User-Tier: Gelernte Wörter laufen mit
`USER_WORD_WEIGHT = 500`, also **+6,2 Nats** gegenüber einem Wörterbuchwort
gleicher Häufigkeit (`SuggestionEngine.kt`). Deshalb gewinnt bei fünf von sechs
Paaren bereits die gemeinte Schreibweise. Eigene Umlaut-Tasten sind für dieses
Gerät nicht erforderlich.

### 4. Englisch als Zweitsprache kostet wenig, aber messbar

Englisch geht mit `SECONDARY_ENGLISH_DIVISOR = 2` in den Kandidaten-Pool, also
**−0,69 Nats**. Bei `shapeWeight = 2.5` genügt ein Formvorteil von 0,3, um das
umzudrehen. Rund ein Drittel der Korrekturen sind denn auch englische Wischer
(`yawl→yak`, `mammy→many`, `clams→commands`) oder gemischt (`wirth→with`,
`message→müsste`).

Die Entscheidung für Englisch bleibt bestehen. Innerhalb dieser Entscheidung
hilft die Zuordnung pro App: In Apps, in denen überwiegend Englisch geschrieben
wird, ist Englisch dann primär (Gewicht 1,0 statt 0,5) und Deutsch nicht im Pool.

### 5. Großschreibung ist kein Thema

Der Wörterbuch-Speicher enthält 30 Wörter mit abweichender Großschreibung, und
nur **0,7 %** der getippten Tokens tragen Großbuchstaben. Glided Wörter werden
ohnehin nur durch Shift oder einen Zug über die Shift-Taste groß
(`glideCased()` in `WMKeyboardService.kt` wendet kein gelerntes `wordCase` an).
Bei diesem Schreibstil bringt „Über Shift wischen zum Großschreiben“ nichts.

## Angewandte Änderungen

| Einstellung | Schlüssel | Vorher | Jetzt | Begründung |
|---|---|---|---|---|
| Wischen vervollständigt getippte Buchstaben | `gesture_swipe_continues_typed` | aus | **an** | Ein Anfangsbuchstabe wird getippt, der Rest gewischt; adressiert die Anfangsklasse (`sie`/`die`, `kauft`/`läuft`, `von`/`bin`) |
| Glide-Engine | `gesture_engine` | (Default) | **`BUILT_IN`** | Nur die eingebaute Engine; FUTO und die Google-Bibliothek bleiben aus |
| Endfehler-Radius | `gesture_end_radius` | 1,6× | **2,2×** | Oberhalb 1,6× wird die Distanz zum letzten Buchstaben auch im Score verziehen; Plateau laut Messung bis 3,0× |
| Wörter, die durch Wischen erzeugt werden können | `gesture_vocabulary` | `ALL` (kein Deckel) | **`MEDIUM` (150k)** | Top-1 auf großer Liste: .7813 ohne Deckel, .8906 bei 150k, .9250 bei 50k; gelernte Wörter bleiben ungedeckelt |
| Das Wort farblich hervorheben … | `gesture_commit_color` | `CONFIDENT` | **`ALWAYS`** | Zeigt vor dem Abheben, welcher Zwilling landet |
| Spur-Dauer | `gesture_trail_duration_ms` | 617 ms | **350 ms** | Kürzere Spur bei schnell aufeinanderfolgenden Wischern |
| Secrets in Sicherungen | `auto_backup_include_secrets` | an | **aus** | Der Export trug den API-Schlüssel im Klartext |
| Schlüssel in Sicherungen | `auto_backup_include_keys` | an | **aus** | Dasselbe für Lizenz-/Zugangsschlüssel |

Nebenwirkung des ersten Punktes: Ein Wisch gehört danach immer zum getippten
Wort; ein Wisch nach einem fertigen Wort klebt an diesem.

## Die fertige Konfiguration

[`data/wmk-settings-de-optimized.wmconfig.json`](data/wmk-settings-de-optimized.wmconfig.json)
enthält alle 140 Einstellungen mit den obigen Werten, als importierbares Bundle
(`format: wmkeyboard-config`, nur die Sektion `settings`).

- **Nicht enthalten** (bewusst entfernt): `ai_deepseek_key`,
  `auto_backup_passphrase`, `auto_backup_locations`. Dazu kommen alle übrigen
  Schlüssel aus `SettingsBackup.SECRET_KEYS` sowie die installspezifischen
  `TRANSIENT_KEYS` (Auto-Backup- und Sync-Zustand), damit die Datei auf einem
  anderen Gerät nichts Falsches behauptet. Die Schlüssel müssen nach dem Import
  neu eingetragen werden.
- **Enthalten, aber groß**: `custom_layouts` (308 KB, die Layout-Definitionen)
  und `keyboard_modes` (4 KB). Ohne diese beiden wäre die Datei rund 6 KB groß.
- **Import**: Einstellungen → Backup & Wiederherstellung → Importieren → Datei
  wählen. Der Import **ergänzt** die vorhandenen Einstellungen
  (`editPrefs { prefs -> entries.forEach { prefs.put(it) } }` in
  `SettingsRepository.importConfig`): Was in der Datei fehlt, bleibt auf dem
  Gerät stehen – insbesondere die eigenen Schlüssel.

## Weitere Empfehlungen (nicht gesetzt)

- **Englisch pro App zuordnen.** In Apps, die überwiegend englisch sind, das
  englische Layout als primäre Sprache eintragen: Englisch ist dort dann
  primär (Gewicht 1,0) statt Zweitsprache (Faktor 2, −0,69 Nats), und Deutsch
  ist nicht im Kandidaten-Pool.
- **FUTO Swipe** bleibt aus (Entscheidung): nur englisch auf QWERTY, und das
  englische Layout ist QWERTZ.

## Bewusst nicht geändert

| Einstellung | Wert | Grund |
|---|---|---|
| Start-Fehlerradius / Pfad-Fehlerradius | 1,78× / 1,76× | Kein Fehlermuster; höher heißt mehr Buchstaben im Rennen |
| Lange Wörter frühzeitig beenden | aus | Die Fehler sind kurze Züge, nicht abgebrochene lange |
| Loop to double a letter | aus | Richtig für unruhige Finger |
| Glide across spacebar | aus | Zerschneidet Wörter bei ungenauen Zügen |
| Über Shift wischen | aus | 0,7 % großgeschriebene Tokens |
| Sandbox („Wessen Wörter …“) | Every word | `PREFER_LEARNED` ist laut Quellcode Instrumentierung, kein Genauigkeitsgewinn (+0,1 Punkte) |
| Gespeicherte Formen pro Wort | 13 | Bis zu 10 Formen pro Wort werden tatsächlich genutzt |
| Kandidaten aus gelernten Formen | an | Genau für ungenaue Start- und Endpunkte |
| FUTO Swipe | aus | Nur Englisch auf QWERTY; das englische Layout ist QWERTZ und fällt zurück |

## Prüfplan

Alle Werte sind gesetzt; zu prüfen ist die Wirkung:

1. 20 deutsche Sätze wischen, Korrekturen zählen – Erwartung: die
   „ein Buchstabe zu früh“-Fälle (`großer`/`große`) verschwinden, die
   `vom`/`von`-Sorte bleibt (die entscheidet der Endpunkt, nicht der Radius).
2. Auf fehlende Komposita achten; wenn eine fehlt, `gesture_vocabulary` auf
   `LARGE` (300k) zurücknehmen. Gelernte Wörter sind nie gedeckelt.
3. Prüfen, ob die Farbhervorhebung den falschen Zwilling vor dem Abheben
   sichtbar macht.
4. Nach einer Woche Export erneut ziehen und die Paare in
   `sections.swipe.outcomes` gegen diese Ausgangsbasis vergleichen.

## Datenschutz

Der vollständige Export enthält Klartext-Geheimnisse (AI-API-Schlüssel,
Backup-Passphrase), das gelernte Wörterbuch und die Wischformen. Er gehört nicht
in dieses Repository und nicht in einen Chat-Upload.

Die eingecheckte Datei ist deshalb auf die Sektion `settings` reduziert und um
alle Schlüssel aus `SettingsBackup.SECRET_KEYS` sowie die installspezifischen
`TRANSIENT_KEYS` bereinigt; die drei im Export vorhandenen Geheimnisse
(`ai_deepseek_key`, `auto_backup_passphrase`, `auto_backup_locations`) sind
entfernt. Wörterbuch, Wischformen, Statistik, Zwischenablage und Emoji-Verlauf
sind nicht enthalten. Die im Umlauf befindlichen Schlüssel sollten trotzdem
ersetzt werden.

