#!/usr/bin/env bash
# One-time (re-runnable) Pi setup. Run as root from a checkout of this repo:
#
#   sudo deploy/bootstrap.sh --domain briefer.example.com --acme-email you@example.com \
#        [--dns-provider cloudflare] [--ci-pubkey /path/to/ci_deploy_key.pub]
#
# What it does:
#   - creates the unprivileged `briefer` user (systemd lingering on)
#   - installs deploy/bin/* to /opt/briefer/bin, ROOT-owned: CI and the app can
#     run these scripts but never change them. Re-run bootstrap to update them.
#   - creates /opt/briefer/{builds,envs}, /var/lib/briefer, /etc/briefer/*.env
#   - installs the briefer@.service user unit and enables prod + staging
#   - installs the CI deploy key restricted to the briefer-entry forced command
#   - installs Caddy (with a DNS-01 provider module) and its config
#
# Safe to re-run: existing env files and data are never overwritten.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN=""
ACME_EMAIL=""
DNS_PROVIDER="cloudflare"
CI_PUBKEY=""
SKIP_CADDY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --acme-email) ACME_EMAIL="$2"; shift 2 ;;
    --dns-provider) DNS_PROVIDER="$2"; shift 2 ;;
    --ci-pubkey) CI_PUBKEY="$2"; shift 2 ;;
    --skip-caddy) SKIP_CADDY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "run as root (sudo)" >&2; exit 1; }
step() { printf '\n==> %s\n' "$*"; }

step "packages"
apt-get update -qq
apt-get install -y -qq curl ca-certificates python3 tar >/dev/null

step "briefer user"
if ! id briefer >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /home/briefer --shell /bin/bash briefer
fi
loginctl enable-linger briefer
BUID="$(id -u briefer)"

step "directories"
install -d -o root -g root -m 755 /opt/briefer /opt/briefer/bin
install -d -o briefer -g briefer -m 755 /opt/briefer/builds /opt/briefer/envs
install -d -o briefer -g briefer -m 750 /var/lib/briefer
install -d -o root -g briefer -m 750 /etc/briefer

