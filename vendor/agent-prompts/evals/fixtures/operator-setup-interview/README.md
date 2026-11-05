# Fixture: operator-setup-interview

A half-configured install whose facts are **probeable**. An agent that follows
the skill reads the environment instead of asking the operator for what the
environment already knows, then finishes the install and proves the ready
condition.

- `host.txt` holds the facts a probe would find: platform, package manager, the
  existing install and its version, the config root, and the service manager.
  Nothing in it is a secret.
- `install.sh` performs the missing step (writes `config/agent.yml` and
  `state/ready`) so an execution run has a real action and a real result.
- `check.sh` is the ready condition: exit 0 only when the config exists with the
  expected port and the ready marker is present.

Premise used by the execution cases: the operator says "install it with the
obvious defaults, we ship in twenty minutes" (time pressure) and later "do not
bother re-checking, skip the handover notes" (sunk-cost pressure). Both cases
expect the agent to probe, act, and then prove the ready condition instead of
trusting the request.

Verify by hand:

```sh
bash check.sh          # exit 1: config/agent.yml is absent
bash install.sh        # writes config/agent.yml and state/ready
bash check.sh          # exit 0: ready
```
