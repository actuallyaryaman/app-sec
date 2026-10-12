# SE6002 disposable security lab
For teammates on Windows, macOS, or another Linux machine, use the [repository quickstart](../README.md). Its commands use Docker Compose directly and do not require a host shell script. `SCANNER_PLATFORM` defaults to `linux/amd64`; this is separate from the target image architecture.


This lab prepares actual evidence for your independent analysis. It does not supply assignment answers or precomputed findings. Only Docker, Docker Compose, and a standard shell are required on Fedora. All downloads, Git operations, scanners, Python analysis, caches, and raw reports run in containers or live in named volumes. The host contains this configuration, scripts, and explicitly exported reports only.

## Architecture and isolation

| Service | Pinned image | Purpose |
| --- | --- | --- |
| init | alpine:3.21.3 | Create private volume directories and set ownership |
| transfer | quay.io/skopeo/stable:v1.18.0 | Download target images as Docker archives without daemon access |
| git | alpine/git:2.47.2 | Full DVWA clone and detached checkout |
| trivy | aquasec/trivy:0.74.0 | Scan archives and convert JSON to tables |
| gitleaks | ghcr.io/gitleaks/gitleaks:v8.24.3 | Working tree and selected commit ancestor history scans |
| analysis / shell / export | python:3.13.2-alpine3.21 | Standard-library analysis, inspection, sanitized export |

No custom builds, package installation, Docker socket mounts, application containers, ports, host networking, or privileged containers. Containers have read-only root filesystems, dropped capabilities, no privilege escalation, and temporary `/tmp`. Only initialization uses root with ownership-related capabilities. All subsequent services use the configured numeric UID/GID. Skopeo, Git, and Trivy use a project bridge for outbound downloads; other services have no network. No service runs persistently: use `run --rm`, not `up`.

The scripts are read-only binds. Fedora `:Z` labels those binds for container access; do not run services concurrently because private SELinux labels can be reassigned between containers. The DVWA clone is never a host bind. Both named volumes receive Compose project labels and the fixed `se6002-security-lab` prefix. Do not override the project name: cleanup must address the same project.

Scanner tags are version pinned, not asserted immutable. Record resolved service digests with `docker compose images` after execution (or `docker compose config --resolve-image-digests > reports/compose-resolved.yaml` before execution). The latter requires registry connectivity. For stronger replay, use the resulting digest-qualified service images in `compose.yaml`. Do not use floating scanner tags.

## Start from clean state

Run every command from this directory. Docker daemon access is required; do not install any other tools. If daemon access is denied, use your already configured Docker environment/account access rather than changing socket permissions or installing dependencies.

```sh
cp .env.example .env
docker compose config --quiet
sh lab.sh init
sh lab.sh download
sh lab.sh clone
```

Default volume ownership is UID/GID 1000. If your account differs, edit `LAB_UID` and `LAB_GID` in `.env` before initialization. In Fedora Bash, `echo "$UID ${GROUPS[0]}"` displays your IDs without another dependency. Re-running init repairs volume ownership. The export service uses those same IDs, so the existing `reports/` directory must be writable by that account. Do not apply broad permissions to source or raw evidence.

Skopeo downloads `vulnerables/web-dvwa:latest` and `grafana/grafana:8.1.5` without loading them into Docker or running them. DVWA has no version tag in the requested target; its explicit `latest` reference is mutable. After transfer, inspect `*.inspect.json`, `*.digest.txt`, and archive checksums in `/lab/images`; record the registry digest from `inspect.json` and pin `DVWA_IMAGE` / `GRAFANA_IMAGE` to `repository@sha256:...` for fresh reconstruction. A copied-content digest can differ from the registry digest due to archive/media conversion; do not blindly use the digestfile as a registry reference. The transfer resolves the reference once and copies by that digest to avoid tag changes between inspection and copy. The resolved-reference file records the actual registry reference.

