# ============================================================
# frontend 模組範本 —— 之後把 frontend/ 的內容搬進 modules/frontend/ 時再填
#
# 這裡先用 nginx 內建的預設設定檔。要讓前端打自己的 /api/... 讓後端
# proxy（順便解決 CORS），記得補一份 nginx.conf 進來，
# 用 COPY nginx.conf /etc/nginx/conf.d/default.conf 蓋掉，範例可以參考
# README-docker.md。
# ============================================================

# ---------- build 階段 ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Vite 的環境變數是「build 時」注入、烤進靜態檔的，不是執行時讀的。
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---------- 執行階段 ----------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
