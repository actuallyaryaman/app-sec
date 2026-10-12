#!/bin/sh
. /scripts/common.sh
target=${1:?Use dvwa or grafana}
case $target in dvwa|grafana) ;; *) exit 2;; esac
[ -f "/lab/images/$target.tar" ]
new_run "trivy-$target"
cache_dir=/cache
mkdir -p "$run/tmp"
TMPDIR="$run/tmp"
export TMPDIR
if [ -n "${DB_SNAPSHOT:-}" ]; then
  [ "$OFFLINE" = 1 ] || { echo "DB_SNAPSHOT requires OFFLINE=1" >&2; exit 2; }
  [ -d "$DB_SNAPSHOT/db" ]
  cache_dir="$run/replay-cache"
  mkdir -p "$cache_dir"
  cp -R "$DB_SNAPSHOT"/. "$cache_dir/"
fi
trivy --version --cache-dir "$cache_dir" > "$run/version-before.txt" 2> "$run/error.log"
cp /lab/images/"$target".*.txt "$run/"
cp "/lab/images/$target.inspect.json" "$run/target-inspect.json"
cp "/lab/images/$target.archive.sha256" "$run/archive.sha256"
set -- image --cache-dir "$cache_dir" --input "/lab/images/$target.tar" --scanners vuln --pkg-types os,library --list-all-pkgs --format json --output "$run/trivy.json" --exit-code 0 --timeout 30m
if [ "$OFFLINE" = 1 ]; then set -- "$@" --skip-db-update --skip-java-db-update --offline-scan; fi
printf 'trivy' > "$run/command.txt"
for arg in "$@"; do printf ' %s' "$arg" >> "$run/command.txt"; done
printf '\n' >> "$run/command.txt"
if trivy "$@" > "$run/stdout.log" 2>> "$run/error.log"; then
  trivy --version --cache-dir "$cache_dir" > "$run/version.txt" 2>> "$run/error.log"
  [ ! -f "$cache_dir/db/metadata.json" ] || cp "$cache_dir/db/metadata.json" "$run/db-metadata.json"
  [ ! -f "$cache_dir/java-db/metadata.json" ] || cp "$cache_dir/java-db/metadata.json" "$run/java-db-metadata.json"
  mkdir -p "$run/database"
  [ ! -d "$cache_dir/db" ] || cp -R "$cache_dir/db" "$run/database/"
  [ ! -d "$cache_dir/java-db" ] || cp -R "$cache_dir/java-db" "$run/database/"
  [ ! -f "$cache_dir/db/metadata.json" ] || sha256sum "$cache_dir"/db/* > "$run/database.sha256"
  printf 'trivy convert --format table --output %s/table.txt %s/trivy.json\n' "$run" "$run" >> "$run/command.txt"
  if trivy convert --format table --output "$run/table.txt" "$run/trivy.json" 2>> "$run/error.log"; then finish 0; else rc=$?; finish "$rc"; exit "$rc"; fi
else rc=$?; finish "$rc"; exit "$rc"; fi
