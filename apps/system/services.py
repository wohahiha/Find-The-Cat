from __future__ import annotations

import os
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
    系统配置服务：
    - 优先读取后台启用的配置值
    - 回退到 .env/settings，再回退到代码默认
    """

    cache_prefix = "system_config:"
    cache_timeout = 300  # 缓存 5 分钟
    # 支持后台覆盖的配置清单：key -> 类型/描述/敏感/必填
    SUPPORTED_CONFIGS = {
        # 安全/调试
        "SECRET_KEY": {
            "type": SystemConfig.ValueType.SECRET,
            "desc": "Django SECRET_KEY",
            "detail": "用于签名和加密，会影响 JWT、CSRF 等安全组件的安全性。必须保持机密且不可为空，泄露会导致 Token 与会话失效被伪造。请填写长度 50+ 的高熵随机字符串，不要与其他环境复用。",
            "sensitive": True,
            "required": True,
        },
        "DEBUG": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "DEBUG 开关（生产应为 False）",
            "detail": "控制 Django 是否开启调试模式，影响错误栈展示和静态资源加载方式。生产环境必须关闭以避免泄露敏感信息，开启只用于本地调试。取值 True/False，可配合 ALLOWED_HOSTS 限制来源。",
            "required": True,
        },
        "ALLOWED_HOSTS": {
            "type": SystemConfig.ValueType.JSON,
            "desc": "允许的主机列表",
            "detail": "限制可访问站点的域名或 IP，防止 Host 头攻击。填写 JSON 数组格式，如 [\"example.com\", \"127.0.0.1\" ]。生产必须填写实际域名/IP，调试可包含 localhost。",
            "required": True,
        },
        "ALLOW_LOGIN_WITHOUT_CAPTCHA": {
            "type": SystemConfig.ValueType.BOOL,
            "desc": "允许登录跳过图形验证码（仅测试用）",
            "detail": "控制登录时是否强制校验图形验证码。仅在联调或自动化测试时可暂时置为 True，生产环境应保持 False 以防爆破。开启 True 时仍应搭配限流策略避免滥用。",
            "required": True,
        },
        # 数据库（sqlite 场景可为空的连接信息不标必填）
        "DB_ENGINE": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "数据库引擎（sqlite/mysql/postgres）",
            "detail": "指定 Django 使用的数据库后端类型，决定连接驱动与后续字段校验。可填写 sqlite、mysql、postgres 等小写值。选择非 sqlite 时需同时填写主机/端口/账号等信息。",
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
        "DOCKER_IMAGE_PREFIX": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Docker 镜像前缀",
            "detail": "镜像仓库前缀或命名空间，用于构造完整镜像名，例如 registry.example.com/ftc。私有仓库必须填写正确前缀，公共 Docker Hub 可留空。结尾无需斜杠，系统自动拼接。",
            "required": False,
        },
        "DOCKER_IMAGE_TAG": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Docker 镜像标签",
            "detail": "靶机镜像的标签版本，用于指定拉取的镜像变体。可填 latest 或具体版本号，例如 v1.2.3。需与镜像仓库中存在的标签一致，否则启动会失败。",
            "required": True,
        },
        "DOCKER_CONTAINER_PORT": {
            "type": SystemConfig.ValueType.INT,
            "desc": "容器内部服务端口",
            "detail": "容器内服务暴露的端口号，用于主机端口映射。必须为整数，通常与题目镜像 Dockerfile 中 EXPOSE 的端口一致。填写错误将导致端口映射失败或服务不可达。",
            "required": True,
        },
        "DOCKER_NETWORK": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "Docker 网络名称",
            "detail": "容器需要加入的 Docker 网络名称，用于隔离或共享网络。自定义网络需提前创建；留空则使用默认 bridge 网络。错误的网络名称会导致容器启动异常。",
            "required": False,
        },
        "MACHINE_MAX_RUNTIME_MINUTES": {
            "type": SystemConfig.ValueType.INT,
            "desc": "靶机实例最长运行分钟数",
            "detail": "单个靶机实例允许存活的最大分钟数，超时将被定时任务自动销毁并释放端口。填写整数，过短会影响选手解题，过长会占用机器资源。根据比赛时长和题目规模设置合理值。",
            "required": True,
        },
        "MACHINE_CLEAN_INTERVAL_SECONDS": {
            "type": SystemConfig.ValueType.INT,
            "desc": "靶机超时清理间隔（秒）",
            "detail": "定时扫描并清理超时靶机的执行周期，单位秒。填写整数，较小的间隔能更快回收端口，较大的间隔可减少调度频率。应与 MACHINE_MAX_RUNTIME_MINUTES 配合评估。",
            "required": True,
        },
        "MACHINE_PORT_CACHE_TTL": {
            "type": SystemConfig.ValueType.INT,
            "desc": "靶机端口占用缓存 TTL（秒）",
            "detail": "宿主机端口占用标记的缓存时间，防止并发分配到同一端口。单位秒，需大于容器启动耗时；过长会导致端口回收延迟。填写整数并与运行规模匹配。",
            "required": True,
        },
        # 计分/缓存
        "SCOREBOARD_CACHE_TTL": {
            "type": SystemConfig.ValueType.INT,
            "desc": "记分板缓存时间（秒）",
            "detail": "记分板缓存的有效时间，单位秒，影响榜单刷新实时性。填整数；数值越小越实时但会增加查询和缓存失效频率，数值越大则更省资源。封榜后仍按此规则缓存。",
            "required": True,
        },
        # 日志
        "LOG_FILE": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "日志文件路径",
            "detail": "平台运行日志写入的文件路径，默认 logs/ftc.log。可填写相对项目根的路径或绝对路径，目录需具备写权限。修改后建议重启服务以确保新的路径生效。",
            "required": True,
        },
        "LOG_LEVEL": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "日志等级",
            "detail": "日志输出等级，控制写入多少调试信息。可填 INFO、DEBUG、WARN、ERROR 等，生产环境建议 INFO 或 WARN 以减少噪声，DEBUG 仅用于问题排查。必须填写标准等级字符串。",
            "required": True,
        },
        "LOG_FORMAT": {
            "type": SystemConfig.ValueType.STRING,
            "desc": "日志格式（json/text）",
            "detail": "日志输出格式，可选 json 或 text。json 便于集中式日志收集与检索，text 更适合本地阅读。填写小写格式名，修改后需重启服务才会应用。",
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
        获取配置值：
        优先后台启用项 -> settings/.env -> 传入默认
        """
        cache_key = self._cache_key(key)
        if (cached := cache.get(cache_key)) is not None:
            return cached

        cfg = self.repo.get_by_key(key)
        if cfg:
            value = cfg.cast_value()
            cache.set(cache_key, value, timeout=self.cache_timeout)
            return value

        value = getattr(settings, key, None)
        if value is None:
            value = os.getenv(key, default)
        if value is None:
            value = default
        cache.set(cache_key, value, timeout=self.cache_timeout)
        return value

    def get_supported_default(self, key: str, default: Any = None) -> Any:
        """获取支持覆盖项的默认值（settings/env 兜底）"""
        if key == "LOG_FILE":
            # 避免将本地绝对路径预填到后台，提供相对默认值
            value = getattr(settings, key, None) or "logs/ftc.log"
            return value
        value = getattr(settings, key, None)
        if value is None:
            value = os.getenv(key, default)
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
                is_active=True,
                is_sensitive=is_sensitive,
                is_required=meta.get("required", False),
            )
            to_create.append(cfg)
        if to_create:
            self.repo.model.objects.bulk_create(to_create, ignore_conflicts=True)

    def invalidate(self, key: str | None = None) -> None:
        """配置变更后清理缓存"""
        if key:
            cache.delete(self._cache_key(key))
        else:
            cache.clear()

    def perform(self, *args, **kwargs):
        """占位实现，满足 BaseService 抽象约束"""
        return None
