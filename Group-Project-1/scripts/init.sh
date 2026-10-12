#!/bin/sh
set -eu
umask 077
mkdir -p /lab/images /lab/source /lab/runs /lab/work /cache
chown -R "$LAB_UID:$LAB_GID" /lab /cache
chmod 700 /lab /cache
printf 'Named volumes initialized for configured UID/GID.\n'
