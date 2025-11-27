# apps/common/infra/email_sender.py

from __future__ import annotations

from typing import Iterable

from django.core.mail import EmailMessage, get_connection, send_mail
from django.conf import settings

from apps.accounts.models import MailAccount
from apps.system.services import ConfigService

config_service = ConfigService()


def send_mail_with_account(
        *,
        account: MailAccount,
        subject: str,
        body: str,
        to: Iterable[str],
) -> None:
    """
    使用指定 MailAccount 发送邮件
    - 业务场景：验证码/通知邮件，优先走配置的发信账号
    - 参数 account：发信账号；subject/body：邮件主题/正文；to：收件人列表
    """
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=account.host,
        port=account.port,
        username=account.username,
        password=account.password,
        use_tls=account.use_tls,
        use_ssl=account.use_ssl,
        timeout=30,
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=account.from_display,
        to=list(to),
        connection=connection,
    )
    email.send(fail_silently=not settings.DEBUG)


def send_mail_with_settings(*, subject: str, body: str, to: Iterable[str]) -> None:
    """
    回退到 settings 中配置的邮件账号
    - 业务场景：未指定 MailAccount 或默认账号缺失时的兜底发送
    - 读取顺序：后台 SystemConfig > settings/.env > 代码默认
    """
    host = config_service.get("EMAIL_HOST")
    port = config_service.get("EMAIL_PORT")
    username = config_service.get("EMAIL_HOST_USER")
    password = config_service.get("EMAIL_HOST_PASSWORD")
    use_tls = bool(config_service.get("EMAIL_USE_TLS", False))
    use_ssl = bool(config_service.get("EMAIL_USE_SSL", False))
    from_email = (
            config_service.get("DEFAULT_FROM_EMAIL")
            or username
            or getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or getattr(settings, "EMAIL_HOST_USER", None)
    )

    # 配置不完整时回退到 Django 默认邮件发送
    if not host or not username:
        send_mail(
            subject,
            body,
            from_email,
            list(to),
            fail_silently=not settings.DEBUG,
        )
        return

    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=host,
        port=port or 587,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        timeout=30,
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=list(to),
        connection=connection,
    )
    email.send(fail_silently=not settings.DEBUG)
