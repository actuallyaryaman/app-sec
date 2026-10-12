# Group Project Part 2 — containerized script investigation
For teammates on Windows, macOS, or another Linux machine, see the [repository quickstart](../README.md). Build/run commands work in PowerShell, Command Prompt, Bash, and zsh. `LAB_PLATFORM` is optional and defaults to native Docker architecture; run `cd Group-Project-2` from the repository root.


Run this lab from `Group-Project-2`. It contains one non-root Python container for the two supplied assignment scripts. Nothing installs Python, pip packages, a virtual environment, a proxy, or analysis tooling on Fedora. Both downloaded files remain in this directory, are mounted read-only, and are verified against recorded SHA-256 hashes. No replacement script was downloaded.

**Transport adaptation is necessary:** both scripts require a local proxy and disable certificate checks. The runner instead makes separate transport-safe copies in a named volume, replacing only those settings. It then guards each outgoing Requests send, including redirects, with the selected exact lab hostname and TLS verification. All shopping logic stays as supplied. This difference is documented in every run and in `SCRIPT_ANALYSIS.md`. Neither script's success has been established.

## Files and storage

```text
Group-Project-2/
  infinite-money-logic-flaw.py             # supplied, unchanged
  infinite-money-logic-flaw__updated.py    # supplied, unchanged
  Dockerfile
  compose.yaml
  requirements.txt
  .env.example
  .dockerignore
  .gitignore
  README.md
  SCRIPT_ANALYSIS.md
  docker/
    entrypoint.py
    selftest.py
    sources.sha256
  logs/
    .gitkeep
```

The official Python slim image includes standard-library debugging/analysis tools. Requests and its four dependencies are version pinned. The updated script's external `diff` requires `diffutils`, installed only during the Docker build. There are no custom host dependencies. Dependency pins are recorded from [Requests](https://pypi.org/project/requests/2.34.2/), [urllib3](https://pypi.org/project/urllib3/2.8.0/), [certifi](https://pypi.org/project/certifi/2026.7.22/), [charset-normalizer](https://pypi.org/project/charset-normalizer/3.4.9/), and [idna](https://pypi.org/project/idna/3.20/). The base version follows the [official Python image source](https://github.com/docker-library/python/blob/master/3.13/slim-bookworm/Dockerfile); immutable digest pinning is explained below. Pins are reproducibility choices, not a claim that all components are vulnerability free.

The Compose project is `se6002-group-project-2`; its only runtime image is `se6002-group-project-2-lab:1`. Do not reuse those names for an unrelated project or override the project name. The project network permits outbound lab HTTPS but publishes no ports. The container has a read-only root, no capabilities, no privilege escalation, no Docker socket, no host networking, and no privileged access. `/tmp` is ephemeral. Docker volume `se6002-group-project-2_work` holds `/work/runs/<run-id>`: generated copies, provenance, optional logs, and the updated script's raw HTML/diff working files. Each run gets its own working directory, so previous files cannot contaminate a new attempt.

Only the two script files and the export-only `logs/` directory are bound from the host; unrelated home files are inaccessible. Run sequentially on Fedora: private `:Z` SELinux labels support the binds and concurrent containers could relabel them. This changes mount labels, not script contents. Logs are written to the host only when you deliberately export a run.

## Build and check — no remote traffic

```sh
cd Group-Project-2
# Optional: cp .env.example .env, then edit IDs or base image pin.
docker compose config --quiet
docker compose build
docker compose run --rm lab versions
docker compose run --rm lab check
docker compose run --rm lab help
docker compose run --rm lab selftest
docker compose run --rm lab diff
docker compose run --rm lab safety-diff original
docker compose run --rm lab safety-diff updated
```

Default UID/GID is 1000. If your account differs, set `LAB_UID`/`LAB_GID` in `.env` before building, or use Fedora Bash built-ins:

```sh
export LAB_UID="$UID" LAB_GID="${GROUPS[0]}"
docker compose build
```

Use the same IDs for build and execution; the Dockerfile pre-owns `/work` so fresh named volumes work without a root initialization service. For an existing volume created with other IDs, export needed evidence and remove that project volume using the documented deletion command, then rebuild/recreate with the intended IDs. `logs/` must be writable by your account. Do not broadly loosen evidence permissions.

For fully disposable **project build caches**, choose a dedicated builder from the start instead of using Docker's shared default builder. Buildx is part of the Docker build tooling already available in this workspace; do not install extra host tooling:

```sh
docker buildx create --name se6002-group-project-2-builder --driver docker-container
docker compose build --builder se6002-group-project-2-builder
```

This does not change the runtime architecture. The builder's cache lives in Docker-managed storage and can be deleted by removing only that builder. Do not reuse that builder for other projects. Standard Docker CLI metadata is managed by Docker itself; no Python/package cache or project environment is created in your host home. With a normal `docker compose build`, shared default-builder cache cannot be safely purged by project ownership.

