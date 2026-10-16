#!/usr/bin/env bash
# Per-node supervisor for the single-writer, group-gated star link.
# Caller owns workspace, neutral hub endpoint and service assembly. No deploy
# defaults live here. Missing replica credentials get one sg re-exec, then fail
# loudly. Both re-exec and every watch restart use the real local source entry.
# Bash 3.2 compatible. Keep the while loop the final shell construct.

PYTHON="${PYTHON:-python3}"
ENTRY="$("$PYTHON" -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$0")" || exit 1
MODULE_DIR="$(dirname "$ENTRY")" || exit 1
WS="$("$PYTHON" "${MODULE_DIR}/platform_paths.py" "$ENTRY")" || exit 1
SYNC="${MODULE_DIR}/ssh-sync.py"
REMOTE="${AGENTS_SYNC_REMOTE:?set AGENTS_SYNC_REMOTE to host:neutral-hub-directory}"
LOG="$WS/run/logs/agents-sync.log"
mkdir -p "$WS/run/logs" || exit 1

_gid_die() {
  local msg
  msg="$(date '+%F %T') [agents-sync-loop] ERROR: process credentials lack ${REPLICA_GROUP} ($1); join the group and relaunch from a fresh login, or launch via sg ${REPLICA_GROUP}. Not entering restart loop."
  if [ /proc/self/fd/2 -ef "$LOG" ]; then
    echo "$msg" >&2
  else
    echo "$msg" >> "$LOG"
    echo "$msg" >&2
  fi
  exit 1
}

REPLICA_GROUP=replica
if ! id -Gn 2>/dev/null | tr ' ' '\n' | grep -qx "$REPLICA_GROUP"; then
  if [ -n "${AGENTS_SYNC_SG_REEXEC:-}" ]; then
    _gid_die "already attempted sg once"
  elif command -v sg >/dev/null 2>&1; then
    echo "$(date '+%F %T') [agents-sync-loop] missing $REPLICA_GROUP credentials; one sg re-exec" >> "$LOG"
    # sg uses /bin/sh -c: quote POSIX shell words, NOT Bash-only %q.
    # Pin the resolved workspace across re-exec and preserve this Bash version.
    SG_COMMAND="$("$PYTHON" -c 'import shlex, sys; print(" ".join(shlex.quote(s) for s in sys.argv[1:]))' \
      env AGENTS_SYNC_SG_REEXEC=1 "PLATFORM_WORKSPACE=$WS" "PYTHON=$PYTHON" "$BASH" "$ENTRY")" || exit 1
    exec sg "$REPLICA_GROUP" -c "$SG_COMMAND"
    _gid_die "exec sg failed"
  else
    _gid_die "sg unavailable"
  fi
fi

export SSH_SYNC_CONFIG="${SSH_SYNC_CONFIG:-$HOME/.ssh/config}"
CHILD=0
SLEEP=2
CAPPED=0
on_term() {
  echo "$(date '+%F %T') [agents-sync-loop] TERM/INT, stopping (pid $$)" >> "$LOG"
  [ "$CHILD" -ne 0 ] && kill "$CHILD" 2>/dev/null
  exit 0
}
trap on_term TERM INT

echo "$(date '+%F %T') [agents-sync-loop] started (pid $$), python=$PYTHON" >> "$LOG"
while :; do
  t0=$(date +%s)
  "$PYTHON" "$SYNC" watch "$WS/agents" "$REMOTE" \
    --debounce 0.5 --min-cycle 3 --interval 30 \
    >> "$LOG" 2>&1 &
  CHILD=$!
  wait "$CHILD" 2>/dev/null
  rc=$?
  CHILD=0
  alive=$(( $(date +%s) - t0 ))
  if [ "$alive" -lt 10 ]; then
    SLEEP=$(( SLEEP * 2 )); [ "$SLEEP" -gt 60 ] && SLEEP=60
    if [ "$SLEEP" -eq 60 ] && [ "$CAPPED" -eq 0 ]; then CAPPED=1; echo "$(date '+%F %T') [agents-sync-loop] fast failures; backoff capped at 60s" >> "$LOG"; fi
  elif [ "$alive" -ge 60 ]; then SLEEP=2; CAPPED=0; fi
  echo "$(date '+%F %T') [agents-sync-loop] watch exited rc=${rc} (${alive}s), restarting in ${SLEEP}s" >> "$LOG"
  sleep "$SLEEP" &
  CHILD=$!
  wait "$CHILD" 2>/dev/null
  CHILD=0
done
