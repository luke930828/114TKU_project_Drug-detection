#!/usr/bin/env bash
# 續期憑證。沒到期就什麼都不做，所以可以每天跑。
#
#     bash scripts/renew-cert.sh
#
# 建議排程（每天早上 6 點）：
#     crontab -e
#     0 6 * * * cd /home/tku/114TKU_project_Drug-detection && bash scripts/renew-cert.sh >> /tmp/cert-renew.log 2>&1
#
# ⚠️ IP 憑證只有 6 天效期，機器關機超過 6 天就會過期。
#    口試前一天記得先開機跑一次，不要當天才發現瀏覽器跳警告。
set -euo pipefail

cd "$(dirname "$0")/.."
CERT_DIR="$PWD/deploy/certs"
ACME_DIR="$PWD/deploy/acme-challenge"
LE_DIR="$PWD/deploy/letsencrypt"

if [ ! -d "$LE_DIR/live" ]; then
    echo "還沒有簽發過憑證，先跑 scripts/issue-cert.sh" >&2
    exit 1
fi

BEFORE=""
[ -f "$CERT_DIR/fullchain.pem" ] && \
    BEFORE=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -enddate 2>/dev/null || true)

docker run --rm \
    -v "$LE_DIR:/etc/letsencrypt" \
    -v "$ACME_DIR:/var/www/certbot" \
    certbot/certbot renew \
    --webroot -w /var/www/certbot \
    --non-interactive

# 不管有沒有實際續到都複製一次——certbot 判斷「還不用續」時會直接跳過，
# 這時複製的是舊檔，沒有副作用；真的續了才會有新內容。
UPDATED=0
for LIVE in "$LE_DIR"/live/*/; do
    [ -f "$LIVE/fullchain.pem" ] || continue
    cp -L "$LIVE/fullchain.pem" "$CERT_DIR/fullchain.pem"
    cp -L "$LIVE/privkey.pem"   "$CERT_DIR/privkey.pem"
    chmod 600 "$CERT_DIR/privkey.pem"
    UPDATED=1
done
[ "$UPDATED" = "1" ] || { echo "找不到任何 live 憑證" >&2; exit 1; }

AFTER=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -enddate 2>/dev/null || true)
echo "續期前：${BEFORE:-（無）}"
echo "續期後：$AFTER"

if [ "$BEFORE" != "$AFTER" ]; then
    echo "憑證有更新，重新載入 nginx。"
    # reload 而不是 restart：不中斷連線，nginx 會用新憑證服務新連線。
    docker compose -f deploy/docker-compose.yml exec -T frontend nginx -s reload \
        && echo "✅ nginx 已重新載入" \
        || echo "⚠️ reload 失敗，請手動重啟 frontend"
else
    echo "尚未到續期時間，沒有變動。"
fi
