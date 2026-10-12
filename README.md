# SE6002 Application Security — team labs

One repository contains two independent, disposable Docker labs:

| Directory | Purpose | Detailed instructions |
| --- | --- | --- |
| `Group-Project-1` | Trivy image scans and DVWA Gitleaks scans | [Part 1 README](Group-Project-1/README.md) |
| `Group-Project-2` | Investigate the two supplied infinite-money Python scripts | [Part 2 README](Group-Project-2/README.md), [source analysis](Group-Project-2/SCRIPT_ANALYSIS.md) |

Each teammate gets their own containers, networks, named volumes, and lab instance. Neither project requires host Python, pip, Git for DVWA, jq, Make, or scanner installations. Docker and Docker Compose are the lab runtime dependencies. Git is optional for acquiring/managing this repository: teammates may instead download and extract its ZIP through their browser. Repository acquisition is separate from the Part 1 DVWA clone, which remains in a Docker volume.

## Supported machines and honest limits

The intended baseline is a 64-bit Windows, macOS, or Linux machine with a working **Linux-container** Docker engine and Compose v2 or newer. Start Docker Desktop on Windows/macOS; use Linux containers on Windows, not Windows container mode. Linux users may use their already configured Docker Engine or Docker Desktop. Docker must have permission to access its daemon and downloaded images. Windows virtualization/WSL requirements are part of [Docker Desktop's supported setup](https://docs.docker.com/desktop/setup/install/windows-install/), not dependencies installed by these labs.

| Machine | Part 1 scanners | Part 2 runner |
| --- | --- | --- |
| Intel/AMD x86-64 Linux/Windows/macOS | Default `linux/amd64` | Native Linux image build |
| Apple Silicon macOS | Default AMD64 scanners require Docker Desktop's available AMD64 emulation | Native ARM64 build |
| ARM64 Linux | Use AMD64 only if emulation is already available; otherwise verify all scanner image ARM64 manifests before changing `SCANNER_PLATFORM` | Native ARM64 build |
| ARM64 Windows | Requires a supported Docker Desktop/WSL Linux-container configuration and AMD64 emulation for default Part 1 | Native ARM64 build where Docker supports it |
| 32-bit CPUs, unsupported OS, no virtualization/usable Docker backend | Not supported | Not supported |

Docker cannot make unsupported hardware or missing architecture manifests disappear. This repository does not install emulators, register host binary handlers, or run privileged setup containers. If your Docker setup cannot execute the selected scanner architecture, Part 1 will fail visibly; use a compatible Docker machine rather than silently changing scan coverage. On ARM64, native scanner support must be verified before opting out of the AMD64 baseline. The CI matrix tests the parser/Part 2 runner on Linux x86-64 and ARM64, not all Part 1 scanner images or every desktop environment.

Part 1 separates `SCANNER_PLATFORM` (tool execution) from `TARGET_ARCH` (image bytes being investigated). Both default to AMD64, so teammates analyze the same target architecture. Skopeo and Trivy do not execute DVWA/Grafana binaries; no vulnerable app is started. Part 2 uses native architecture by default; optional `LAB_PLATFORM=linux/amd64` selects an emulated build/runtime explicitly when supported. Emulation can be slower.

Allow several GB of Docker disk space, especially for Part 1 archives/database snapshots. Internet access to image/package registries and databases is required for initial setup. Part 2's deliberate attack runs require access to your own authorized Academy instance. Available hardware resources, remote lab changes, registry availability, and database updates affect behavior; identical code does not imply identical remote results.

## Get the repository

Once a remote repository has been published, clone its URL using an existing Git installation, or download its ZIP without installing Git. No remote is configured or published by this implementation. In an ordinary writable checkout, initialize a repository with:

```text
git init -b main
git add .
git commit -m "Initialize SE6002 security labs"
```

The entire `AppSec` directory is one repository, with standard metadata in the root `.git` directory. Both project folders share its history. From the repository root, use:

```text
git status
git log --oneline
```

You can add a chosen remote later using standard Git commands. Git metadata is not a lab dependency or included in project image build contexts. No remote target URL/credential is stored in the repository.

## Common preflight

These commands work in PowerShell, Command Prompt, Bash, and zsh; run them from the repository root:

```text
docker --version
docker compose version
docker info
docker compose -f Group-Project-1/compose.yaml config --quiet
docker compose -f Group-Project-2/compose.yaml config --quiet
```

Keep the whole extracted repository together, including the empty `reports/` and `logs/` directories. Relative Compose paths are resolved from each project's Compose file, so checkout location and path spaces do not require editing configurations. Do not rename the assignment script files. Use a local checkout with a local Docker engine: bind-mounted files must exist on the Docker engine's machine; an arbitrary remote context is not automatically supported.

No `.env` file is required for the defaults. For overrides, copy that project's `.env.example` to `.env` using your file manager/editor. On macOS/Windows Docker Desktop, keep UID/GID defaults unless you have a specific mapped-permission issue. On Linux, set `LAB_UID`/`LAB_GID` to your account's numeric IDs before initialization/build if they differ from 1000; this permits host report export without root. Your existing shell/user settings can provide those IDs. Part 1 init fixes volume ownership; Part 2's IDs must match at build/run time. These are per-machine settings and `.env` is ignored by Git.

Windows checkouts are protected by `.gitattributes`: orchestration files use LF, while the supplied assignment scripts bypass line-ending conversion entirely so their hashes remain identical. Do not let an editor reformat those originals. PowerShell users do not need Bash, Git Bash, WSL shell commands, or the optional Part 1 `lab.sh` wrapper to operate the labs; use Compose below.

## Part 1 — same commands on every supported OS

From the repository root:

```text
cd Group-Project-1
docker compose run --rm init
docker compose run --rm transfer all
docker compose run --rm git
docker compose run --rm trivy dvwa
docker compose run --rm trivy grafana
docker compose run --rm gitleaks
docker compose run --rm analysis summary
docker compose run --rm export
```

To inspect findings and collect genuine screenshots:

```text
docker compose run --rm analysis table dvwa
docker compose run --rm analysis table grafana
docker compose run --rm analysis cve
docker compose run --rm analysis binaries
docker compose run --rm analysis secrets
```

To test only the parser, without downloading targets or scanning DVWA:

```text
docker compose run --rm init
docker compose run --rm --entrypoint python analysis /scripts/selftest.py
```

Exports appear in `Group-Project-1/reports/`. Target archives, full DVWA clone/history, scanner caches, raw evidence, and database snapshots stay in local named volumes. Do not compare teammate counts as equivalent unless target image digests, target architecture, scanner versions, database snapshots, flags, and repository SHA agree. See the Part 1 README for frozen replay and screenshot details.

## Part 2 — offline checks, then an explicit authorized run

Open a terminal at the repository root:

```text
cd Group-Project-2
docker compose build
docker compose run --rm lab versions
docker compose run --rm lab check
docker compose run --rm lab selftest
docker compose run --rm lab diff
docker compose run --rm lab safety-diff original
docker compose run --rm lab safety-diff updated
```

Offline tests use mocked responses and never launch a remote attack. For a deliberate run, replace `LAB-ID` with your own active instance. Use fresh instances for a fair comparison or record shared state:

```text
docker compose run --rm lab original https://LAB-ID.web-security-academy.net/ --log
docker compose run --rm lab updated https://LAB-ID.web-security-academy.net/ --log
docker compose run --rm lab runs
docker compose run --rm lab export RUN-ID
```

Exports appear in `Group-Project-2/logs/`. Private response files, generated transport-safe copies, and raw working state stay in named volumes. Each teammate must use their own authorized lab. Ctrl+C interrupts; a zero exit status is not proof of completion. Record the browser's balance/solved indicator, and note manual steps separately.

## Git hygiene and collaboration

Root ignore rules exclude local agent/cloud configuration, `.env` files, private keys, caches, and raw/exported evidence. Empty report/log directories are retained via `.gitkeep`. All project configuration, documentation, tools, and supplied scripts are intended to be versioned. The supplied scripts contain public training credentials; they are not real account credentials. Never add your real cookies, passwords, lab tokens, or raw HTML to Git.

Share reviewed, sanitized evidence through your team's chosen channel, or explicitly force-add only files you have checked. Keep machine-specific `.env` overrides local. Do not commit result files simply to make teammate counts match. The two Compose project names are distinct; cleanup of one does not affect the other. Multiple checkouts of the same project on one Docker engine share that fixed project's volumes, so do not run those concurrently or use them as independent experiments.

## CI and verification status

`.github/workflows/validate.yaml` configures offline checks on GitHub Linux x86-64 and ARM64 runners, using a commit-pinned checkout action. It validates both Compose files, executes Part 1's synthetic parser tests, and builds/checks/tests Part 2. It never supplies a remote lab URL or runs either attack script. It does not claim to perform real vulnerability scans. [GitHub documents the selected runner architectures](https://docs.github.com/en/actions/reference/runners/github-hosted-runners); private repositories need suitable Actions access/minutes.

Local Compose validation, ignore-rule checks, original source checksums, and Git line-ending attribute checks were performed. Docker execution is unavailable in this managed workspace, so images, emulation, offline tests, export, cleanup, and desktop OS compatibility remain runtime-unverified. CI has been configured but has not yet run. Teammates should run the preflight/offline tests before collecting evidence; failures are evidence to diagnose, not fabricated zero findings.

## Delete only one lab

From `Group-Project-1`:

```text
docker compose down --volumes --remove-orphans --rmi local
```

From `Group-Project-2`:

```text
docker compose down --volumes --remove-orphans --rmi all
```

If you used the Part 2 README's optional dedicated builder, also remove only that builder with `docker buildx rm se6002-group-project-2-builder`. No global pruning. Git/source files and exported reports/logs remain; named volumes and their private evidence are deleted. Shared upstream images/layers and default builder caches are preserved where exclusive project ownership cannot be established.
