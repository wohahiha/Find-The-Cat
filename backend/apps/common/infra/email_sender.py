# apps/common/infra/email_sender.py

from __future__ import annotations

from typing import Iterable
from email.mime.image import MIMEImage
from email.utils import formataddr
from smtplib import SMTPRecipientsRefused, SMTPDataError

from django.core.mail import EmailMultiAlternatives, get_connection, send_mail
from django.conf import settings

# MailAccount 已迁移至系统模块
from apps.system.models import MailAccount
from apps.system.services import ConfigService
from apps.common.exceptions import EmailSendError, ValidationError
from apps.common.infra.logger import get_logger

config_service = ConfigService()
logger = get_logger(__name__)


def _build_sender(name: str | None, username: str | None) -> tuple[str, str]:
    """
    构造发信人：
    - envelope_from：SMTP MAIL FROM，固定使用用户名邮箱
    - header_from：邮件头展示，附带名称（如有）
    """
    from_email = username or getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
    header_from = formataddr((name or "", from_email)) if name else from_email
    return from_email, header_from


def send_mail_with_account(
        *,
        account: MailAccount,
        subject: str,
        body: str,
        html_body: str | None = None,
        inline_images: Iterable[dict[str, object]] | None = None,
        to: Iterable[str],
) -> None:
    """
    使用指定 MailAccount 发送邮件
    - 业务场景：验证码/通知邮件，优先走配置的发信账号
    - 参数 account：发信账号；subject/body：邮件主题/正文；to：收件人列表
    """
    try:
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
        envelope_from, header_from = _build_sender(account.from_name, account.username)
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=envelope_from,
            to=list(to),
            connection=connection,
            headers={"From": header_from},
        )
        if html_body:
            email.attach_alternative(html_body, "text/html")
        # 内联图片（如 Logo）：防止外链加载失败
        if inline_images:
            for image in inline_images:
                cid = image.get("cid")
                content = image.get("content")
                mime_type = image.get("mimetype") or "image/png"
                if not cid or not content:
                    continue
                subtype = mime_type.split("/", 1)[1] if "/" in mime_type else None
                try:
                    img = MIMEImage(content, _subtype=subtype) if subtype else MIMEImage(content)
                    img.add_header("Content-ID", f"<{cid}>")
                    img.add_header("Content-Disposition", "inline")
                    email.attach(img)
                except Exception:
                    # 图片解析失败不阻塞发送，写日志便于排查
                    logger.warning("内联图片附加失败", extra={"cid": cid, "mime_type": mime_type})
        email.send(fail_silently=not settings.DEBUG)
    except (SMTPRecipientsRefused, SMTPDataError) as exc:
        # 收件人无效：明确提示邮箱不存在/不可达
        logger.warning(
            "收件邮箱被拒收",
            extra={
                "recipients": list(to),
                "account_id": getattr(account, "id", None),
                "smtp_code": getattr(exc, "smtp_code", None) or getattr(exc, "smtp_error", None),
            },
        )
        raise ValidationError(message="收件邮箱无效或不存在") from exc
    except Exception as exc:
        logger.exception("使用指定 MailAccount 发送邮件失败", extra={"account_id": getattr(account, "id", None)})
        raise EmailSendError() from exc


def send_mail_with_settings(
        *,
        subject: str,
        body: str,
        to: Iterable[str],
        html_body: str | None = None,
        inline_images: Iterable[dict[str, object]] | None = None,
) -> None:
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
    envelope_from, header_from = _build_sender(None, username)

    try:
        # 配置不完整时提示管理员配置（生产关闭 DEBUG 时强制报错；DEBUG 下允许 console 兜底）
        if not host or not username:
            if not settings.DEBUG:
                raise ValidationError(message="邮件服务未配置，请联系管理员在后台填充 SMTP 或发信账号后重试")
            logger.warning("邮件服务未配置，DEBUG 下回退 console 后端", extra={"host": host, "user": username})
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=envelope_from,
                to=list(to),
                headers={"From": header_from},
            )
            if html_body:
                email.attach_alternative(html_body, "text/html")
            if inline_images:
                for image in inline_images:
                    cid = image.get("cid")
                    content = image.get("content")
                    mime_type = image.get("mimetype") or "image/png"
                    if not cid or not content:
                        continue
                    subtype = mime_type.split("/", 1)[1] if "/" in mime_type else None
                    try:
                        img = MIMEImage(content, _subtype=subtype) if subtype else MIMEImage(content)
                        img.add_header("Content-ID", f"<{cid}>")
                        img.add_header("Content-Disposition", "inline")
                        email.attach(img)
                    except Exception:
                        logger.warning("内联图片附加失败", extra={"cid": cid, "mime_type": mime_type, "using_settings": True})
            email.send(fail_silently=not settings.DEBUG)
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
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=envelope_from,
            to=list(to),
            connection=connection,
            headers={"From": header_from},
        )
        if html_body:
            email.attach_alternative(html_body, "text/html")
        if inline_images:
            for image in inline_images:
                cid = image.get("cid")
                content = image.get("content")
                mime_type = image.get("mimetype") or "image/png"
                if not cid or not content:
                    continue
                subtype = mime_type.split("/", 1)[1] if "/" in mime_type else None
                try:
                    img = MIMEImage(content, _subtype=subtype) if subtype else MIMEImage(content)
                    img.add_header("Content-ID", f"<{cid}>")
                    img.add_header("Content-Disposition", "inline")
                    email.attach(img)
                except Exception:
                    logger.warning("内联图片附加失败", extra={"cid": cid, "mime_type": mime_type, "using_settings": True})
        email.send(fail_silently=not settings.DEBUG)
    except (SMTPRecipientsRefused, SMTPDataError) as exc:
        logger.warning(
            "收件邮箱被拒收",
            extra={
                "recipients": list(to),
                "using_settings": True,
                "smtp_code": getattr(exc, "smtp_code", None) or getattr(exc, "smtp_error", None),
            },
        )
        raise ValidationError(message="收件邮箱无效或不存在") from exc
    except Exception as exc:
        logger.exception("使用系统配置发送邮件失败")
        raise EmailSendError() from exc
