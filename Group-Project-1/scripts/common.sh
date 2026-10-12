set -eu
umask 077
new_run() {
  kind=$1
  run=$(mktemp -d "/lab/runs/$(date -u +%Y%m%dT%H%M%SZ)-$kind-XXXXXX")
  date -u +%Y-%m-%dT%H:%M:%SZ > "$run/started.txt"
  trap 'rc=$?; if [ ! -f "$run/exit-code.txt" ]; then printf "Incomplete invocation: exit %s\n" "$rc" >> "$run/error.log"; finish "$rc"; fi' 0
}
finish() {
  printf '%s\n' "$1" > "$run/exit-code.txt"
  date -u +%Y-%m-%dT%H:%M:%SZ > "$run/finished.txt"
  printf 'Evidence: %s (exit %s)\n' "$run" "$1"
}
