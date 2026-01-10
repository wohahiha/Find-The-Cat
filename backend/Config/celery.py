from __future__ import annotations

import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Config.settings")

# 创建 Celery 应用，使用 Django 配置中的 CELERY_* 变量
app = Celery("Config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# 统一时区，与 Django 设置保持一致
if getattr(settings, "TIME_ZONE", None):
    app.conf.timezone = settings.TIME_ZONE

# Celery Beat 额外调度（settings 中也已声明，便于代码级注入）
cleanup_interval = getattr(settings, "MACHINE_CLEAN_INTERVAL_SECONDS", 300)
app.conf.beat_schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
# 若外部未设置，则动态注入默认的靶机清理任务
if "cleanup-expired-machines" not in app.conf.beat_schedule:
    app.conf.beat_schedule["cleanup-expired-machines"] = {
        "task": "apps.machines.tasks.cleanup_expired_machines",
        "schedule": cleanup_interval,
    }