## Deliberate runs against your authorized Academy lab

Start your own instance of the Academy **Infinite money logic flaw** lab and copy its HTTPS origin. The public description page at `portswigger.net` is not an execution target. Do not paste tokens, credentials, paths, queries, or fragments. A trailing slash is added automatically.

```sh
# Validation alone performs no request; replace LAB-ID with your actual instance ID.
docker compose run --rm lab validate-url https://LAB-ID.web-security-academy.net/
# These are deliberate attack runs, each requiring a URL on the command line.
docker compose run --rm lab original https://LAB-ID.web-security-academy.net/ --log
docker compose run --rm lab updated https://LAB-ID.web-security-academy.net/ --log
```

Use a different fresh instance for the second run when comparing equivalent initial states, or document the difference. Do not run both commands on a random example host. No URL is taken from environment configuration, and building, checking, starting with default `help`, exporting, or testing never launches an attack. Implementers have not executed either attack.

The runner parses the hostname, requires a proper subdomain of `web-security-academy.net`, restricts HTTPS to port 443, rejects credentials/path/query/fragment in the base URL, and locks outgoing requests/redirects to that exact hostname. The supplied sources define only relative lab endpoints and a loopback proxy; the latter is removed in generated copies. No secondary remote destinations are enabled. Certificate verification is forced; environment/script proxy choices are bypassed. Certificate errors terminate the run rather than disabling verification.

This is a guard for the inspected scripts, not a network firewall for arbitrary programs. Interactive Python/shell sessions permit private debugging but bypass the runner if you invoke other code directly. Use the provided run commands for remote execution. Editing either original causes the checksum check to refuse execution until a deliberate new source review/baseline update.

## Output, interruption, and evidence

Expect up to 500 iterations, with eight explicit HTTP calls per iteration plus any GET redirects. Duration depends on the lab/network; the assignment's 5–10 minutes is not a measured duration here. No concurrency, bulk retry, timing optimization, additional attack requests, or short timeout is introduced. The scripts themselves have no HTTP timeouts, so a stalled request may require interruption.

Terminal progress is shown in real time as timestamped lines; carriage-return progress is converted to lines for readability. The updated script's printed gift-card values are redacted. Error type and stack filename/line/function are preserved; exception messages, source snippets, locals, and response bodies are omitted because they can contain secrets. Ctrl+C interrupts the run, records exit 130, and releases the container on exit. SIGTERM also triggers an interruption; Compose stop uses SIGINT and allows 30 seconds. Already completed remote actions remain completed. Do not automatically retry a partial run.

`--log` additionally saves:

- `terminal.log`: the same timestamped/redacted stdout and stderr shown in the terminal.
- `http.jsonl`: actual per-send method, known endpoint path, start/end time, response status or exception type; no request bodies, query values, cookies, authorization headers, or response HTML.
- Gift-card submissions receive an opaque per-run reference number and a `gift_card_seen_before` boolean, making code reuse reviewable without revealing a code. These numbers are not shared across runs and do not prove redemption success.

Every run saves `metadata.json` (source/copy/runner hashes, normalized command, runtime/dependency versions, start/end, attempts, and exit code) and `safety.diff`. These are also saved without `--log`. Missing completion fields mean an incomplete run, such as a force-kill. Exit zero is **not** a solved-lab assertion. Check credit and completion manually in your browser. Neither supplied script buys the target jacket.

```sh
docker compose run --rm lab runs
# Replace RUN-ID with the exact ID printed by a completed/interrupted run.
docker compose run --rm lab export RUN-ID
```

Exports are flat, timestamped files in `logs/`, with mode 600. Only wrapper-produced metadata, redacted terminal/status logs, and the reviewed safety diff are exported. Raw `req.txt`, `req2.txt`, and `file3.txt` remain private in the named volume and are never exported automatically. Do not capture them or debugger locals for presentation screenshots. No raw unredacted terminal log is stored. Keep shared logs as produced; private container sessions can inspect raw originals without rewriting them.

```sh
docker compose run --rm lab shell
# Inside container: private inspection; use the real run ID.
ls /work/runs
cat /work/runs/RUN-ID/metadata.json
cat /work/runs/RUN-ID/http.jsonl
# Only privately: inspect updated run's req.txt/req2.txt/file3.txt if necessary.
exit
# Interactive Python; no automatic network calls:
docker compose run --rm lab python
```

For source-level debugging inside the container shell, standard `python -m pdb /opt/lab/entrypoint.py original <AUTHORIZED-LAB-URL> --log` enters the same guarded runner. This is still a deliberate remote run; do not invoke it during offline validation. Exposing response bodies, cookies, form data, or variables in the debugger may disclose credentials, so presentation evidence should use redacted logs and the browser's credit/status display instead.

