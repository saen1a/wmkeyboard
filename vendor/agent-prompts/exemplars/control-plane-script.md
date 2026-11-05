# Service control script: worked reference

A control script answers one question for a supervisor or an operator: what is
the state of this service, and may it be started, stopped, or left alone? This
exemplar fixes the answers to four exit codes, records operator intent in a
marker that outlives the controller, holds a single-instance lock, and refuses
to force-kill.

Scope: one service, one host, one controller. The service's own startup and
health checks are supplied as two commands and are not specified here.

## The four exit codes

| Code | State | Meaning for the caller |
|---:|---|---|
| 0 | running | Running and every part reports healthy |
| 1 | stopped, or must restart | Not running, or the running process is superseded and must be replaced |
| 2 | degraded | Running, but a part reports an error |
| 3 | starting or stopping | Running, but setup or shutdown is still in progress |

Code 1 is two facts with one consequence: a stopped service and a service whose
probe reports a superseded build both require a restart. `start` is not the
remedy for a live process; the caller's rule is 0 leave alone, 1 restart, 2
report, 3 wait. Code 2 and code 3 are deliberately different: an error is not a
wait, and a caller that retries a wait must not retry an error blindly.

The four codes describe the service. When the controller itself cannot observe
or act (the lock is held, the marker write failed), it reports 2 with the reason
code and `state=unknown`: "the controller could not establish the state" is an
error, and it must never be rounded down to 0.

The code is the contract. Log text is not. A log line is free-form, localized,
versioned, and often buffered or truncated; a caller that greps it is coupled to
another program's wording and breaks when the wording improves. A closing
sentence in a log is an instruction to believe a state; the exit code is the
part the caller can enforce, which is the distinction
`standards/work-authorization.md` WA-11 draws between a claim and enforcement.
When a check could not run at all, the script reports 3 or 2 with a reason code
and never 0: `standards/verification-integrity.md` VI-03 makes skipped
unverified, and unknown health is not healthy.

The status line is derived from facts every time: the pid file, the marker, and
the probe. No component writes a `status` column, so the line cannot drift from
the process, as `standards/verification-integrity.md` VI-15 requires.

## The intentional-stop marker

A crash and an operator stop both leave the process absent, and only the second
one may suppress an automatic restart. The marker records the intent:

```text
<boot_id> <pid> <epoch>
```

The stop command writes it before sending TERM, using a temp file and an atomic
rename, so a controller crash leaves either the old state or the marker, never a
truncated file. The start command removes it. Three rules keep it from becoming
a trap:

- A marker from a different boot is ignored. Intent is scoped to the boot in
  which it was recorded; a persistent disable belongs in the supervisor's enable
  flag, not here.
- The automatic path (`recover`) refuses while a current marker exists; the
  explicit path (`start`) clears it. The one exception is a stop that is still
  in progress (same pid, inside the timeout): `start` waits for it instead of
  racing it. Recovery is never blocked by a human decision that has been
  superseded.
- A marker whose pid no longer matches a live process is stale. A running
  process wins, and the next successful start removes the marker.

The marker also gives a crashed stop a state: while the process is still alive
and the marker is younger than the stop timeout, the status is `stopping` (3);
after that it is `stop-timeout` (2). The caller learns that the stop did not
finish instead of reading a plain `running`.

## The single-instance lock

`start`, `stop`, `restart`, and `recover` take an exclusive lock before they act.
The lock is a kernel lock on an open file descriptor (`flock -n`), so the
kernel releases it when the controller dies. A lock directory with a pid file
needs a stale-lock rule, and that rule races with pid reuse; the file-descriptor
lock has neither problem on the local host.

A second controller that cannot take the lock prints `reason=locked` and exits
2. It never reports 0, because it did not observe the service, and it never
waits with a timeout that could exceed the caller's deadline.

The launched service must not inherit the lock descriptor. The skeleton closes
it on the launch redirection (`9>&-`); without that, the service holds the lock
for its whole lifetime and every later stop waits for the service to exit, which
is the deadlock the lock exists to prevent.

## A restart that never force-kills

`restart` is `stop` followed by `start`. The stop sends TERM once, then polls
for at most `STOP_TIMEOUT` seconds. If the process is still alive, the restart
exits 2 and leaves the old process running; it does not send KILL and does not
start a second copy.

Force-kill is refused for three reasons. TERM lets the process finish a
committed effect or an in-flight shutdown, and `standards/durable-effects.md`
EF-10 treats a crash as recoverable but does not make one free. A silent KILL
destroys the evidence of why the process did not stop, which is the one fact the
operator needs. And escalation belongs to the supervisor's declared unit policy
with its own timeout, where it is visible in configuration; a control script
that escalates on its own hides that policy.

