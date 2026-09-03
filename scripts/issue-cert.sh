#!/usr/bin/env bash
# 用 Let's Encrypt 簽發憑證。網域與 IP 位址都支援。
#
#     bash scripts/issue-cert.sh drugdetect.tku.edu.tw      # 網域
#     bash scripts/issue-cert.sh 163.13.202.107             # IP
#     bash scripts/issue-cert.sh 163.13.202.107 --staging   # 先用測試環境試
#
# 前提（沒滿足的話一定失敗，腳本會先檢查）：
#   1. port 80 從網際網路連得到——Let's Encrypt 的伺服器要主動連進來驗證
#   2. frontend 容器正在跑（ACME 的挑戰檔由它從 /var/www/certbot 提供）
#
# 關於 IP 憑證
# ────────────
# Let's Encrypt 從 2025 年開始支援 IP 位址憑證，用的是 shortlived profile。
# 但那是 **6 天** 效期，不是 90 天。也就是說：
#   * 續期必須自動化，而且至少每 2~3 天跑一次
#   * 機器關機超過 6 天，憑證就過期了
# 對筆電型的部署這很麻煩。如果學校能給子網域，優先用網域（90 天，好管理）。
#
# 憑證會放到 deploy/certs/{fullchain,privkey}.pem，重啟 frontend 就會啟用。
set -euo pipefail

cd "$(dirname "$0")/.."
TARGET="${1:-}"
shift || true
EXTRA=("$@")

if [ -z "$TARGET" ]; then
    echo "用法：bash scripts/issue-cert.sh <網域或IP> [--staging]" >&2
    exit 1
fi

CERT_DIR="$PWD/deploy/certs"
ACME_DIR="$PWD/deploy/acme-challenge"
LE_DIR="$PWD/deploy/letsencrypt"
mkdir -p "$CERT_DIR" "$ACME_DIR" "$LE_DIR"

# IP 或網域？IP 要指定 shortlived profile，網域不用。
if printf '%s' "$TARGET" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    IS_IP=1
    echo "→ 目標是 IP 位址，使用 shortlived profile（效期 6 天）"
    EXTRA+=(--preferred-profile shortlived)
else
    IS_IP=0
    echo "→ 目標是網域，使用一般 profile（效期 90 天）"
fi

# ---- 前置檢查：frontend 有沒有在跑、port 80 通不通 ----
if ! docker compose -f deploy/docker-compose.yml ps --format '{{.Service}} {{.Status}}' 2>/dev/null \
     | grep -q '^frontend .*Up'; then
    echo "❌ frontend 容器沒有在跑。先 make full 或 make local。" >&2
    exit 1
fi

PROBE="acme-selftest-$RANDOM"
echo "$PROBE" > "$ACME_DIR/$PROBE"
# 自我檢查：從本機打一次，確認 nginx 真的會從 /var/www/certbot 提供這個路徑。
# 這一步失敗的話，Let's Encrypt 那邊也一定失敗，先在這裡擋下來比較好查。
if ! curl -fsS -m 10 "http://127.0.0.1/.well-known/acme-challenge/$PROBE" 2>/dev/null | grep -q "$PROBE"; then
    rm -f "$ACME_DIR/$PROBE"
    echo "❌ 本機讀不到 /.well-known/acme-challenge/ ——" >&2
    echo "   frontend 的 nginx 設定或 volume 掛載有問題，這樣驗證一定過不了。" >&2
    exit 1
fi
rm -f "$ACME_DIR/$PROBE"
echo "✅ ACME 挑戰路徑本機可讀"
echo "⚠️  接下來 Let's Encrypt 會從網際網路連 http://$TARGET/ ——"
echo "   那個位址的 port 80 必須從校外連得到，否則會失敗。"

# ---- 簽發 ----
# webroot 模式：certbot 把挑戰檔寫進共用目錄，nginx 負責提供。
# 這樣不用停掉 nginx（standalone 模式要佔用 port 80）。
docker run --rm \
    -v "$LE_DIR:/etc/letsencrypt" \
    -v "$ACME_DIR:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot -w /var/www/certbot \
    -d "$TARGET" \
    --agree-tos --register-unsafely-without-email \
    --non-interactive --keep-until-expiring \
    "${EXTRA[@]}"

# ---- 複製到 nginx 讀得到的地方 ----
# certbot 產出的是 symlink（live/ 指向 archive/），直接掛給 nginx 的話
# 容器裡會是斷掉的連結，所以複製實體檔案。
LIVE="$LE_DIR/live/$TARGET"
if [ ! -f "$LIVE/fullchain.pem" ]; then
    echo "❌ 簽發後找不到 $LIVE/fullchain.pem" >&2
    exit 1
fi
cp -L "$LIVE/fullchain.pem" "$CERT_DIR/fullchain.pem"
cp -L "$LIVE/privkey.pem"   "$CERT_DIR/privkey.pem"
chmod 600 "$CERT_DIR/privkey.pem"

echo
echo "✅ 憑證已放到 deploy/certs/"
openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -subject -dates 2>/dev/null || true
echo
echo "重啟前端讓它生效："
echo "    docker compose -f deploy/docker-compose.yml --env-file .env.local up -d frontend"
if [ "$IS_IP" = "1" ]; then
    echo
    echo "⚠️  IP 憑證只有 6 天效期。設定自動續期："
    echo "    scripts/renew-cert.sh 加進 cron 或工作排程器，每天跑一次。"
fi