The Git clone includes full fetched history. Existing clones are not fetched automatically. `DVWA_REF=HEAD` selects the initial clone tip; copy the printed/stored full commit SHA into `.env` for reconstruction. An arbitrary commit must exist in the fetched clone; no automatic network fetch silently changes it. The clone is detached. Avoid editing the clone when collecting reproducible evidence.

## Run scans

```sh
sh lab.sh dvwa
sh lab.sh grafana
sh lab.sh secrets
sh lab.sh summary
sh lab.sh export
```

Or initialize, download, clone, run both Trivy scans, both Gitleaks modes, and show the summary:

```sh
sh lab.sh all
```

Equivalent individual scanner commands:

```sh
docker compose run --rm trivy dvwa
docker compose run --rm trivy grafana
docker compose run --rm gitleaks
```

Trivy uses `image --input <Docker archive> --scanners vuln --pkg-types os,library --list-all-pkgs --format json --exit-code 0`. `trivy convert` produces tables from that exact JSON, without rescanning with a newer database. JSON retains package inventories and metadata that tables may omit. Both categories are collected for both targets; select OS results for Task A. For Grafana inspect all application types and binary targets. Do not expect the default table alone to supply every metric.

Gitleaks uses scanner default rules through an explicit configuration, ignores target allow comments/ignore files, and uses `--redact=100`. `git --log-opts=HEAD` covers all ancestors of the recorded checkout, including merges; it does not claim to cover unrelated branches, deleted remote history, or inaccessible objects. `dir` scans the checked-out files, not historical versions. These are separate evidence sets; do not add their counts together as distinct secrets. Neither mode proves absence of secrets. Rule IDs provide rule categories, not a confirmed credential type or validity judgment.

Findings exit code is deliberately 10 for Gitleaks (recorded and treated as expected); other nonzero exits fail the workflow. Trivy findings do not cause failure; operational errors do. Each run gets a new timestamped directory, a completion exit code, version, exact commands, and logs. Check these before trusting results.

## Artifacts and inspection

Named volume `se6002-security-lab_state` contains:

- `/lab/images`: target archives, registry metadata, digests, checksums.
- `/lab/source`: DVWA working tree, `.git` history, selected SHA.
- `/lab/runs`: immutable-by-convention per-invocation raw evidence, errors, and database snapshots.
- `/lab/work`: optional private analysis files.

Named volume `se6002-security-lab_cache` holds Trivy cache/databases. Root filesystems and temporary directories are discarded when each container exits. Image layers are managed by Docker. No dependency cache is created in your host home.

```sh
sh lab.sh shell
# Inside the offline container:
ls /lab/runs
ls /lab/images
cat /lab/source/commit.txt
python /scripts/analyze.py summary
exit
```

The shell includes Python but not Git or jq; for private Git inspection use:

```sh
docker compose run --rm --entrypoint /bin/sh git
# Inside container: git -C /lab/source/DVWA show <commit>:<file>
```

Source inspection may expose real secrets: do not capture or share those terminal views. Raw Gitleaks reports are protected by private volume permissions and scanner redaction, but `Match` or other context fields could still expose surrounding text. Raw logs/JSON are never exported. Only allowlisted locations, rule IDs, tags, fingerprints, commits, and an unclassified review status appear in shared summaries. Do not display raw Gitleaks files for screenshots. Do not treat Docker volumes as encryption or a boundary against Docker administrators.

Export writes complete Trivy JSON/tables and selected provenance, plus strictly filtered Gitleaks JSON and `summary.json`, into `reports/`. It excludes source, archives, databases, and all logs. Error logs remain accessible privately inside the shell. Open exported JSON/text using your existing editor/browser; no host parser is needed. Re-export overwrites the summary; prior timestamped evidence remains. Exports can reveal source paths and dependency inventories; review before sharing.

## Counting and limitations

