# Safety

- {{SAFETY_RULE}}: history rewrite or force-push, deleting data or volumes,
  deploying or redeploying a stack, dropping a database -- ask first, and never
  bundle one into a verification or cleanup step.

Never print secrets, tokens or credentials, even to prove they exist.

A step that needs authority you do not have stops: report BLOCKED, do not
improvise past it.
