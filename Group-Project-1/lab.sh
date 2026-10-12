#!/bin/sh
# Host orchestration only: shell + Docker Compose. Always run from this directory.
set -eu
case ${1:-help} in
 init) docker compose run --rm init;;
 download) docker compose run --rm transfer "${2:-all}";;
 clone) docker compose run --rm git;;
 dvwa|grafana) docker compose run --rm trivy "$1";;
 secrets) docker compose run --rm gitleaks;;
 all)
  docker compose run --rm init
  docker compose run --rm transfer all
  docker compose run --rm git
  docker compose run --rm trivy dvwa
  docker compose run --rm trivy grafana
  docker compose run --rm gitleaks
  docker compose run --rm analysis summary;;
 summary|cve|binaries) docker compose run --rm analysis "$1";;
 export) docker compose run --rm export;;
 shell) docker compose run --rm shell;;
 reset-delete-state|delete-lab-and-volumes)
  docker compose down --volumes --remove-orphans --rmi local;;
 *) printf '%s\n' 'Usage: sh lab.sh init|download [dvwa|grafana|all]|clone|dvwa|grafana|secrets|all|summary|cve|binaries|export|shell|reset-delete-state|delete-lab-and-volumes';;
esac
