# ============================================================
# 四種情境 = 四個指令
#
# Windows 沒有 make 的話，直接看每個目標底下那行指令複製來用就好，
# 或裝 Git Bash / WSL。
# ============================================================

COMPOSE      := docker compose -f deploy/docker-compose.yml
DEV_OVERRIDE := -f deploy/docker-compose.dev.yml

.DEFAULT_GOAL := help
.PHONY: help dev local full demo tailscale logs ps stop clean rebuild check

help: ## 顯示這份說明
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---------- 情境一：寫程式 ----------
dev: ## 開發模式：程式碼掛載 + 熱重載，存檔就生效
	$(COMPOSE) $(DEV_OVERRIDE) --env-file .env.local up -d
	@echo ""
	@echo "  後端 API  → http://localhost:8000/docs"
	@echo "  前端畫面  → http://localhost:5173"
	@echo "  資料庫    → localhost:3306"
	@echo ""
	@echo "  改 .py 或 .tsx 存檔就會自動重載，不用重跑這個指令。"

# ---------- 情境二：單機整合 ----------
local: ## 單機：後端 + DB + 前端（爬蟲/YOLO/NLP 還沒好時用這個）
	$(COMPOSE) --env-file .env.local up -d --build

full: ## 單機：全部六個服務一起跑
	$(COMPOSE) --env-file .env.local --profile full up -d --build

# ---------- 情境三：跨機測試 ----------
tailscale: ## 跨機：只跑本機負責的模組，位址指向 tailnet
	$(COMPOSE) --env-file .env.tailscale up -d --build
	@echo ""
	@echo "  本機 tailnet 位址："
	@tailscale ip -4 2>/dev/null || echo "  （tailscale 指令找不到，確認有裝且已登入）"

# ---------- 情境四：展示 ----------
demo: ## 展示日：前一天先跑這個預熱，現場才不用等下載
	$(COMPOSE) --env-file .env.local --profile full pull
	$(COMPOSE) --env-file .env.local --profile full build
	@echo ""
	@echo "  image 都在本機了。展示現場執行 make full 即可，"
	@echo "     就算沒網路也能起來。"

# ---------- 日常 ----------
logs: ## 追蹤所有服務的即時紀錄
	$(COMPOSE) logs -f --tail=100

ps: ## 看每個服務的健康狀態
	$(COMPOSE) ps

stop: ## 停止（資料保留）
	$(COMPOSE) --profile full down

rebuild: ## 只重建某個模組：make rebuild M=backend
	@test -n "$(M)" || (echo "用法：make rebuild M=backend" && exit 1)
	$(COMPOSE) --env-file .env.local build --no-cache $(M)
	$(COMPOSE) --env-file .env.local up -d $(M)

clean: ## ⚠️ 停止並刪掉資料庫資料，整個重來
	@echo "這會刪掉資料庫裡所有資料。"
	@read -p "確定嗎？打 yes 繼續：" ans && [ "$$ans" = "yes" ]
	$(COMPOSE) --profile full down -v

check: ## 部署前檢查：確認沒有把秘密或大檔加進 git
	@echo "→ 檢查有沒有密碼進 git..."
	@! git ls-files | grep -iE '密碼|password|secret|\.env$$' \
		|| (echo "  ❌ 上面這些檔案不該進 git！" && exit 1)
	@echo "  ✅ 沒有"
	@echo "→ 檢查有沒有大檔..."
	@! git ls-files | xargs -I{} sh -c 'test -f "{}" && find "{}" -size +5M' 2>/dev/null | grep . \
		|| (echo "  ⚠️  上面這些檔案超過 5MB，考慮改用 Release assets" )
	@echo "→ 檢查有沒有寫死的 IP..."
	@! grep -rn '100\.[0-9]\+\.[0-9]\+\.[0-9]\+' modules/ --include='*.py' --include='*.ts' --include='*.tsx' \
		|| (echo "  ❌ 還有寫死的 tailnet IP，應該改用 config.py" && exit 1)
	@echo "  ✅ 沒有"

smoke: ## 整合冒煙測試：驗證模組間的介面契約
	python3 scripts/smoke_test.py --base-url http://localhost:8000

up-staged: ## 分階段起：一次加一個模組，壞了才知道是誰
	$(COMPOSE) --env-file .env.local up -d mysql
	@echo "→ 等 MySQL healthy..." && sleep 5
	$(COMPOSE) --env-file .env.local up -d backend
	@echo "→ 後端起來了，先驗一次" && sleep 5 && python3 scripts/smoke_test.py || true
	$(COMPOSE) --env-file .env.local --profile full up -d nlp
	$(COMPOSE) --env-file .env.local --profile full up -d yolo
	$(COMPOSE) --env-file .env.local --profile full up -d crawler
	$(COMPOSE) --env-file .env.local up -d frontend
	@$(COMPOSE) ps

models: ## 下載模型權重（照 models/MODELS.txt 的清單）
	./scripts/download_models.sh