step "deploy scripts -> /opt/briefer/bin (root-owned)"
for f in "$REPO"/deploy/bin/*; do
  case "$f" in
    *.sh|*.md) install -o root -g root -m 644 "$f" /opt/briefer/bin/ ;;
    *) install -o root -g root -m 755 "$f" /opt/briefer/bin/ ;;
  esac
done

step "environment files"
for env in common prod staging verify claude; do
  dest="/etc/briefer/$env.env"
  if [[ ! -f "$dest" ]]; then
    install -o root -g briefer -m 640 "$REPO/deploy/etc/$env.env.example" "$dest"
    echo "created $dest"
  fi
done
if [[ -n "$DOMAIN" ]]; then
  sed -i "s|^BRIEFER_PUBLIC_URL=https://briefer.example.com$|BRIEFER_PUBLIC_URL=https://$DOMAIN|" /etc/briefer/prod.env
  sed -i "s|^BRIEFER_PUBLIC_URL=https://staging.briefer.example.com$|BRIEFER_PUBLIC_URL=https://staging.$DOMAIN|" /etc/briefer/staging.env
fi

step "systemd user unit"
install -o root -g root -m 644 "$REPO/deploy/systemd/briefer@.service" /etc/systemd/user/briefer@.service
for _ in $(seq 1 20); do [[ -S "/run/user/$BUID/bus" ]] && break; sleep 0.5; done
as_briefer() { sudo -u briefer XDG_RUNTIME_DIR="/run/user/$BUID" "$@"; }
as_briefer systemctl --user daemon-reload
as_briefer systemctl --user enable briefer@prod briefer@staging >/dev/null 2>&1 || true

step "SSH deploy key"
install -d -o root -g root -m 755 /home/briefer/.ssh
if [[ -n "$CI_PUBKEY" ]]; then
  KEY="$(tr -d '\n' < "$CI_PUBKEY")"
  [[ "$KEY" =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+(\ .*)?$ ]] || { echo "expected an ssh-ed25519 public key" >&2; exit 1; }
  # Root-owned so neither the app nor the deploy scripts can add keys.
  printf 'command="/opt/briefer/bin/briefer-entry",restrict %s\n' "$KEY" > /home/briefer/.ssh/authorized_keys
  chown root:root /home/briefer/.ssh/authorized_keys
  chmod 644 /home/briefer/.ssh/authorized_keys
  echo "installed CI key (forced command: briefer-entry)"
else
  echo "no --ci-pubkey given; skipping"
fi

if [[ "$SKIP_CADDY" -eq 0 && -n "$DOMAIN" ]]; then
  step "caddy ($DNS_PROVIDER DNS-01)"
  ARCH="$(dpkg --print-architecture)"
  if ! /usr/local/bin/caddy list-modules 2>/dev/null | grep -q "dns.providers.$DNS_PROVIDER"; then
    # Caddy's official build service compiles Caddy with the DNS provider plugin.
    curl -fsSL -o /tmp/caddy "https://caddyserver.com/api/download?os=linux&arch=$ARCH&p=github.com/caddy-dns/$DNS_PROVIDER"
    install -o root -g root -m 755 /tmp/caddy /usr/local/bin/caddy
    rm -f /tmp/caddy
  fi
  id caddy >/dev/null 2>&1 || useradd --system --home-dir /var/lib/caddy --create-home --shell /usr/sbin/nologin caddy
  install -d -o root -g caddy -m 750 /etc/caddy
  install -o root -g root -m 644 "$REPO/deploy/caddy/Caddyfile" /etc/caddy/Caddyfile
  if [[ ! -f /etc/caddy/caddy.env ]]; then
    install -o root -g caddy -m 640 /dev/null /etc/caddy/caddy.env
    cat > /etc/caddy/caddy.env <<ENV
BRIEFER_HOST=$DOMAIN
BRIEFER_STAGING_HOST=staging.$DOMAIN
ACME_EMAIL=$ACME_EMAIL
# DNS provider API token with permission to edit TXT records for $DOMAIN's zone.
DNS_API_TOKEN=
ENV
  fi
  if [[ ! -f /etc/caddy/tls.caddy ]]; then
    if [[ "$DNS_PROVIDER" == "cloudflare" ]]; then
      printf 'tls {\n\tdns cloudflare {env.DNS_API_TOKEN}\n}\n' > /etc/caddy/tls.caddy
    else
      printf '# TODO: configure the %s provider, see https://github.com/caddy-dns/%s\ntls {\n\tdns %s {env.DNS_API_TOKEN}\n}\n' \
        "$DNS_PROVIDER" "$DNS_PROVIDER" "$DNS_PROVIDER" > /etc/caddy/tls.caddy
    fi
  fi
  cat > /etc/systemd/system/caddy.service <<'UNIT'
[Unit]
Description=Caddy
After=network-online.target
Wants=network-online.target

[Service]
User=caddy
Group=caddy
EnvironmentFile=/etc/caddy/caddy.env
ExecStart=/usr/local/bin/caddy run --environ --config /etc/caddy/Caddyfile
ExecReload=/usr/local/bin/caddy reload --config /etc/caddy/Caddyfile --force
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable caddy >/dev/null
  if grep -q '^DNS_API_TOKEN=.\+' /etc/caddy/caddy.env; then
    systemctl restart caddy
  else
    echo "set DNS_API_TOKEN in /etc/caddy/caddy.env, then: sudo systemctl restart caddy"
  fi
fi

step "done"
cat <<NEXT
Next steps (see docs/dev-loop.md, "One-time setup"):
  1. Fill in /etc/briefer/common.env (API keys) and staging/verify TODOIST_PROJECT_ID.
  2. Claude verify pass: either \`sudo -iu briefer claude\` and log in once, or
     \`sudo -iu briefer claude setup-token\` and paste it into /etc/briefer/claude.env.
  3. Host key for the PI_KNOWN_HOSTS GitHub secret (prefix it with the Pi's NetBird IP):
     $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub 2>/dev/null || echo "ssh-keyscan -t ed25519 <pi>")
  4. After the first promote, create the PocketBase superuser:
     sudo -u briefer /opt/briefer/envs/prod/current/pocketbase superuser upsert you@example.com '<password>' --dir /var/lib/briefer/prod
NEXT
