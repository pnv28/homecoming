#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    printf '%s\n' 'Usage: ~/update-homecoming.sh [--check|--help]' \
        'Pull GitHub main, install locked dependencies, restart Homecoming, and check health.' \
        'Restarting clears active sessions and background jobs.' \
        '--check: run preflight checks without downloading or restarting anything.'
}

case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    ''|--check) ;;
    *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then usage >&2; exit 2; fi
if (( EUID != 0 )); then
    printf '%s\n' 'Run this script as root on the Homecoming VPS.' >&2
    exit 1
fi

for command in git uv curl systemctl flock chown install chmod; do
    command -v "$command" >/dev/null || { printf 'Missing command: %s\n' "$command" >&2; exit 1; }
done
cd /opt/homecoming
test -x .venv/bin/python
if [[ "$(git branch --show-current)" != main ]]; then
    printf '%s\n' 'The server checkout must be on main. No changes were made.' >&2
    exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
    printf '%s\n' 'The server checkout has local changes. Review them before updating:' >&2
    git status --short >&2
    exit 1
fi
if [[ "${1:-}" == --check ]]; then
    printf '%s\n' 'Preflight checks passed. No update performed.'
    exit 0
fi

exec 9>/run/lock/homecoming-update.lock
flock -n 9 || { printf '%s\n' 'Another Homecoming update is already running.' >&2; exit 1; }
trap 'printf "Update stopped at line %s. See the error above; no changes were discarded.\n" "$LINENO" >&2' ERR

printf '%s\n' 'Pulling GitHub main. If prompted, use your GitHub username and PAT as the password.'
git -c credential.helper='cache --timeout=3600' pull --ff-only origin main
uv pip install --no-cache --python .venv/bin/python -r requirements.lock
chown -R homecoming:homecoming runtime precomputed/maps/basemap
if [[ ! -f .env ]]; then
    install -m 600 .env.example .env
fi
chmod 600 .env
chown root:root .env
install -m 644 deploy/homecoming.service /etc/systemd/system/homecoming.service
systemctl daemon-reload
printf '%s\n' 'Restarting Homecoming. Active sessions and jobs will be cleared.'
systemctl restart homecoming
curl --fail --silent --show-error --retry 12 --retry-connrefused --retry-delay 2 \
    --connect-timeout 5 --max-time 15 http://127.0.0.1:8000/api/health >/dev/null
systemctl is-active --quiet homecoming
printf 'Homecoming updated to %s. Open https://homecoming.pidge.dev\n' "$(git rev-parse --short HEAD)"
