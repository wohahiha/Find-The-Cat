#!/bin/sh
set -e

# 默认使用 Config.settings
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-Config.settings}

# 迁移与静态收集
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 启动应用（默认 uvicorn ASGI，若需要 WSGI 可覆盖 CMD）
exec "$@"
