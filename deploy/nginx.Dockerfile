# syntax=docker/dockerfile:1

########################################
# Frontend build stage
########################################
# 使用 debian-slim 避免 rollup 可选二进制在 musl 下缺失
FROM node:20-slim AS frontend-builder
# 构建需要 devDependencies（vite 等）
ENV NODE_ENV=development
WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
RUN npm install @rollup/rollup-linux-x64-gnu --no-save

COPY frontend/ ./
RUN npm run build

########################################
# Nginx runtime with built frontend
########################################
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# 复制构建产物
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# 默认挂载的静态/媒体目录（若宿主挂载会覆盖）
RUN mkdir -p /usr/share/nginx/html/static /usr/share/nginx/html/media

# Nginx 配置（可在 docker-compose 中通过卷覆盖）
COPY deploy/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
