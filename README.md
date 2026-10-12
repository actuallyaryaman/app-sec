# SE6002 Application Security

Two Docker labs in one repository:

- **[Part 1](Group-Project-1/README.md):** Trivy scans of DVWA/Grafana and Gitleaks scans of DVWA.
- **[Part 2](Group-Project-2/README.md):** Run and compare the supplied infinite-money scripts. [Code analysis](Group-Project-2/SCRIPT_ANALYSIS.md).

## Requirements

Docker with Linux containers and Compose v2+. Windows/macOS users can use Docker Desktop. All lab tools run in containers.

Part 1 uses AMD64 scanners; ARM machines need AMD64 emulation. Part 2 builds for your machine's architecture. On Linux, if your UID/GID differs from 1000, set `LAB_UID` and `LAB_GID` in each project's `.env` before setup.

Clone this repository or [download its ZIP](https://github.com/actuallyaryaman/app-sec/archive/refs/heads/main.zip):

```text
git clone https://github.com/actuallyaryaman/app-sec.git
cd app-sec
```

## Part 1

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

Sanitized reports are exported to `Group-Project-1/reports/`.

## Part 2

From the repository root:

```text
cd Group-Project-2
docker compose build
docker compose run --rm lab diff
```

Replace `LAB-ID` with your own Academy instance. Use a fresh instance for each comparison run.

```text
docker compose run --rm lab original https://LAB-ID.web-security-academy.net/ --log
docker compose run --rm lab updated https://LAB-ID.web-security-academy.net/ --log
docker compose run --rm lab runs
docker compose run --rm lab export RUN-ID
```

Replace `RUN-ID` with the ID printed by `lab runs`. Redacted logs are exported to `Group-Project-2/logs/`.

The runner keeps the originals unchanged and runs separate copies with direct HTTPS and TLS verification. Ctrl+C stops a run. Check completion in the browser; neither script purchases the jacket.

## Cleanup

Run inside the project directory. These commands delete its containers, volumes, and network. Source files and exported reports/logs remain.

**Part 1:**

```text
docker compose down --volumes --remove-orphans --rmi local
```

**Part 2** (also removes its built image):

```text
docker compose down --volumes --remove-orphans --rmi all
```

Keep `.env`, cookies, raw responses, and unredacted evidence out of Git. See each project's README for inspection commands, screenshots, troubleshooting, and optional builder cleanup.