A start that dies immediately is reported as 1 (`start-failed`), not 3. The
check is a liveness test after launch, not a readiness test; readiness is the
probe's job, and a probe that has not answered yet is 3.

## The status line

One line on stdout, `key=value` fields in a fixed order, no spaces in values:

```text
service=<name> state=<state> pid=<pid|-> uptime=<seconds|-> reason=<code>
```

| Key | Value |
|---|---|
| `service` | The configured name, unchanged for the life of the deployment |
| `state` | `running`, `starting`, `stopping`, `stopped`, or `unknown` |
| `pid` | The live pid, or `-` when absent |
| `uptime` | Seconds the current pid has run, or `-` when absent |
| `reason` | A closed code: `ok`, `setup-wait`, `part-error`, `restart-required`, `probe-unknown`, `crash`, `operator-stop`, `stop-in-progress`, `stop-timeout`, `start-failed`, `marker-failed`, `locked`, `usage` |

Consumers parse by key. A key is never renamed or repurposed; a new fact is a
new key appended to the line, and an unknown key is ignored. Values are closed
tokens or integers, so a consumer never needs a regular expression to read a
field. Diagnostics and stack traces go to stderr, so the status line stays one
machine-readable record. Every invocation prints exactly one line: `restart`
suppresses the intermediate stop line and reports the state it reached after the
composite action.

Example lines:

```text
service=api state=running pid=4242 uptime=813 reason=ok
service=api state=running pid=4242 uptime=813 reason=restart-required
service=api state=starting pid=4243 uptime=0 reason=setup-wait
service=api state=stopping pid=4242 uptime=815 reason=stop-timeout
service=api state=stopped pid=- uptime=- reason=operator-stop
```

## Skeleton