## Presentation screenshot checklist

1. `versions` and `check`: actual container Python/packages, external diff availability, and original hashes.
2. `safety-diff`: transport adaptation clearly disclosed.
3. The exact `original ... --log` command and actual timestamped progress/error output.
4. Original run metadata/status log, repeated opaque card references if observed, and browser credit/order behavior supporting your conclusion.
5. `diff`: actual differences between the unmodified provided sources; reference the line numbers in `SCRIPT_ANALYSIS.md`.
6. The exact `updated ... --log` command and genuine output.
7. Updated run metadata/status log and browser credit; then the actual solved/not-solved indicator, documenting manual actions separately.

Capture starting account credit and use separate fresh instances or document shared state. Do not manufacture screenshots, infer a failure cause from a generic exception, or equate a successful checkout/redirection with a completed objective.

## Reproduction and common issues

Version pins alone do not guarantee byte-for-byte images: base tags and Debian repository availability can change. Set `PYTHON_IMAGE` in `.env` to the resolved official `python@sha256:...` digest for stricter reconstruction. Record your local build image ID through `docker compose images`, and retain `Dockerfile`, requirements, sources, baseline hashes, wrapper, source diff, and run metadata. Pip versions are fully pinned but package artifacts are not hash locked; preserve the built Docker image for identical dependency bytes. Docker image preservation, if needed, must use Docker tooling rather than host package installation. Live lab state, generated codes, timestamps, and server changes prevent deterministic remote outcomes even with an identical image.

- **Docker unavailable:** config validation still works; builds, imports, and tests need daemon access. Do not change socket permissions or install host Python to work around it.
- **Proxy/TLS failures:** the wrapper bypasses the hardcoded local proxy and forces verification. It intentionally offers no insecure/proxy mode. Diagnose CA/network configuration rather than adding `verify=False`.
- **Regex/CSRF/session failures:** use the error class and source line, HTTP statuses, and private browser/debugger inspection. A new container cannot repair an expired remote instance. Source assumptions are documented without silently fixing them.
- **Missing diff:** `check` confirms `/usr/bin/diff`; rebuild the image. Do not install diffutils on the host.
- **Package/build network errors:** retry the build deliberately once connectivity is repaired; runtime execution never auto-retries the entire workflow. Apt/pip downloads happen only in Docker build layers; caches are disabled/removed inside those layers.
- **ARM64:** the official image is selected for your Docker host architecture. The scripts run Python and diff, not target binaries. Pinned wheel/base availability must be verified by the build. No host emulation setup is introduced.
- **No logs found:** `--log` must be supplied before the run; metadata is always present but absent terminal/HTTP logs cannot be reconstructed later.
- **File permissions:** keep build/run UID/GID aligned and run Fedora binds sequentially with the supplied SELinux labels. Exported logs remain owned by the configured account.

## Cleanup, scoped to this project

Remove only raw per-run HTML/diff working files while preserving copies/logs/provenance:

```sh
docker compose run --rm lab clean-temporary-files
```

After exporting desired evidence, this explicitly destructive command removes the project containers, project network, named work volume (all run files), and the uniquely named local project image:

```sh
docker compose down --volumes --remove-orphans --rmi all
# If you created the dedicated builder above, delete its containers/cache volume too:
docker buildx rm se6002-group-project-2-builder
```

No global pruning is used. Original Python files, configuration, documents, and exported `logs/` remain on the host. Unrelated Docker resources and Group-Project-1 are unaffected. Base images/shared layers, Docker's default-builder shared cache (if used), and Docker's own CLI metadata may remain; they cannot safely be treated as exclusive project assets. A dedicated builder gives scoped deletion of this project's build cache. Do not delete a builder or image under these names if you have reused it for another project.

## Implementation validation status

Both original files were read completely. Their before/after SHA-256 hashes match. Compose v5.6.0 accepts this configuration; local Docker help confirms `build --builder` and scoped `buildx rm`. The static inspection found the required imports, external diff, writable files, proxy/TLS conflict, and source differences.

Docker daemon access is denied. The build attempt also failed because this environment disallows writing Docker's builder activity metadata under its configuration directory. No build completed. Python syntax/imports, URL/redirect guards, invocation, signal behavior, volume permissions, export, and cleanup have **not** been runtime tested. No host packages were installed, no remote attack was run, and no lab outcome is asserted.

After Docker access works, run `build`, `versions`, `check`, and `selftest` before a deliberate authorized lab run. `selftest` uses local synthetic responses only: it checks misleading-host URL rejection, normalization, redirect blocking, forced TLS/proxy removal, fragmented-output redaction, opaque card references, both scripts' usage exits without HTTP, and graceful signal metadata. Fixtures are temporary container files, are not exported, and are not remote security evidence.
