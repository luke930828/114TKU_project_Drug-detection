#!/usr/bin/env bash
# 關掉 WSL 的崩潰傾印，並讓它在每次開機時自動生效。
#
# 為什麼需要這支
# ──────────────
# WSL 的 /proc/sys/kernel/core_pattern 預設是 |/wsl-capture-crash。
# core_pattern 導向管線時，核心不會套用 RLIMIT_CORE 的大小上限，
# 崩潰的行程會把整個位址空間原封不動寫出來，沒有任何煞車。
#
#   2026-08-29  191.7 GB  → Docker Desktop 崩潰
#   2026-08-31  172 GB    → C 槽從 580 GB 掉到 366 GB
#   2026-09-02  736 GB    → 單一檔案 244 GB，C 槽 100% 滿，Docker 停擺
#
# 三次都是容器裡 Playwright 的 Chromium 崩潰。崩潰本身不是災難，
# 沒有上限的傾印檔才是。
#
# compose 已經有 ulimits.core: 0，但 2026-09-02 那次還是產生了傾印檔，
# 表示容器層級的限制擋不住（Chromium 的子行程沒有繼承到）。
# 這支從核心層關掉，不管哪個容器、哪個 distro 都涵蓋。
#
# ⚠️ WSL2 所有 distro 共用同一個核心，kernel.core_pattern 也不是
#    per-namespace 的，所以在這個 distro 設定會全域生效，
#    包含 Docker Desktop 用的 docker-desktop distro。
#
# 用 /etc/sysctl.d 而不是 wsl.conf 的 [boot] command：
# 這台機器的 /etc/wsl.conf 已經有 systemd=true，而啟用 systemd 之後
# [boot] command 不保證會被執行。systemd-sysctl 才是對的掛載點。
#
# 用法：
#     sudo bash scripts/disable-wsl-coredumps.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "需要 root：sudo bash $0" >&2
    exit 1
fi

CONF=/etc/sysctl.d/99-disable-coredump.conf

echo "改之前：core_pattern = $(cat /proc/sys/kernel/core_pattern)"

cat > "$CONF" <<'EOF'
# 關掉崩潰傾印。
# 預設的 |/wsl-capture-crash 是管線，核心不會套用 RLIMIT_CORE 的大小上限，
# Chromium 崩一次就能寫出數百 GB（2026-09-02 那次單一檔案 244 GB，
# 把 C 槽塞到 100% 並讓 Docker 停擺）。
# 改成寫檔案之後 RLIMIT_CORE 會生效，而預設的 ulimit -c 是 0，等於不產生。
kernel.core_pattern=core
EOF
echo "已寫入 $CONF"

# 立即生效
sysctl -p "$CONF" >/dev/null
echo "改之後：core_pattern = $(cat /proc/sys/kernel/core_pattern)"

# systemd 會在開機時套用 /etc/sysctl.d/*.conf
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable systemd-sysctl.service >/dev/null 2>&1 || true
    if systemctl is-enabled systemd-sysctl.service >/dev/null 2>&1; then
        echo "systemd-sysctl 已啟用，開機會自動套用。"
    else
        echo "⚠️ 查不到 systemd-sysctl 的狀態，重開機後請再確認一次。"
    fi
fi

echo
echo "驗證："
echo "  core_pattern = $(cat /proc/sys/kernel/core_pattern)   （應為 core）"
echo "  ulimit -c    = $(ulimit -c)                            （應為 0）"
echo
echo "兩個都對的話，Chromium 再崩也不會產生傾印檔。"
echo "重開機後可以用這行複查："
echo "  cat /proc/sys/kernel/core_pattern"
