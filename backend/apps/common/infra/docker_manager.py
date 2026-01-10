"""
Docker 管理封装：
- 业务场景：题目靶机的启动/停止，支持本地或远程 Docker
- 模块角色：统一封装容器操作，提供 mock 模式，屏蔽底层 SDK 差异
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from django.conf import settings
from apps.common.infra.logger import get_logger

_USE_MOCK = os.getenv("DOCKER_USE_MOCK", "0") == "1"
# 镜像前缀/标签、容器端口、网络等配置，通过环境变量控制，便于举办方自定义
IMAGE_PREFIX = os.getenv("DOCKER_IMAGE_PREFIX", "")  # 例：registry.local/ftc/
IMAGE_TAG = os.getenv("DOCKER_IMAGE_TAG", "latest")
CONTAINER_PORT = int(os.getenv("DOCKER_CONTAINER_PORT", "80"))  # 容器内服务端口，默认 80
DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", None)  # 可选：docker 网络名称
# 安全开关：默认非特权用户 + 剥离能力，支持只读根和禁网（通过环境变量控制）
RUN_AS_NON_ROOT = os.getenv("DOCKER_RUN_AS_NON_ROOT", "1") == "1"
DEFAULT_RUN_USER = os.getenv("DOCKER_DEFAULT_USER", "65534:65534")  # nobody:nogroup
DROP_ALL_CAPS = os.getenv("DOCKER_DROP_ALL_CAPS", "1") == "1"
READ_ONLY_ROOT = os.getenv("DOCKER_READ_ONLY_ROOT", "0") == "1"
DISABLE_NETWORK_WHEN_POSSIBLE = os.getenv("DOCKER_DISABLE_NETWORK", "0") == "1"

try:
    import docker  # type: ignore
except Exception:  # pragma: no cover
    docker = None

_logger = get_logger(__name__)


def _get_client():
    """获取 Docker client，支持环境变量配置与 TLS；mock 模式下返回 None"""
    if _USE_MOCK:
        return None
    if not docker:
        raise RuntimeError("未安装 docker SDK，请 pip install docker 或设置 DOCKER_USE_MOCK=1 启用模拟模式")
    host = getattr(settings, "DOCKER_HOST", None)
    tls_verify = os.getenv("DOCKER_TLS_VERIFY", "0")
    cert_path = os.getenv("DOCKER_CERT_PATH", None)

    kwargs = {}
    if host:
        kwargs["base_url"] = host
    if tls_verify == "1" and cert_path:
        tls_config = docker.tls.TLSConfig(
            client_cert=(os.path.join(cert_path, "cert.pem"), os.path.join(cert_path, "key.pem")),
            verify=True,
            ca_cert=os.path.join(cert_path, "ca.pem"),
        )
        kwargs["tls"] = tls_config
    try:
        return docker.from_env(**kwargs) if not host else docker.DockerClient(**kwargs)
    except Exception:
        _logger.exception("Docker client 连接失败", extra={"host": host or "local"})
        raise


def start_container(
        image: str,
        *,
        name: Optional[str] = None,
        port: Optional[int] = None,
        env: Optional[dict] = None,
        container_port: int | None = None,
        network: Optional[str] = None,
) -> str:
    """
    启动容器：
    - image：镜像名（外部可传完整名，或结合 IMAGE_PREFIX/TAG 预处理）
    - name：可选容器名
    - port：映射到宿主机的端口（映射容器内 container_port，默认 80）
    - env：环境变量（可用于注入动态 flag）
    - container_port：容器内部监听端口，未指定则使用环境变量 CONTAINER_PORT
    - network：可选 docker 网络名称
    返回容器 ID
    """
    if _USE_MOCK:
        return f"mock-{secrets.token_hex(4)}"
    client = _get_client()
    ports = {}
    if port:
        c_port = container_port or CONTAINER_PORT or 80
        ports = {f"{c_port}/tcp": port}
    # 允许通过全局网络配置注入
    run_kwargs = {
        "detach": True,
        "name": name,
        "ports": ports or None,
        "environment": env or None,
    }
    # 安全默认：非特权用户 + 剥离特权，可通过环境变量关闭
    if RUN_AS_NON_ROOT and DEFAULT_RUN_USER:
        run_kwargs["user"] = DEFAULT_RUN_USER
    if DROP_ALL_CAPS:
        run_kwargs["cap_drop"] = ["ALL"]
    if READ_ONLY_ROOT:
        run_kwargs["read_only"] = True
    # 网络限制：若明确禁网且未暴露端口，则 network_mode=none；否则使用指定/默认网络
    if DISABLE_NETWORK_WHEN_POSSIBLE and not port:
        run_kwargs["network_mode"] = "none"
    elif network or DOCKER_NETWORK:
        run_kwargs["network"] = network or DOCKER_NETWORK
    container = client.containers.run(
        image,
        **run_kwargs,
    )
    return container.id


def stop_container(container_id: str) -> None:
    """
    停止并移除容器
    - mock 模式直接返回，不做实际操作
    """
    if _USE_MOCK:
        return
    client = _get_client()
    try:
        container = client.containers.get(container_id)
        container.stop()
        container.remove()
    except Exception:
        # 容器可能已不存在，忽略
        return
