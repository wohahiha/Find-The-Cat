# syntax=docker/dockerfile:1

# =========================
# Builder：安装依赖
# =========================
FROM python:3.11-slim-bookworm AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .

# 为 Postgres/MySQL 驱动准备编译链与头文件，安装依赖后清理
RUN set -eux \
 && for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/debian.sources; do \
      if [ -f "$f" ]; then sed -i 's|http://deb.debian.org|https://deb.debian.org|g' "$f"; fi; \
    done \
 && apt-get update -o Acquire::Retries=5 -o Acquire::http::Timeout=30 \
 && apt-get install -y --no-install-recommends build-essential libpq-dev default-libmysqlclient-dev \
 && pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt \
 && apt-get purge -y build-essential libpq-dev default-libmysqlclient-dev \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# =========================
# Runtime：仅拷贝依赖与代码
# =========================
FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=Config.settings
WORKDIR /app

# 依赖
COPY --from=builder /install /usr/local
# 代码
COPY . /app

RUN mkdir -p /data/db /data/media /app/static

# 入口脚本（负责 migrate/collectstatic）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
# 默认 ASGI（支持 WebSocket/异步）；若需 WSGI 可运行时覆盖为 gunicorn Config.wsgi:application
CMD ["uvicorn", "Config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