```sh
#!/bin/sh
# svcctl: status/start/stop/restart/recover for one service.
# set -e is deliberately absent: every failure maps to a declared exit code.
set -u

NAME=${SERVICE_NAME:?}
STATE_DIR=${STATE_DIR:?}
SERVICE_BIN=${SERVICE_BIN:?}
HEALTH_CMD=${HEALTH_CMD:?}
PID_FILE=$STATE_DIR/$NAME.pid
STOP_MARKER=$STATE_DIR/$NAME.intentional-stop
LOCK_FILE=$STATE_DIR/$NAME.lock
STOP_TIMEOUT=${STOP_TIMEOUT:-20}
PROBE_TIMEOUT=${PROBE_TIMEOUT:-5}

line() {
  printf 'service=%s state=%s pid=%s uptime=%s reason=%s\n' \
    "$NAME" "$1" "$2" "$3" "$4"
}

boot_id() {
  cat /proc/sys/kernel/random/boot_id 2>/dev/null || printf 'unknown\n'
}

read_pid() {
  [ -s "$PID_FILE" ] || return 1
  candidate=$(cat "$PID_FILE") || return 1
  case $candidate in ''|*[!0-9]*) return 1 ;; esac
  kill -0 "$candidate" 2>/dev/null || return 1
  printf '%s\n' "$candidate"
}

uptime_of() {
  seconds=$(ps -o etimes= -p "$1" 2>/dev/null | tr -d ' ') || seconds=
  printf '%s\n' "${seconds:-0}"
}

marker_is_current() {
  [ -s "$STOP_MARKER" ] || return 1
  marker_boot=
  marker_pid=
  marker_at=
  read -r marker_boot marker_pid marker_at <"$STOP_MARKER" || return 1
  [ -n "$marker_boot" ] || return 1
  case $marker_at in ''|*[!0-9]*) return 1 ;; esac
  [ "$marker_boot" = "$(boot_id)" ]
}

marker_pid_matches() {
  marker_boot=
  marker_pid=
  marker_at=
  read -r marker_boot marker_pid marker_at <"$STOP_MARKER" || return 1
  [ "$marker_pid" = "$1" ]
}

marker_age() {
  marker_boot=
  marker_pid=
  marker_at=
  read -r marker_boot marker_pid marker_at <"$STOP_MARKER" || return 1
  printf '%s\n' "$(( $(date +%s) - marker_at ))"
}

write_marker() {
  tmp=$STOP_MARKER.tmp.$$
  printf '%s %s %s\n' "$(boot_id)" "$1" "$(date +%s)" >"$tmp" || return 1
  mv -f "$tmp" "$STOP_MARKER"
}

clear_marker() {
  rm -f "$STOP_MARKER"
}

take_lock() {
  command -v flock >/dev/null 2>&1 || return 1
  exec 9>"$LOCK_FILE" || return 1
  flock -n 9
}

probe_parts() {
  answer=$(timeout "$PROBE_TIMEOUT" "$HEALTH_CMD" "$1" 2>/dev/null) || answer=unknown
  case $answer in
    ok|waiting|error|restart) printf '%s\n' "$answer" ;;
    *) printf 'unknown\n' ;;
  esac
}

start_process() {
  exec "$SERVICE_BIN"
}

report_stopping() {
  pid=$1
  age=$(marker_age) || age=0
  if [ "$age" -lt "$STOP_TIMEOUT" ]; then
    line stopping "$pid" - stop-in-progress
    return 3
  fi
  line stopping "$pid" - stop-timeout
  return 2
}

report_running() {
  pid=$1
  result=$(probe_parts "$pid") || result=unknown
  case $result in
    ok)
      line running "$pid" "$(uptime_of "$pid")" ok
      return 0
      ;;
    waiting)
      line running "$pid" "$(uptime_of "$pid")" setup-wait
      return 3
      ;;
    restart)
      line running "$pid" "$(uptime_of "$pid")" restart-required
      return 1
      ;;
    error)
      line running "$pid" "$(uptime_of "$pid")" part-error
      return 2
      ;;
    *)
      line running "$pid" "$(uptime_of "$pid")" probe-unknown
      return 2
      ;;
  esac
}

cmd_status() {
  pid=$(read_pid) || pid=
  if [ -z "$pid" ]; then
    if marker_is_current; then
      line stopped - - operator-stop
    else
      line stopped - - crash
    fi
    return 1
  fi
  if marker_is_current && marker_pid_matches "$pid"; then
    report_stopping "$pid"
    return $?
  fi
  report_running "$pid"
}

cmd_start() {
  pid=$(read_pid) || pid=
  if [ -n "$pid" ] && marker_is_current && marker_pid_matches "$pid"; then
    report_stopping "$pid"
    return $?
  fi
  if [ -n "$pid" ]; then
    clear_marker
    report_running "$pid"
    return $?
  fi
  start_process </dev/null >>"$STATE_DIR/$NAME.log" 2>&1 9>&- &
  pid=$!
  printf '%s\n' "$pid" >"$PID_FILE.tmp.$$" && mv -f "$PID_FILE.tmp.$$" "$PID_FILE"
  sleep 0
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    line stopped - - start-failed
    return 1
  fi
  clear_marker
  line starting "$pid" 0 setup-wait
  return 3
}

cmd_stop() {
  pid=$(read_pid) || pid=
  if [ -z "$pid" ]; then
    write_marker -
    line stopped - - operator-stop
    return 1
  fi
  write_marker "$pid" || {
    line running "$pid" "$(uptime_of "$pid")" marker-failed
    return 2
  }
  kill -TERM "$pid" 2>/dev/null || true
  waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$STOP_TIMEOUT" ]; then
      line stopping "$pid" - stop-timeout
      return 2
    fi
    sleep 1
    waited=$((waited + 1))
  done
  rm -f "$PID_FILE"
  line stopped - - operator-stop
  return 1
}

cmd_restart() {
  stopped=$(cmd_stop)
  if [ $? -eq 2 ]; then
    printf '%s\n' "$stopped"
    return 2
  fi
  cmd_start
}

cmd_recover() {
  if marker_is_current; then
    pid=$(read_pid) || pid=
    if [ -z "$pid" ]; then
      line stopped - - operator-stop
      return 1
    fi
    if marker_pid_matches "$pid"; then
      report_stopping "$pid"
      return $?
    fi
    report_running "$pid"
    return $?
  fi
  cmd_start
}

with_lock() {
  if ! take_lock; then
    line unknown - - locked
    return 2
  fi
  "$@"
}

case ${1:-} in
  status)  cmd_status ;;
  start)   with_lock cmd_start ;;
  stop)    with_lock cmd_stop ;;
  restart) with_lock cmd_restart ;;
  recover) with_lock cmd_recover ;;
  *)       line unknown - - usage; exit 2 ;;
esac
exit $?
```

