#!/bin/sh
. /scripts/common.sh
new_run clone
 git --version > "$run/version.txt"
printf 'git clone https://github.com/digininja/DVWA.git /lab/source/DVWA; git checkout --detach %s\n' "$DVWA_REF" > "$run/command.txt"
if [ ! -d /lab/source/DVWA/.git ]; then
  if git clone https://github.com/digininja/DVWA.git /lab/source/DVWA > "$run/stdout.log" 2> "$run/error.log"; then :; else rc=$?; finish "$rc"; exit "$rc"; fi
fi
if git -C /lab/source/DVWA checkout --detach "$DVWA_REF" >> "$run/stdout.log" 2>> "$run/error.log"; then :; else rc=$?; finish "$rc"; exit "$rc"; fi
git -C /lab/source/DVWA rev-parse HEAD > /lab/source/commit.txt
cp /lab/source/commit.txt "$run/commit.txt"
git -C /lab/source/DVWA status --porcelain > "$run/status.txt"
finish 0
