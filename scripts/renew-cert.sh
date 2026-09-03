#!/usr/bin/env bash
# 續期憑證。還沒到續期時間就什麼都不做，所以可以頻繁跑。
#
#     ACME_EMAIL=you@example.com bash scripts/renew-cert.sh
#
# 排程（IP 憑證只有 6.7 天，每 6 小時檢查一次）：
#     crontab -e
#     0 */6 * * * cd /home/tku/114TKU_project_Drug-detection && \
#       ACME_EMAIL=you@example.com bash scripts/renew-cert.sh >> /tmp/cert-renew.log 2>&1
#
# ⚠️ 機器關機超過 6.7 天，IP 憑證就過期了。口試前一天先開機跑一次，
#    不要當天才發現瀏覽器跳警告。
set -euo pipefail

cd "$(dirname "$0")/.."
CERT_DIR="$PWD/deploy/certs"
ACME_DIR="$PWD/deploy/acme-challenge"
LEGO_DIR="$PWD/deploy/lego"

if [ -z "${ACME_EMAIL:-}" ]; then
    echo "❌ 請設定 ACME_EMAIL（要跟簽發時同一個，否則會註冊新帳號）" >&2
    exit 1
fi

# 從既有的憑證讀出目標名稱，不用再傳一次參數——傳錯就會簽到別的東西。
TARGET=$(ls "$LEGO_DIR/certificates/"*.crt 2>/dev/null | head -1 | xargs -r basename | sed 's/\.crt$//' || true)
if [ -z "$TARGET" ]; then
    echo "還沒有簽發過憑證，先跑 scripts/issue-cert.sh" >&2
    exit 1
fi
echo "目標：$TARGET"

if printf '%s' "$TARGET" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    PROFILE=(--profile shortlived)
    # 6.7 天的憑證，剩不到 3 天就換。Let's Encrypt 建議在剩下 1/3 效期時續。
    DAYS=3
else
    PROFILE=()
    DAYS=30
fi

BEFORE=""
[ -f "$CERT_DIR/fullchain.pem" ] && \
    BEFORE=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -enddate 2>/dev/null || true)

# lego renew 自己判斷要不要換：沒到 --days 門檻就直接結束，不會浪費額度。
docker run --rm \
    -v "$LEGO_DIR:/data" -v "$ACME_DIR:/webroot" \
    goacme/lego run \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --path /data --email "$ACME_EMAIL" \
    --http --http.webroot /webroot \
    -d "$TARGET" --accept-tos "${PROFILE[@]}" \
    2>&1 | tail -6 || {
        echo "⚠️ 續期失敗，沿用現有憑證。檢查 port 80 是否仍對外開放。" >&2
        exit 1
    }

docker run --rm -v "$LEGO_DIR:/data" -v "$CERT_DIR:/out" alpine sh -c "
    cp /data/certificates/$TARGET.crt /out/fullchain.pem &&
    cp /data/certificates/$TARGET.key /out/privkey.pem &&
    chown $(id -u):$(id -g) /out/fullchain.pem /out/privkey.pem &&
    chmod 644 /out/fullchain.pem && chmod 600 /out/privkey.pem"

AFTER=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -enddate 2>/dev/null || true)
echo "續期前：${BEFORE:-（無）}"
echo "續期後：$AFTER"

if [ "$BEFORE" != "$AFTER" ]; then
    echo "憑證有更新，重新載入 nginx。"
    # reload 不是 restart：不中斷既有連線，新連線就會用到新憑證。
    docker compose -f deploy/docker-compose.yml exec -T frontend nginx -s reload \
        && echo "✅ nginx 已重新載入" \
        || echo "⚠️ reload 失敗，請手動重啟 frontend"
else
    echo "尚未到續期時間，沒有變動。"
fi
