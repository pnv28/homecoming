# VPS deployment

The hackathon deployment serves https://homecoming.pidge.dev from 2.29.103.66.
Set a DNS-only A record `homecoming` → `2.29.103.66` in the `pidge.dev` zone.
Ports 80 and 443 must reach Caddy. SSH remains on port 22.

The application lives at `/opt/homecoming`, owned by root. A dedicated
`homecoming` user runs one Uvicorn process behind Caddy. One worker is required
because sessions and background jobs are in memory. Caddy manages HTTPS and
redirects HTTP to HTTPS. Only the loopback proxy can supply trusted forwarded
headers. API keys belong to individual browser sessions and are never placed
in a service environment file.

Use a managed Python 3.12 from uv, stored at `/opt/homecoming-python`, rather
than changing Ubuntu's system Python. Install the frozen dependencies with:

```sh
UV_PYTHON_INSTALL_DIR=/opt/homecoming-python uv python install 3.12
UV_PYTHON_INSTALL_DIR=/opt/homecoming-python uv venv --python 3.12 /opt/homecoming/.venv
uv pip install --no-cache --python /opt/homecoming/.venv/bin/python -r /opt/homecoming/requirements.lock
```

Create the system user and writable cache directories before installing the unit:

```sh
useradd --system --create-home --home-dir /var/lib/homecoming --shell /usr/sbin/nologin homecoming
install -d -o homecoming -g homecoming /opt/homecoming/runtime
chown -R homecoming:homecoming /opt/homecoming/runtime /opt/homecoming/precomputed/maps/basemap
install -m 644 /opt/homecoming/deploy/homecoming.service /etc/systemd/system/homecoming.service
systemctl daemon-reload
systemctl enable --now homecoming
```

Install Caddy using its [official Ubuntu instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian),
then install the supplied configuration after the DNS record resolves:

```sh
install -m 644 /opt/homecoming/deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
systemctl enable caddy
```

After the site's HTTPS certificate works, the DNS record can be switched to
Cloudflare **Proxied**. Use **Full (strict)** under SSL/TLS so Cloudflare also
verifies the VPS certificate. Caddy continues managing the origin certificate.
Cloudflare then returns its own IP addresses in public DNS. This does not erase
the server IP from previous DNS records or prevent direct access by someone who
already knows it. See [proxy status](https://developers.cloudflare.com/dns/proxy-status/)
and [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/).

Operational commands (run over SSH as root):

```sh
systemctl status homecoming caddy --no-pager
journalctl -u homecoming -u caddy -n 80 --no-pager
curl -fsS https://homecoming.pidge.dev/api/health
```

From a development computer with the browser dependencies installed, verify the
public interface, map exports, operator review gate, and an on-demand walk with:

```sh
HOMECOMING_BASE_URL=https://homecoming.pidge.dev .venv/bin/python tests/browser_check.py
```

Set `HOMECOMING_BROWSER_PATH` to a Chromium executable on other computers, or
to an empty string to use Playwright's installed Chromium. The check uses
fictional applicants and mocked provider responses; it makes no paid API calls.

For updates, finish any previous Git/LFS operation before pulling. GitHub access
requires a repository-scoped token with Contents: read access or a read-only SSH
deploy key. Never put a token in the remote URL. Pull as root, refresh the locked
dependencies if changed, and restart the service. Restarting clears sessions and
jobs, so do it between demonstrations:

```sh
cd /opt/homecoming
git pull --ff-only origin main
uv pip install --no-cache --python .venv/bin/python -r requirements.lock
systemctl restart homecoming
```

To take the app offline after the hackathon:

```sh
systemctl disable --now homecoming caddy
```

This preserves the code and prepared data. The first LFS checkout needs about
28 GB while both the working files and LFS download cache are present. Avoid
making another full copy on the 38 GB VPS disk. Uploaded applications are
processed in memory; only reusable geographic caches are written to disk.
