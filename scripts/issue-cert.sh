#!/usr/bin/env bash
# 用 Let's Encrypt 簽發憑證。網域與 IP 位址都可以。
#
#     ACME_EMAIL=you@example.com bash scripts/issue-cert.sh 163.13.202.107
#     ACME_EMAIL=you@example.com bash scripts/issue-cert.sh drugdetect.tku.edu.tw
#     ACME_EMAIL=... bash scripts/issue-cert.sh 163.13.202.107 --staging
#
# 為什麼用 lego 不用 certbot
# ─────────────────────────
# Let's Encrypt 的 shortlived profile 支援 IP identifier——官方 profile 表格
# 寫著 Identifier Types: DNS, IP，效期 160 小時。但 certbot 5.8.0 會在客戶端
# 就擋掉：
#
#     Requested name 163.13.202.107 is an IP address.
#     The Let's Encrypt certificate authority will not issue certificates
#     for a bare IP address.
#
# 那是 certbot 自己的檢查，不是伺服器拒絕。lego 5.4.1 送得出去——
# 2026-09-03 實測對 staging 成功拿到 SAN 為 IP Address:163.13.202.107 的憑證。
#
# 前提（沒滿足一定失敗，腳本會先檢查）：
#   1. port 80 從網際網路連得到——ACME 伺服器要主動連進來驗證
#   2. frontend 容器正在跑（挑戰檔由它從 /var/www/certbot 提供）
#
# ⚠️ IP 憑證只有 6.7 天效期，renew-cert.sh 一定要排進排程；
#    機器關機超過一週憑證就過期。網域是 90 天，好管理得多。
set -euo pipefail

cd "$(dirname "$0")/.."
TARGET="${1:-}"
shift || true
STAGING=0
for arg in "$@"; do
    [ "$arg" = "--staging" ] && STAGING=1
done

if [ -z "$TARGET" ]; then
    echo "用法：ACME_EMAIL=you@example.com bash scripts/issue-cert.sh <網域或IP> [--staging]" >&2
    exit 1
fi
if [ -z "${ACME_EMAIL:-}" ]; then
    echo "❌ 請設定 ACME_EMAIL。那個位址會註冊在 Let's Encrypt 的 ACME 帳號上，" >&2
    echo "   所以由你決定要用哪一個，腳本不預設。" >&2
    echo "   例：ACME_EMAIL=you@example.com bash $0 $TARGET" >&2
    exit 1
fi

CERT_DIR="$PWD/deploy/certs"
ACME_DIR="$PWD/deploy/acme-challenge"
LEGO_DIR="$PWD/deploy/lego"
mkdir -p "$CERT_DIR" "$ACME_DIR" "$LEGO_DIR"

SERVER="https://acme-v02.api.letsencrypt.org/directory"
[ "$STAGING" = "1" ] && SERVER="https://acme-staging-v02.api.letsencrypt.org/directory"

if printf '%s' "$TARGET" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    # IP 只有 shortlived 這個 profile 收，其餘 profile 的 Identifier Types 只有 DNS。
    PROFILE=(--profile shortlived)
    echo "→ 目標是 IP，使用 shortlived profile（效期約 6.7 天）"
else
    PROFILE=()
    echo "→ 目標是網域，使用預設 profile（效期 90 天）"
fi
[ "$STAGING" = "1" ] && echo "→ staging 測試環境：拿到的憑證瀏覽器不信任，只用來驗流程"

# ---- 前置檢查 ----
if ! docker compose -f deploy/docker-compose.yml ps --format '{{.Service}} {{.Status}}' 2>/dev/null \
     | grep -q '^frontend .*Up'; then
    echo "❌ frontend 容器沒有在跑。先 make full 或 make local。" >&2
    exit 1
fi

# 探測檔要放在 <webroot>/.well-known/acme-challenge/ 底下，不是 webroot 根目錄——
# nginx 是 root + 完整 URI，放錯位置會 404 而誤判成「nginx 設定壞了」。
PROBE="selftest-$RANDOM"
PROBE_DIR="$ACME_DIR/.well-known/acme-challenge"
mkdir -p "$PROBE_DIR"
echo "$PROBE" > "$PROBE_DIR/$PROBE"
if ! curl -fsS -m 10 "http://127.0.0.1/.well-known/acme-challenge/$PROBE" 2>/dev/null | grep -q "$PROBE"; then
    rm -f "$PROBE_DIR/$PROBE"
    echo "❌ 本機讀不到 /.well-known/acme-challenge/ ——" >&2
    echo "   nginx 設定或 volume 掛載有問題，這樣驗證一定過不了。" >&2
    exit 1
fi
rm -f "$PROBE_DIR/$PROBE"
echo "✅ ACME 挑戰路徑本機可讀"
echo "⚠️  接下來 ACME 伺服器會從網際網路連 http://$TARGET/，port 80 必須對外開放。"

# ---- 簽發 ----
# lego 5.4.1 的旗標全部掛在 run 子命令上，不是全域的（放前面會說 flag not defined）。
docker run --rm \
    -v "$LEGO_DIR:/data" -v "$ACME_DIR:/webroot" \
    goacme/lego run \
    --server "$SERVER" \
    --path /data --email "$ACME_EMAIL" \
    --http --http.webroot /webroot \
    -d "$TARGET" --accept-tos "${PROFILE[@]}"

# ---- 複製給 nginx ----
# lego 的輸出是容器裡的 root 建的，宿主機讀不到，所以在容器裡複製並改權限。
docker run --rm -v "$LEGO_DIR:/data" -v "$CERT_DIR:/out" alpine sh -c "
    cp /data/certificates/$TARGET.crt /out/fullchain.pem &&
    cp /data/certificates/$TARGET.key /out/privkey.pem &&
    chown $(id -u):$(id -g) /out/fullchain.pem /out/privkey.pem &&
    chmod 644 /out/fullchain.pem && chmod 600 /out/privkey.pem"

echo
echo "✅ 憑證已放到 deploy/certs/"
openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -issuer -dates -ext subjectAltName 2>/dev/null | sed 's/^/   /'
echo
echo "重啟前端讓它生效："
echo "    docker compose -f deploy/docker-compose.yml --env-file .env.local up -d --force-recreate frontend"
echo
echo "設定自動續期（IP 憑證只有 6.7 天，一定要排）："
echo "    crontab -e"
echo "    0 */6 * * * cd $PWD && ACME_EMAIL=$ACME_EMAIL bash scripts/renew-cert.sh >> /tmp/cert-renew.log 2>&1"
