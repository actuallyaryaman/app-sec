#!/bin/sh
. /scripts/common.sh
[ -f /lab/source/commit.txt ]
for mode in git dir; do
  new_run "gitleaks-$mode"
  gitleaks version > "$run/version.txt"
  cp /lab/source/commit.txt "$run/commit.txt"
  git -C /lab/source/DVWA rev-parse HEAD > "$run/actual-commit.txt" 2> "$run/error.log"
  cmp "$run/commit.txt" "$run/actual-commit.txt" > /dev/null || {
    printf 'Checkout differs from recorded SHA; rerun clone with the intended DVWA_REF.\n' >> "$run/error.log"
    exit 2
  }
  git -C /lab/source/DVWA status --porcelain > "$run/status.txt" 2>> "$run/error.log"
  [ ! -s "$run/status.txt" ] || {
    printf 'Checkout has local changes; restore a clean checkout before scanning.\n' >> "$run/error.log"
    exit 2
  }
  set -- "$mode" /lab/source/DVWA --config /scripts/gitleaks.toml --gitleaks-ignore-path /tmp/nonexistent-ignore --ignore-gitleaks-allow --redact=100 --no-banner --no-color --report-format json --report-path "$run/gitleaks.json" --exit-code 10
  # History restricted to ancestors of the recorded checkout, not mutable remote refs.
  if [ "$mode" = git ]; then set -- "$@" --log-opts=HEAD; fi
  printf 'gitleaks' > "$run/command.txt"
  for arg in "$@"; do printf ' %s' "$arg" >> "$run/command.txt"; done
  printf '\n' >> "$run/command.txt"
  cp /scripts/gitleaks.toml "$run/config.toml"
  if gitleaks "$@" > "$run/stdout.log" 2> "$run/error.log"; then rc=0; else rc=$?; fi
  finish "$rc"
  case $rc in 0|10) ;; *) exit "$rc";; esac
done
