#!/bin/bash
# Cài đặt hoặc cập nhật Be The Agent (chanme) trên VPS Ubuntu (systemd, phía sau cloudflared).
# Dùng: sudo bash install.sh <thư mục bundle> [file secrets]
# Không in secret ra màn hình; file secrets tạm bị shred sau khi nạp.
set -euo pipefail

B=$1
S=${2:-}

id chanme >/dev/null 2>&1 || useradd --system --home /opt/chanme --shell /usr/sbin/nologin chanme
mkdir -p /opt/chanme /etc/chanme /var/lib/chanme/output

rm -rf /opt/chanme/codebase /opt/chanme/deploy
cp -r "$B/codebase" /opt/chanme/
cp -r "$B/deploy" /opt/chanme/
ln -sfn /var/lib/chanme/output /opt/chanme/output
cp "$B/chanme.service" /etc/systemd/system/chanme.service

chown -R root:root /opt/chanme/codebase /opt/chanme/deploy
# Khắc phục quyền 700 khi scp từ Windows
chmod -R u=rwX,go=rX /opt/chanme/codebase /opt/chanme/deploy
chown -R chanme:chanme /var/lib/chanme
chmod 750 /var/lib/chanme /var/lib/chanme/output

get() { { grep -E "^$1=" "$S" || true; } | head -1 | cut -d= -f2- | tr -d '\r'; }

if [ -n "$S" ] && [ -f "$S" ]; then
  umask 027
  PROVIDER=$(get MODEL_PROVIDER); [ -n "$PROVIDER" ] || PROVIDER=gemini
  MNAME=$(get MODEL_NAME); [ -n "$MNAME" ] || MNAME=gemini-3.8-flash
  APIKEY=$(get GEMINI_API_KEY)
  HOST_V=$(get CHANME_HOST); [ -n "$HOST_V" ] || HOST_V=chanme.arsneonci.space
  SECRET_V=$(get WEB_SECRET)
  [ -n "$SECRET_V" ] || SECRET_V=$({ grep -E '^WEB_SECRET=' /etc/chanme/chanme.env 2>/dev/null || true; } | head -1 | cut -d= -f2-)
  [ -n "$SECRET_V" ] || SECRET_V=$(python3 -c "import secrets;print(secrets.token_hex(32))")
  {
    echo "MODEL_PROVIDER=$PROVIDER"
    echo "MODEL_NAME=$MNAME"
    echo "GEMINI_API_KEY=$APIKEY"
    echo "CHANME_HOST=$HOST_V"
    echo "CHANME_BIND=127.0.0.1"
    echo "CHANME_PORT=8795"
    echo "WEB_SECRET=$SECRET_V"
    echo "PYTHONDONTWRITEBYTECODE=1"
    echo "PYTHONIOENCODING=utf-8"
  } > /etc/chanme/chanme.env
  chown root:chanme /etc/chanme/chanme.env
  chmod 640 /etc/chanme/chanme.env
  shred -u "$S" 2>/dev/null || rm -f "$S"
fi

systemctl daemon-reload
systemctl enable chanme >/dev/null 2>&1
systemctl restart chanme
sleep 2
systemctl is-active chanme
curl -fsS http://127.0.0.1:8795/health && echo " <- chanme local health"