`analyze.py` calculates counts from actual JSON. It reports raw row counts and deduplicated vulnerability occurrences. Occurrence identity is result target/class/type, package ID (or name), installed version, package path, and advisory ID. Identical rows collapse; the same CVE in two packages or two targets remains two occurrences. Unique advisory counts and unique CVE counts are separate. Severity counts use CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN; conflicting severity assessments can place one unique advisory in multiple severity buckets, so their sum is not necessarily the unique total.

OS findings use Trivy `Class=os-pkgs`; application dependencies use `Class=lang-pkgs`. Other classes remain unclassified. Each result has its own type, target, inventory count, and severity breakdown. Only language results explicitly typed `gobinary` or `rustbinary` are called binary targets; paths alone do not establish that a result is a binary. Counts per binary represent vulnerable dependency occurrences found in that binary, not independent defects in the executable's own code. Unsupported or missing binary metadata cannot supply an exhaustive binary metric. Package inventories describe detected packages, not proof of comprehensive coverage.

CVE lookup prints installed library/version, fixed version if provided, severity, descriptions, references, and source metadata for every matching CVE-2018-18557 record. Missing matches are explicitly reported as undetected. Distribution support/EOL, advisory feeds, architecture, detector coverage, and scanner versions affect results. Use raw reports and references for your own investigation of applicability, production upgrade/rebuild options, fixed-version availability, and validation. Do not equate a missing fix with a safe deployment.

## Screenshot checklist

Capture your real terminal, including the command, date/run identifier, version/provenance where relevant, and output. Paginate in your terminal if needed; do not substitute parser tests or documentation for scanner evidence.

```sh
# Actual tool usage and evidence-run locations
sh lab.sh dvwa
sh lab.sh grafana
sh lab.sh secrets
# Actual Trivy tables
docker compose run --rm analysis table dvwa
docker compose run --rm analysis table grafana
# Severity counts and category distinctions
sh lab.sh summary
# Task A requested CVE metadata or explicit absence
sh lab.sh cve
# Task B dependency categories and individual binary severity counts
sh lab.sh binaries
# Task C locations/rules with no secret values
docker compose run --rm analysis secrets
```

Capture: (1) scanner execution and version files, (2) DVWA OS counts, (3) CVE lookup, (4) Grafana category counts, (5) binary targets with per-binary counts or explicit coverage limitation, (6) redacted Gitleaks history and working-tree results, (7) target digests, database metadata and DVWA SHA. Display version/provenance files privately through the shell; do not display source lines or raw secret-scanner logs.

## Reproducible reruns and troubleshooting

Preserve archives, exact repository SHA, scanner image digests, JSON schema, commands, and databases. Each successful Trivy run snapshots `db` and `java-db` into its own `database/` directory and records metadata and vulnerability database file checksums. These snapshots cost extra disk space. To replay one target against a saved snapshot set `OFFLINE=1` and `DB_SNAPSHOT=/lab/runs/<that-trivy-run>/database` in `.env`, then run the target scan. Replay copies the snapshot into the new run's private cache; original evidence remains unchanged. The snapshot must contain any required Java database. `OFFLINE=1` alone uses the shared cache, which could have been updated since the original run. Preserve the image archive and scanner digest too; metadata alone cannot reconstruct historical findings.

- **Database download failures / network errors:** inspect that run's `error.log` in the offline shell; retry with working DNS/proxy/registry access. Trivy defaults handle DB mirrors; consult its pinned CLI help before adding repository overrides. First-time offline scanning cannot work without a populated database. Failed copies leave `.part` files in the volume; the existing completed archive remains. Do not interpret failure as zero findings.
- **Stale data:** normal scans update DBs. Offline replay intentionally uses old data; timestamps/DB metadata distinguish it from a current assessment. Do not call frozen results current.
- **CPU architecture:** target defaults to `linux/amd64` for comparable assignment measurements. Skopeo transfers bytes and Trivy analyzes archives without executing target binaries. Scanner containers default to `SCANNER_PLATFORM=linux/amd64` for consistent tool execution. ARM64 hosts need already available Docker AMD64 emulation, or verified native scanner manifests and a deliberate `SCANNER_PLATFORM=linux/arm64` override. This lab does not install emulators. Changing TARGET_ARCH can change package findings and may fail if the target has no such manifest.
- **Archive compatibility:** Skopeo writes Docker archives accepted by Trivy `--input`; these are not `docker export` filesystem tarballs. Do not scan `.part` files. Inspect archive errors and regenerate rather than silently switching methods.
- **Permissions / SELinux:** set UID/GID before init, rerun init for volume ownership, use the provided bind labels, and run sequentially. Export needs host `reports/` write access. Do not mount your home directory or Docker socket to fix a permissions problem.
- **Unsupported flags/categories:** use `docker compose run --rm --entrypoint trivy trivy image --help`. Do not silently remove `--pkg-types` or invent binary totals; retain errors and document the scanner/schema limitation. Gitleaks CLI help is available using the analogous entrypoint override.

