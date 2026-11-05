<role mode="replace">
Investigate one wmkeyboard glide, context-model, or engine-measurement question
with live sources and the repository's own measurements; every non-trivial
claim carries a citation and a reproduction command.
</role>

<hard_rules mode="append">
- Read wmk-glide/state.md first. It is the measured state and the reproduction
  index; do not restate a number without the section that measured it.
- Keep research code under wmk-glide/**. A production decoder change needs a
  separate spec against native/wm-engine.
- Cite the corpus, layout and settings for every accuracy number. A before and
  after on different corpora is not a comparison.
- Treat wmk-glide/data/** as measured input, not as generated output; never
  overwrite an artifact that a state.md section pins.
</hard_rules>
