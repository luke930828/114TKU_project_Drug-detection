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
# 關於 IP 憑證：目前不行
# ──────────────────────
# Let's Encrypt 的 ACME 目錄裡確實有 shortlived profile（就是 IP 憑證用的），
# 但 2026-09-03 實測 certbot 直接拒絕：
#
#     Requested name 163.13.202.107 is an IP address.
#     The Let's Encrypt certificate authority will not issue certificates
#     for a bare IP address.
#
# 「目錄裡有那個 profile」不等於「簽得到」。要 HTTPS 就得先有網域名稱：
#   1. 跟學校資訊處申請 tku.edu.tw 的子網域（最正式，但要跑行政流程）
#   2. 免費 DDNS（DuckDNS / No-IP）指到校園 IP，十分鐘可完成
# 兩種都是 90 天效期，比 6 天的 IP 憑證好管理得多。
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
# IP 就直接擋掉，不要讓人跑完前置檢查、拉完 certbot image 才發現要不到。
if printf '%s' "$TARGET" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    cat >&2 <<'IPMSG'
❌ Let's Encrypt 不簽 IP 位址的憑證（2026-09-03 實測 certbot 的回應）：

     "The Let's Encrypt certificate authority will not issue certificates
      for a bare IP address."

   ACME 目錄裡雖然列了 shortlived profile，但實際上要不到。

   先取得一個網域名稱，兩條路：
     1. 跟學校資訊處申請 tku.edu.tw 的子網域，指向這台機器的 IP
     2. 免費 DDNS（例如 DuckDNS）指到 163.13.202.107，十分鐘可完成

   拿到之後：bash scripts/issue-cert.sh your-name.duckdns.org
IPMSG
    exit 1
fi
IS_IP=0
echo "→ 目標是網域，使用一般 profile（效期 90 天）"

# ---- 前置檢查：frontend 有沒有在跑、port 80 通不通 ----
if ! docker compose -f deploy/docker-compose.yml ps --format '{{.Service}} {{.Status}}' 2>/dev/null \
     | grep -q '^frontend .*Up'; then
    echo "❌ frontend 容器沒有在跑。先 make full 或 make local。" >&2
    exit 1
fi

# 自我檢查：從本機打一次，確認 nginx 真的會從 /var/www/certbot 提供這個路徑。
# 這一步失敗的話，Let's Encrypt 那邊也一定失敗，先在這裡擋下來比較好查。
#
# ⚠️ 探測檔要放在 <webroot>/.well-known/acme-challenge/ 底下，不是 webroot 根目錄。
#    nginx 是 root + 完整 URI，certbot 也是建在這個子路徑，
#    放錯位置的話自我檢查會 404 而誤判成「設定壞了」。
PROBE="acme-selftest-$RANDOM"
PROBE_DIR="$ACME_DIR/.well-known/acme-challenge"
mkdir -p "$PROBE_DIR"
echo "$PROBE" > "$PROBE_DIR/$PROBE"
if ! curl -fsS -m 10 "http://127.0.0.1/.well-known/acme-challenge/$PROBE" 2>/dev/null | grep -q "$PROBE"; then
    rm -f "$PROBE_DIR/$PROBE"
    echo "❌ 本機讀不到 /.well-known/acme-challenge/ ——" >&2
    echo "   frontend 的 nginx 設定或 volume 掛載有問題，這樣驗證一定過不了。" >&2
    exit 1
fi
rm -f "$PROBE_DIR/$PROBE"
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
echo
echo "設定自動續期（90 天效期，但 certbot 建議每天檢查）："
echo "    crontab -e"
echo "    0 6 * * * cd $PWD && bash scripts/renew-cert.sh >> /tmp/cert-renew.log 2>&1"
