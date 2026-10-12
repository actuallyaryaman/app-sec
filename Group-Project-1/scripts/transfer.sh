#!/bin/sh
. /scripts/common.sh
case ${1:-all} in
  dvwa) targets=dvwa;; grafana) targets=grafana;; all) targets='dvwa grafana';; *) exit 2;;
esac
for target in $targets; do
  if [ "$target" = dvwa ]; then ref=$DVWA_IMAGE; else ref=$GRAFANA_IMAGE; fi
  new_run "transfer-$target"
  skopeo --version > "$run/version.txt"
  # Resolve once and copy by digest so a tag update cannot change the selected input.
  if digest=$(skopeo inspect --override-os linux --override-arch "$TARGET_ARCH" --format '{{.Digest}}' "docker://$ref" 2> "$run/error.log"); then :; else rc=$?; finish "$rc"; exit "$rc"; fi
  source="${ref%%@*}@$digest"
  printf '%s\n' "$source" > "$run/resolved-reference.txt"
  printf 'skopeo copy --override-os linux --override-arch %s --digestfile %s/digest.txt docker://%s docker-archive:/lab/images/%s.tar.part:lab/%s:artifact\n' "$TARGET_ARCH" "$run" "$source" "$target" "$target" > "$run/command.txt"
  if skopeo inspect --override-os linux --override-arch "$TARGET_ARCH" --raw "docker://$source" > "$run/manifest.json" 2>> "$run/error.log" &&
     skopeo inspect --override-os linux --override-arch "$TARGET_ARCH" "docker://$source" > "$run/inspect.json" 2>> "$run/error.log"; then
    if skopeo copy --override-os linux --override-arch "$TARGET_ARCH" --digestfile "$run/digest.txt" "docker://$source" "docker-archive:/lab/images/$target.tar.part:lab/$target:artifact" > "$run/stdout.log" 2>> "$run/error.log"; then
      mv "/lab/images/$target.tar.part" "/lab/images/$target.tar"
      sha256sum "/lab/images/$target.tar" > "$run/archive.sha256"
      printf '%s\n' "$ref" > "$run/reference.txt"
      printf '%s\n' "$TARGET_ARCH" > "$run/architecture.txt"
      cp "$run/inspect.json" "/lab/images/$target.inspect.json"
      for name in digest reference resolved-reference architecture; do cp "$run/$name.txt" "/lab/images/$target.$name.txt"; done
      cp "$run/archive.sha256" "/lab/images/$target.archive.sha256"
      finish 0
    else rc=$?; finish "$rc"; exit "$rc"; fi
  else rc=$?; finish "$rc"; exit "$rc"; fi
done
