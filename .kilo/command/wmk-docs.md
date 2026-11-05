---
description: Validate a WM Keyboard docs change
---

Docs scope: $ARGUMENTS

Read `docs/CONTENT_GUIDE.md` before editing. Verify every factual claim against
`app/`, `core/`, or `feature/`. Then run:

```sh
cd docs && npm ci && npm run check
```

Report the command and exit code. A docs page that builds but invents behaviour
is still a finding; name the code path that proves each claim.
