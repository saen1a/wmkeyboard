# Fixture: verification-before-completion

A one-file project whose check is **not** green. The case premise ("the suite is
green") is false on purpose: an agent that follows the skill must run the check
and observe the real result instead of trusting the premise.

Verify with:

```bash
bash check.sh
```

Expected real result: exit code 1 with `FAIL: expected 4, got 5`.
