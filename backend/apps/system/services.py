from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.conf import settings

from apps.common.base.base_service import BaseService
from apps.common.infra.logger import get_logger
from .repo import SystemConfigRepo
from .models import SystemConfig

logger = get_logger(__name__)


class ConfigService(BaseService[SystemConfig]):
    """
    系统配置服务：动态配置管理

    核心功能：
    1. 配置优先级：后台配置 > settings.py 默认值 > 传入默认值
    2. 自动初始化：Django 启动时自动将 settings.py 的值填入数据库
    3. 缓存机制：Redis 缓存（5分钟），不可用时自动降级
    4. 配置变更：后台修改后调用 invalidate() 清理缓存

    配置分类：
    - 启动必需配置（SECRET_KEY、数据库、Redis等）：修改后需重启服务
    - 运行时配置（日志级别、Docker参数等）：部分修改后立即生效

    注意：
    - 不再使用 .env 文件，所有默认值在 settings.py 中硬编码
    - 首次启动后，管理员应在后台修改敏感配置（SECRET_KEY、密码等）
    """

    cache_prefix = "system_config:"
    cache_timeout = 300  # 缓存 5 分钟

    # 支持后台覆盖的配置清单：key -> 类型/描述/敏感/必填
    # 注：首次启动时会自动从 settings.py 读取默认值填入数据库
    SUPPORTED_CONFIGS = {
        # 安全/调试
        "SECRET_KEY": {
            "type": SystemConfig.ValueType.SECRET,
            "desc": "Django SECRET_KEY",
            "detail": "用于签名和加密，会影响 JWT、CSRF 等安全组件的安全性。必须保持机密且不可为空，泄露会导致 Token 与会话失效被伪造。首次启动时会自动填入 settings.py 的默认值（不安全），生产环境必须在后台修改为长度 50+ 的高熵随机字符串。修改后需重启服务生效。",
            "sensitive": True,
            "required": True,
        },
        "FLAG_SECRET": {
            "type": SystemConfig.ValueType.SECRET,
            "desc": "动态 Flag HMAC 密钥",
            "detail": "用于为动态 Flag 生成 HMAC，必须为高熵随机字符串，避免复用 SECRET_KEY。泄露将导致所有动态 Flag 可被伪造，生产环境务必设置为 32+ 字符并保密。修改后需重启服务生效。",
            "sensitive": True,
            "required": True,
        },
        "DEBUG": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "DEBUG 开关（生产应为 False）",
            "detail": "控制 Django 是否开启调试模式，影响错误栈展示和静态资源加载方式。生产环境必须关闭以避免泄露敏感信息，开启只用于本地调试或首启在未配置证书时临时允许 HTTP 访问后台。完成配置后请改为 False 并重启。",
            "required": True,
        },
        "ALLOWED_HOSTS": {
            "type": SystemConfig.ValueType.JSON,
            "desc": "允许的主机列表",
            "detail": "限制可访问站点的域名或 IP，防止 Host 头攻击。填写 JSON 数组格式，如 [\"example.com\", \"127.0.0.1\"]。首次启动时默认为 [\"localhost\", ]（允许本地），生产环境必须在后台修改为实际域名/IP。修改后需重启服务生效。",
            "required": True,
        },
        "SITE_BRAND": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "站点品牌名称",
            "detail": "平台前台展示的站点品牌名，默认为 'Find The Cat'",
            "required": True,
        },
        "ALLOW_LOGIN_WITHOUT_CAPTCHA": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "允许登录跳过图形验证码（仅测试用）",
            "detail": "控制登录时是否强制校验图形验证码。仅在联调或自动化测试时可暂时置为 True，生产环境应保持 False（默认）。",
            "required": True,
        },
        "SECURE_SSL_REDIRECT": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "强制 HTTPS 跳转",
            "detail": "控制是否将所有 HTTP 请求 301 跳转至 HTTPS。生产环境启用；首启可关闭以便在未配置证书前访问后台，证书就绪后开启并重启。修改后需重启生效。",
            "required": True,
        },
        "SESSION_COOKIE_SECURE": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "Session Cookie 仅限 HTTPS",
            "detail": "开启后 Session Cookie 仅通过 HTTPS 传输，防止明文泄露。与 TLS 配置一致，证书就绪后应开启。修改后需重启生效。",
            "required": True,
        },
        "CSRF_COOKIE_SECURE": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "CSRF Cookie 仅限 HTTPS",
            "detail": "开启后 CSRF Cookie 仅通过 HTTPS 传输。需与实际部署协议一致；证书就绪后应开启。修改后需重启生效。",
            "required": True,
        },
        "CSRF_TRUSTED_ORIGINS": {
            "type": SystemConfig.ValueType.JSON,
            "desc": "CSRF 信任域名列表",
            "detail": "允许提交跨域表单的可信站点列表，使用 JSON 数组格式，例如 [\"https://ctf.example.com\" , \"https://admin.example.com\"]。配置错误会导致后台表单/接口 CSRF 校验失败。修改后需重启生效。",
            "required": False,
        },
        "CORS_ALLOWED_ORIGINS": {
            "type": SystemConfig.ValueType.JSON,
            "desc": "CORS 允许来源列表",
            "detail": "允许跨域请求的来源列表，JSON 数组格式，例如 [\"https://ctf.example.com\"]。为空则默认全开放（开发模式），生产建议显式配置域名。修改后需重启生效。",
            "required": False,
        },
        "MACHINE_PUBLIC_HOST": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "靶机访问主机名/IP",
            "detail": "前端展示靶机链接时使用的主机名或 IP，例如外网反向代理地址。为空则回退为 localhost。修改后需重启相关服务生效。",
            "required": False,
        },
        "WS_MAX_CONNECTIONS_PER_USER": {
            "type": SystemConfig.ValueType.INT,
            "desc": "单用户最大 WebSocket 连接数",
            "detail": "限制同一用户的并发 WebSocket 连接数量，防止滥用。默认 5，可根据并发与前端策略调整。修改后即可生效。",
            "required": True,
        },
        "WS_MAX_CONNECTIONS_PER_IP": {
            "type": SystemConfig.ValueType.INT,
            "desc": "单 IP 最大 WebSocket 连接数",
            "detail": "限制同一 IP 的并发 WebSocket 连接数量，防止滥用。默认 20，可按部署环境与安全要求调整。修改后即可生效。",
            "required": True,
        },
        "SCOREBOARD_PUSH_INTERVAL_SECONDS": {
            "type": SystemConfig.ValueType.INT,
            "desc": "记分板推送节流间隔（秒）",
            "detail": "高频榜单推送的节流时间，默认 3 秒；数值越大推送越少。用于减轻前端刷屏与通道压力。修改后即可生效。",
            "required": True,
        },
        "SCOREBOARD_PUSH_TOP": {
            "type": SystemConfig.ValueType.INT,
            "desc": "记分板推送条目数量",
            "detail": "scoreboard_snapshot 事件中返回的前 N 名条目数，默认 10。可根据前端展示需求调整，修改后即可生效。",
            "required": True,
        },
        # 数据库（sqlite 场景可为空的连接信息不标必填）
        "DB_ENGINE": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "数据库引擎（sqlite/mysql/postgres）",
            "detail": "指定 Django 使用的数据库后端类型，决定连接驱动与后续字段校验。可填写 sqlite、mysql、postgres 等小写值。首次启动时默认为 sqlite（本地开发），生产环境可改为 mysql 或 postgres。切换引擎后需同时填写 DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT，并重启服务生效。",
            "required": True,
        },
        "DB_NAME": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "数据库名称",
            "detail": "数据库名称或 sqlite 文件名，用于定位存储库。MySQL/PostgreSQL 填实际库名；sqlite 可填写 db.sqlite3 或绝对/相对路径。确保账号具有访问权限。",
            "required": True,
        },
        "DB_USER": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "数据库用户名",
            "detail": "连接数据库使用的账号，关联 DB_PASSWORD。仅在 MySQL/PostgreSQL 等服务型数据库下必填；sqlite 可留空。建议使用最小权限的专用账户。",
            "required": False,
        },
        "DB_PASSWORD": {
            "type": SystemConfig.ValueType.SECRET,
            "desc": "数据库密码",
            "detail": "对应 DB_USER 的登录密码，用于建立数据库连接。为敏感信息，后台列表脱敏显示。仅 sqlite 场景可留空，其余数据库必须填写并保证复杂度。",
            "sensitive": True,
            "required": False,
        },
        "DB_HOST": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "数据库主机",
            "detail": "数据库服务器的主机名或 IP 地址，用于 TCP 连接。MySQL/PostgreSQL 等需填写，例如 127.0.0.1 或 db.internal。sqlite 场景留空即可。",
            "required": False,
        },
        "DB_PORT": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "数据库端口",
            "detail": "数据库服务监听端口，需与 DB_HOST 搭配。MySQL 默认 3306，PostgreSQL 默认 5432；sqlite 可留空或写 0。为兼容 env 读取，端口以字符串保存。",
            "required": False,
        },
        # Redis
        "REDIS_HOST": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Redis 主机",
            "detail": "Redis 服务器的主机名或 IP，缓存、限流、记分板和 Celery 都依赖该地址。填写如 127.0.0.1 或 redis.internal。需确保网络可达并与端口/密码一致。",
            "required": True,
        },
        "REDIS_PORT": {
            "type": SystemConfig.ValueType.INT,
            "desc": "Redis 端口",
            "detail": "Redis 服务端口，默认 6379。需填写整数，确保与防火墙和服务配置一致。修改后请同步 Celery/限流等引用。",
            "required": True,
        },
        "REDIS_DB_CACHE": {
            "type": SystemConfig.ValueType.INT,
            "desc": "Redis 缓存库索引",
            "detail": "用于缓存、限流等通用键的 Redis DB 库索引。填写 0-15 的整数，建议与 Celery 使用的库区分，避免键冲突和清理误伤。",
            "required": True,
        },
        "REDIS_DB_CELERY": {
            "type": SystemConfig.ValueType.INT,
            "desc": "Redis Celery Broker 库索引",
            "detail": "Celery Broker 使用的 Redis DB 库索引，用于存放任务队列。可留空使用默认库，但推荐独立库减少键污染。填写整数并确认与 REDIS_DB_CACHE 不同。",
            "required": False,
        },
        "REDIS_DB_CELERY_RESULT": {
            "type": SystemConfig.ValueType.INT,
            "desc": "Redis Celery 结果库索引",
            "detail": "Celery 结果存储使用的 Redis DB 库索引，用于持久化任务返回值。可与 Broker 分离以降低干扰，留空则使用默认。填写整数并避免与其他库冲突。",
            "required": False,
        },
        # Docker/靶机（远程/TLS/网络/镜像前缀可选）
        "DOCKER_HOST": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Docker API Endpoint（为空则本地）",
            "detail": "Docker API 访问地址，决定靶机容器创建所连接的 Docker Daemon。远程节点填写 tcp://host:2375 或 https://host:2376，启用 TLS 时需 https。留空则使用本地 unix/npipe 默认。",
            "required": False,
        },
        "DOCKER_TLS_VERIFY": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "Docker TLS 校验开关",
            "detail": "是否对 Docker API 开启 TLS 校验，保证远程连接安全。公网或跨机房访问必须设为 True 并提供证书；本地或受信网络可设为 False 方便调试。开启后必须同时配置 DOCKER_CERT_PATH。",
            "required": True,
        },
        "DOCKER_CERT_PATH": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Docker TLS 证书路径",
            "detail": "Docker TLS 所需证书目录，需包含 ca.pem/cert.pem/key.pem。仅在 DOCKER_TLS_VERIFY=True 时必填，可写绝对路径或相对项目根的路径。未启用 TLS 时可留空。",
            "required": False,
        },
        "DOCKER_USE_MOCK": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "是否启用 Mock Docker",
            "detail": "控制是否使用 Mock 方式代替真实 Docker 操作，便于测试不启动容器。设为 True 时不会创建真实靶机，生产及比赛环境必须为 False。修改后需重启相关服务。",
            "required": True,
        },
        "DOCKER_NETWORK": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Docker 网络名称",
            "detail": "容器需要加入的 Docker 网络名称，用于隔离或共享网络。自定义网络需提前创建；留空则使用默认 bridge 网络。错误的网络名称会导致容器启动异常。",
            "required": False,
        },
        # 计分/缓存
        "SCOREBOARD_CACHE_TTL": {
            "type": SystemConfig.ValueType.INT,
            "desc": "记分板缓存时间（秒）",
            "detail": "记分板缓存的有效时间，单位秒，影响榜单刷新实时性。填整数；数值越小越实时但会增加查询和缓存失效频率，数值越大则更省资源。封榜后仍按此规则缓存。",
            "required": True,
        },
        # 日志
        "LOG_PATH": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "日志目录路径",
            "detail": "平台运行日志存储的目录路径，默认 logs/。日志文件名为 system.log，支持按日期自动轮转。可填写相对项目根的路径或绝对路径，目录需具备写权限。修改后需重启服务生效。",
            "required": True,
        },
        # Celery
        "CELERY_TASK_DEFAULT_QUEUE": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Celery 默认队列",
            "detail": "Celery 默认任务队列名称，未显式指定 queue 的任务将发送到该队列。需与 worker 启动参数 --queues 对齐。推荐使用易读的英文小写名称。",
            "required": True,
        },
        "CELERY_BROKER_URL": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Celery Broker URL",
            "detail": "Celery Broker 连接串，决定任务队列的存储位置。常用写法为 Redis：redis://user:pass@host:port/db，也可接入 RabbitMQ 等。需确保账号和网络可访问，对应库索引与 REDIS 配置匹配。",
            "required": True,
        },
        "CELERY_RESULT_BACKEND": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Celery 结果存储 URL",
            "detail": "Celery 任务结果存储的连接串，决定任务返回值的落库位置。通常与 Broker 共用 Redis，可写 redis://... 格式；也可改为数据库后端。格式需符合 Celery 支持的后端写法，否则任务结果无法写入。",
            "required": True,
        },
    }

    def __init__(self, repo: SystemConfigRepo | None = None):
        self.repo = repo or SystemConfigRepo()

    def _cache_key(self, key: str) -> str:
        return f"{self.cache_prefix}{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（按优先级读取）：

        优先级顺序：
        1. 后台配置（SystemConfig 表，管理员通过后台"基础配置"设置）
        2. settings.py 硬编码值（默认值，首次启动时会自动填入后台）
        3. 传入的 default 参数（兜底值）

        注意：
        - Redis 不可用时自动降级跳过缓存，直接查数据库
        - 配置变更后需调用 invalidate() 清理缓存
        - 部分配置（如 SECRET_KEY、数据库）修改后需重启服务生效
        """
        cache_key = self._cache_key(key)

        # 尝试从缓存读取，失败时记录日志并降级
        try:
            if (cached := cache.get(cache_key)) is not None:
                return cached
        except Exception as e:
            logger.warning(f"缓存读取失败，降级到数据库查询: {e}")

        # 优先级 1：从数据库读取后台配置
        cfg = self.repo.get_by_key(key)
        if cfg:
            value = cfg.cast_value()
            # 尝试写缓存，失败不影响返回
            try:
                cache.set(cache_key, value, timeout=self.cache_timeout)
            except Exception as e:
                logger.warning(f"缓存写入失败: {e}")
            return value

        # 优先级 2：从 settings.py 读取默认值
        value = getattr(settings, key, None)
        if value is None:
            # 优先级 3：使用传入的 default 参数
            value = default

        # 尝试写缓存，失败不影响返回
        try:
            cache.set(cache_key, value, timeout=self.cache_timeout)
        except Exception as e:
            logger.warning(f"缓存写入失败: {e}")

        return value

    def get_supported_default(self, key: str, default: Any = None) -> Any:
        """
        获取支持覆盖项的默认值（用于初始化后台配置）

        用途：
        - 首次启动时，从 settings.py 读取默认值填入 SystemConfig 表
        - 不再读取 .env 文件，所有默认值都在 settings.py 中硬编码

        返回值：
        - settings.py 中对应配置项的值
        - 若未定义则返回传入的 default 参数
        """
        # 特殊处理：LOG_PATH 返回相对路径（避免硬编码绝对路径到后台）
        if key == "LOG_PATH":
            value = getattr(settings, key, None) or "logs/"
            return value

        # 直接从 settings.py 读取默认值（不再读取 .env）
        value = getattr(settings, key, None)
        return value if value is not None else default

    def ensure_supported_configs(self) -> None:
        """确保支持的配置项都存在记录，缺失时按默认值创建，并同步元数据"""
        existing = {c.key: c for c in self.repo.model.objects.all()}
        to_create = []
        for key, meta in self.SUPPORTED_CONFIGS.items():
            if key in existing:
                cfg = existing[key]
                updated = False
                value_type = meta.get("type", SystemConfig.ValueType.STRING)
                is_sensitive = meta.get("sensitive", False)
                is_required = meta.get("required", False)
                desc = meta.get("desc", "")
                detail_desc = meta.get("detail", "")
                if cfg.value_type != value_type:
                    cfg.value_type = value_type
                    updated = True
                if cfg.is_sensitive != is_sensitive:
                    cfg.is_sensitive = is_sensitive
                    updated = True
                if cfg.is_required != is_required:
                    cfg.is_required = is_required
                    updated = True
                if cfg.description != desc:
                    cfg.description = desc
                    updated = True
                if cfg.detail_description != detail_desc:
                    cfg.detail_description = detail_desc
                    updated = True
                if updated:
                    cfg.save(
                        update_fields=[
                            "value_type",
                            "is_sensitive",
                            "is_required",
                            "description",
                            "detail_description",
                            "updated_at",
                        ]
                    )
                continue
            default_val = self.get_supported_default(key, "")
            value_type = meta.get("type", SystemConfig.ValueType.STRING)
            is_sensitive = meta.get("sensitive", False)
            cfg = SystemConfig(
                key=key,
                value=str(default_val) if default_val is not None else "",
                value_type=value_type,
                description=meta.get("desc", ""),
                detail_description=meta.get("detail", ""),
                is_sensitive=is_sensitive,
                is_required=meta.get("required", False),
            )
            to_create.append(cfg)
        if to_create:
            self.repo.model.objects.bulk_create(to_create, ignore_conflicts=True)

    def invalidate(self, key: str | None = None) -> None:
        """
        配置变更后清理缓存

        注：Redis 不可用时仅记录日志，不影响配置更新流程
        """
        try:
            if key:
                cache.delete(self._cache_key(key))
            else:
                cache.clear()
        except Exception as e:
            logger.warning(f"缓存失效操作失败（不影响配置更新）: {e}")

    def perform(self, *args, **kwargs):
        """占位实现，满足 BaseService 抽象约束"""
        return None


def apply_security_settings_from_config():
    """
    启动时根据 SystemConfig 覆盖部分安全相关 settings
    - 允许管理员在后台调整 HTTPS/CSRF 行为，重启后生效
    - 读取失败时记录日志但不阻断启动
    """
    from django.conf import settings  # 延迟导入避免循环

    cfg = ConfigService()

    def _normalize_origins(val):
        if val is None:
            return []
        if isinstance(val, str):
            try:
                # 尝试解析 JSON 字符串
                import json
                loaded = json.loads(val)
                if isinstance(loaded, list):
                    return [str(v).strip() for v in loaded if str(v).strip()]
            except Exception:
                # 尝试解析 Python 风格列表（如 "['http://localhost']"）
                try:
                    import ast

                    loaded = ast.literal_eval(val)
                    if isinstance(loaded, (list, tuple, set)):
                        return [str(v).strip() for v in loaded if str(v).strip()]
                except Exception:
                    pass
                # fallback: 逗号分隔
                return [v.strip().strip("'\"") for v in val.split(",") if v.strip().strip("'\"")]
        if isinstance(val, (list, tuple, set)):
            return [str(v).strip() for v in val if str(v).strip()]
        return [str(val).strip()]

    try:
        settings.DEBUG = bool(cfg.get("DEBUG", settings.DEBUG))
        settings.SECURE_SSL_REDIRECT = bool(
            cfg.get("SECURE_SSL_REDIRECT", getattr(settings, "SECURE_SSL_REDIRECT", False))
        )
        settings.SESSION_COOKIE_SECURE = bool(
            cfg.get("SESSION_COOKIE_SECURE", getattr(settings, "SESSION_COOKIE_SECURE", False))
        )
        settings.CSRF_COOKIE_SECURE = bool(
            cfg.get("CSRF_COOKIE_SECURE", getattr(settings, "CSRF_COOKIE_SECURE", False))
        )
        origins = _normalize_origins(cfg.get("CSRF_TRUSTED_ORIGINS", getattr(settings, "CSRF_TRUSTED_ORIGINS", [])))
        settings.CSRF_TRUSTED_ORIGINS = origins
        cors_origins = _normalize_origins(
            cfg.get("CORS_ALLOWED_ORIGINS", getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        )
        if cors_origins:
            settings.CORS_ALLOW_ALL_ORIGINS = False
            settings.CORS_ALLOWED_ORIGINS = cors_origins
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"安全配置应用失败（跳过覆盖，使用默认值）：{exc}")