The two application hooks are `SERVICE_BIN`, which must run in the foreground,
and `HEALTH_CMD <pid>`, which must print exactly `ok`, `waiting`, `error`, or
`restart`. `restart` means the process is healthy but is not the current build,
so the caller replaces it; it maps to exit 1, never to 0. Any other output, an
unset command, a non-zero exit, or a run longer than `PROBE_TIMEOUT` seconds
becomes `probe-unknown` and exit 2. A hung probe must not hang the status call.
The probe is a contract, not a suggestion.

## Failure matrix

Columns: marker state, process state, probe answer, resulting code, and what the
caller does. "Current" means the marker's boot id matches this boot.

| Condition | Marker | Process | Probe | Code | Action |
|---|---|---|---:|---:|---|
| Healthy | absent or stale | alive | ok | 0 | Leave alone |
| Superseded build | absent or stale | alive | restart | 1 | Restart at a safe boundary; a live process is not healthy here |
| Still initializing | absent | alive | waiting | 3 | Poll again after the declared backoff |
| Part failed after start | absent | alive | error | 2 | Report; do not restart blindly |
| Probe missing, unreadable, or timed out | absent | alive | unknown | 2 | Report unknown health; never treat as healthy |
| Crashed | absent or previous boot | dead | not run | 1 | Restart; the crash is the fact |
| Stopped by an operator | current | dead | not run | 1 | Do not auto-restart; wait for an explicit start |
| Stop in progress | current | alive, same pid | not run | 3 | Wait up to the stop timeout |
| Stop timed out | current | alive, same pid | not run | 2 | Report; a second stop or a supervisor policy decides |
| Stale marker, service running | current, other pid | alive | any | 0, 1, 2, or 3 | Trust the process state; clear the marker on the next start |
| Start launched, not yet ready | absent | alive | waiting | 3 | Poll again |
| Start died immediately | absent | dead | not run | 1 | Report `start-failed`; do not retry in a tight loop |
| Another controller holds the lock (mutating verb) | any | any | not run | 2 | Report `locked`; retry after the holder exits |
| Unknown verb | any | any | not run | 2 | Report `usage`; fix the caller |

Two rows are worth reading twice. A stale marker with a running process must
resolve to the process state, not to `operator-stop`: the marker describes a
stop that did not complete, and the live process is the newer fact. A probe that
cannot run is an error, not a wait: waiting hides a broken health surface behind
a repeated poll.

## What this does not prove

- **No supervision.** The script does not reap children, run as PID 1, order
  startup across services, restart on its own, or survive the host's boot. It is
  the control interface a supervisor calls; the supervisor owns those duties.
- **No health of the supervised process beyond the contract.** Exit 0 means the
  probe answered `ok`, not that the service does its job. The probe's own
  coverage is the probe's claim, and this script cannot widen it.
- **No proof that the `restart` answer is right.** The script repeats what the
  probe says. A probe that flags a current build as superseded causes a needless
  restart, and a probe that misses a superseded build causes a stale process to
  keep running; neither is detectable from the control layer.
- **No absence of races.** The pid is checked, then the probe runs, then the
  line is printed. The process may die in between; the code is a snapshot, and
  the caller must handle the next call seeing a different state.
- **No pid-reuse proof.** The marker stores a pid and a boot id, not a process
  start time, so a reused pid on a long-running boot can make a marker look
  current. The stop timeout bounds the confusion but does not remove it.
- **No durable marker across a power cut.** The write is an atomic rename, which
  survives a process crash, not necessarily a power loss before the filesystem
  flushes. For power-loss durability, fsync the temp file before the rename.
- **No distributed lock.** `flock` is local to the host. Two hosts running this
  script against shared storage have two locks.
- **No proof that TERM is honoured.** The script asks; a process that ignores
  TERM yields exit 2 and keeps running. That is the contract, not a failure of
  the script to be fixed with KILL.
- **No reaping.** If the supervisor does not reap the exited process, `kill -0`
  keeps succeeding on the zombie and every stop times out. Reaping belongs to
  the supervisor; the control script cannot distinguish a zombie from a live
  process with `kill -0` alone.
- **No portability proof.** `/proc/sys/kernel/random/boot_id`, `ps -o etimes=`,
  `flock`, and `timeout` are Linux or coreutils/util-linux facilities. A
  different host needs equivalents, and the marker format stays the same.

## Cross-refs

- `../standards/work-authorization.md` -- WA-11: a state claim is not enforcement; the exit code is
- `../standards/verification-integrity.md` -- VI-03 (skipped is not passed), VI-15 (status is derived from facts)
- `../standards/durable-effects.md` -- EF-10: shutdown leaves in-flight effects and restart resumes them
- `durable-effects-reference.md` -- the effect queue this control plane may supervise
