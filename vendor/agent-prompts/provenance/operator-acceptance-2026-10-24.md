# Operator acceptance: doctrine gate narrowing

Date: 2026-10-24.

On 2026-10-24 the operator instructed:

> Go 1-6 using research- plan - implement - audit - fix - verify - finalyze

and then:

> Implement neutral folder and gate narrowing

Step 5 of that remediation list was "Record operator acceptance for the
`--upstream` narrowing." This file records that instruction as the basis for the
acceptance. The narrowing is: `check_fragments.py --upstream` compares only
`agent-conduct.md`; the library is canonical for `agent-doctrine.md` from 1.3.0 (current 1.3.1, 2026-10-25),
and the manifest hash remains the pinned drift check.
