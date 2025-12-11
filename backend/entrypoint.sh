#!/bin/sh
set -e

# 默认使用 Config.settings
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-Config.settings}

# 生成并持久化 SECRET_KEY/FLAG_SECRET（优先环境变量，其次持久化文件）
ensure_secrets() {
  secret_dir="${SECRET_STORAGE_DIR:-/data/secrets}"
  secret_file="$secret_dir/secrets.env"
  mkdir -p "$secret_dir"

  # 先加载已有文件（仅在环境变量未显式提供时）
  if [ -f "$secret_file" ]; then
    if [ -z "${SECRET_KEY:-}" ] || [ -z "${FLAG_SECRET:-}" ]; then
      set -a
      . "$secret_file"
      set +a
    fi
  fi

  # 如仍缺失则生成并写入文件，后续重启可复用
  if [ -z "${SECRET_KEY:-}" ] || [ -z "${FLAG_SECRET:-}" ]; then
    SECRET_KEY_VALUE="${SECRET_KEY:-$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)}"
    FLAG_SECRET_VALUE="${FLAG_SECRET:-$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)}"
    cat > "$secret_file" <<EOF
SECRET_KEY=${SECRET_KEY_VALUE}
FLAG_SECRET=${FLAG_SECRET_VALUE}
EOF
    chmod 600 "$secret_file" || true
    export SECRET_KEY="$SECRET_KEY_VALUE"
    export FLAG_SECRET="$FLAG_SECRET_VALUE"
    echo "Generated SECRET_KEY/FLAG_SECRET and saved to $secret_file"
  fi
}

ensure_secrets

RUN_MIGRATIONS=$(echo "${RUN_MIGRATIONS:-true}" | tr '[:upper:]' '[:lower:]')
RUN_COLLECTSTATIC=$(echo "${RUN_COLLECTSTATIC:-true}" | tr '[:upper:]' '[:lower:]')

# 迁移与静态收集（可通过环境变量跳过）
if [ "$RUN_MIGRATIONS" = "true" ]; then
  python manage.py migrate --noinput
else
  echo "Skip migrations (RUN_MIGRATIONS=${RUN_MIGRATIONS})"
fi

if [ "$RUN_COLLECTSTATIC" = "true" ]; then
  python manage.py collectstatic --noinput
else
  echo "Skip collectstatic (RUN_COLLECTSTATIC=${RUN_COLLECTSTATIC})"
fi

# 启动应用（默认 uvicorn ASGI，若需要 WSGI 可覆盖 CMD）
exec "$@"