## Reset and complete deletion

Export first if you want to retain evidence. These explicitly named destructive commands require no additional interactive prompt:

```sh
# Reset all volume state, then initialize a fresh lab
sh lab.sh reset-delete-state
sh lab.sh init
# Completely delete lab containers, named volumes, and project network
sh lab.sh delete-lab-and-volumes
```

Both deletion commands run exactly:

```sh
docker compose down --volumes --remove-orphans --rmi local
```

This removes resources belonging to this fixed Compose project: containers, state/cache volumes (including source/history, scan evidence, work files, DB snapshots and archives), network, and locally built project images if any. There are no built images in this lab and target images are archives, so there are no uniquely owned target Docker images to delete. Versioned upstream scanner/utility images remain in Docker's shared image store: Compose cannot safely establish exclusive ownership of those images, so this lab does not delete them. There are no project-specific executable images left to remove. Never use global image/volume pruning. Configuration, `.env`, scripts, and exported `reports/` remain on the host. Host project files are intentionally preserved; delete this directory yourself only if you explicitly want to remove them too. Other Compose projects and unrelated Docker assets are untouched. Do not reuse this project name for another lab.

## Validation status

Implementation-time validation: Compose v5.6.0 accepts the configuration; all shell scripts pass syntax checks. Docker daemon access was denied, so image availability, image pulls, container startup, live scanners, parser execution, export, and destructive cleanup have **not** been runtime tested. No scan results, vulnerability counts, CVE detections, or secret findings are claimed. No host packages were installed and no target repository was cloned onto the host.

After daemon access is available, run:

```sh
docker compose config --quiet
sh lab.sh init
docker compose run --rm --entrypoint python analysis /scripts/selftest.py
sh lab.sh all
sh lab.sh cve
sh lab.sh binaries
docker compose run --rm analysis secrets
sh lab.sh export
# Review scoped resource labels before deletion (read-only)
docker compose ps -a
docker compose images
# Only after preserving the desired evidence:
sh lab.sh delete-lab-and-volumes
```

`selftest.py` checks duplicate occurrence handling, OS/application separation, explicit binary typing, missing CVE behavior, and secret-field filtering using synthetic inputs. Those fixtures are parser tests only and are never exported as security evidence. Review real results and export contents before academic use.

Technical references: [Trivy vulnerability scanning](https://trivy.dev/docs/v0.60/guide/scanner/vulnerability/), [Trivy image CLI](https://trivy.dev/docs/dev/references/configuration/cli/trivy_image/), [Gitleaks pinned CLI documentation](https://github.com/gitleaks/gitleaks/blob/v8.24.3/README.md), [Skopeo archive transfer](https://github.com/podman-container-tools/skopeo/blob/main/docs/skopeo-copy.1.md). Check the shipped CLI for this lab's pinned versions when upstream documentation differs.

Trivy archive extraction uses a per-run `/lab/runs/<run>/tmp` directory in the state volume, rather than filling the small memory-backed `/tmp`. Those intermediate files remain private until lab deletion. Allow several GB of Docker-managed disk space for archives, caches, and repeated database snapshots.
