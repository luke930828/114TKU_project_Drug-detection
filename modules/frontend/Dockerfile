# ---------- build 階段 ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY app/package.json app/package-lock.json* ./
RUN npm install

COPY app/ .

# Vite 的環境變數是「build 時」注入、烤進靜態檔的，不是執行時讀的。
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---------- 執行階段 ----------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
