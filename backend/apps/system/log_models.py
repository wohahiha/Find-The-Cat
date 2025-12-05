"""
日志数据模型

定义 LogEntry 和 LogParser 类，用于日志的解析、存储和展示。
符合 FTC 日志标准。
"""
from datetime import datetime
from typing import Optional, Dict, Generator, List
import os

from apps.common.utils.log_formatter import (
    to_plain,
    parse_json,
    parse_plain,
    detect_format,
    format_message_summary
)


class LogEntry:
    """
    日志条目类

    表示一条解析后的日志，提供统一的访问接口。
    无论原始格式是 JSON 还是 PLAIN，统一转换为 LogEntry 对象。
    """

    def __init__(
            self,
            id: int,
            timestamp: datetime,
            level: str,
            logger_name: str,
            message: str,
            username: Optional[str] = None,
            user_id: Optional[int] = None,
            account_id: Optional[int] = None,
            ip_address: Optional[str] = None,
            request_path: Optional[str] = None,
            **kwargs  # 允许额外字段
    ):
        """
        初始化日志条目

        Args:
            id: 日志行号（唯一标识）
            timestamp: 日志时间
            level: 日志级别（INFO/WARNING/ERROR/CRITICAL）
            logger_name: logger 名称
            message: 日志消息
            username: 用户名（可选）
            user_id: 用户ID（可选）
            account_id: 账户ID（可选）
            ip_address: IP地址（可选）
            request_path: 请求路径（可选）
            **kwargs: 其他扩展字段
        """
        self.id = id
        self.timestamp = timestamp
        self.level = level
        self.logger_name = logger_name
        self.message = message
        self.username = username
        self.user_id = user_id
        self.account_id = account_id
        self.ip_address = ip_address
        self.request_path = request_path
        self.extra = kwargs  # 存储额外字段

        # Django Admin 需要的字段
        self.state = type('obj', (object,), {'adding': False, 'db': 'default'})
        # 部分 Admin 功能依赖 _state 属性，补充兼容
        self._state = self.state
        self.pk = id

        # 添加_meta属性（从SystemLog模型获取）
        from apps.system.models import SystemLog
        self._meta = SystemLog._meta

    def serializable_value(self, field_name: str):
        """
        返回字段的可序列化值（Django Admin需要）

        Args:
            field_name: 字段名

        Returns:
            字段值
        """
        return getattr(self, field_name, None)

    def get_type(self) -> str:
        """
        获取日志类型（大类）

        根据 logger 名称自动判断：
        - 业务日志：apps.accounts, apps.contests, apps.challenges, apps.submissions, apps.machines, apps.problem_bank
        - 系统日志：apps.system, apps.common, celery, root
        - 框架日志：django.*
        - 其他：未匹配以上规则

        Returns:
            日志类型字符串
        """
        # 系统日志（优先级最高，必须先判断）
        if self.logger_name.startswith('apps.system') or \
                self.logger_name.startswith('apps.common') or \
                self.logger_name in ['celery', 'root', 'system']:
            return '系统日志'
        # 业务日志
        elif self.logger_name.startswith('apps.'):
            return '业务日志'
        # 框架日志
        elif self.logger_name.startswith('django.'):
            return '框架日志'
        # 其他
        else:
            return '其他'

    def get_source(self) -> str:
        """
        获取日志来源（小类）

        日志标准要求来源字段限定为：accounts/contests/challenges/submissions/machines/system/django，
        因此需要将 logger 名称映射到上述集合，避免出现 __main__、django.request 等原始值。
        """
        logger_name = self.logger_name or ""

        # 业务模块映射，仅保留一级模块名称
        business_apps = {"accounts", "contests", "challenges", "submissions", "machines"}
        if logger_name.startswith("apps."):
            parts = logger_name.split(".", 2)
            if len(parts) >= 2:
                app_name = parts[1]
                if app_name in business_apps:
                    return app_name
                # system/common 归类到系统日志
                if app_name in {"system", "common"}:
                    return "system"
                # 其他业务模块（如 problem_bank）归入 challenges，便于保持统一来源
                if app_name == "problem_bank":
                    return "challenges"

        # Django/框架日志统一显示为 django
        if logger_name.startswith("django."):
            return "django"
        if logger_name == "django":
            return "django"

        # 系统级 logger 统一归到 system
        system_loggers = {"system", "celery", "root", "__main__"}
        if logger_name in system_loggers:
            return "system"

        # 未匹配的情况统一归类为 system，避免出现标准之外的值
        return "system"

    def get_summary(self, max_length: int = 150) -> str:
        """
        获取消息摘要

        智能截断和格式化日志消息：
        1. 错误堆栈：只显示错误类型和第一行
        2. JSON 日志：提取 message 字段
        3. 普通文本：去除换行和多余空格，截断到指定长度

        Args:
            max_length: 最大长度，默认 150 字符

        Returns:
            格式化后的消息摘要
        """
        return format_message_summary(self.message, max_length)

    def to_json(self) -> Dict:
        """
        转换为 JSON 格式的字典

        Returns:
            包含所有字段的字典
        """
        data = {
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'level': self.level,
            'logger': self.logger_name,
            'message': self.message,
        }

        # 添加可选字段
        if self.username:
            data['username'] = self.username
        if self.user_id is not None:
            data['user_id'] = self.user_id
        if self.account_id is not None:
            data['account_id'] = self.account_id
        if self.ip_address:
            data['ip_address'] = self.ip_address
        if self.request_path:
            data['request_path'] = self.request_path

        # 添加额外字段
        data.update(self.extra)

        return data

    def to_plain(self) -> str:
        """
        转换为 PLAIN 格式的字符串

        Returns:
            PLAIN 格式的日志字符串
        """
        return to_plain(self.to_json())

    def __str__(self):
        """字符串表示"""
        return f"LogEntry({self.id}, {self.timestamp}, {self.level}, {self.logger_name})"

    def __repr__(self):
        """调试表示"""
        return self.__str__()


class LogParser:
    """
    日志解析器

    解析日志文件，支持 JSON 和 PLAIN 两种格式。
    提供逐行解析、格式检测、过滤等功能。
    """

    def __init__(self, file_path: str):
        """
        初始化日志解析器

        Args:
            file_path: 日志文件路径
        """
        self.file_path = file_path

    def parse_file(
            self,
            filters: Optional[Dict] = None,
            limit: Optional[int] = 500,
            offset: int = 0,
            *,
            order: str = "desc",
    ) -> Generator[LogEntry, None, None]:
        """
        解析日志文件（生成器）

        逐行读取和解析日志文件，返回 LogEntry 对象。
        支持边解析边过滤，提高性能。
        支持多行日志（如堆栈跟踪）的合并。

        Args:
            filters: 过滤条件字典，例如 {'level': 'ERROR', 'type': '业务日志'}
            limit: 返回的最大日志数量（分页）
            offset: 跳过的日志数量（分页）

        Yields:
            LogEntry 对象

        Example:
            >>> parser = LogParser('logs/ftc.log')
            >>> for entry in parser.parse_file(filters={'level': 'ERROR'}, limit=50):
            ...     print(entry)
        """
        if not os.path.exists(self.file_path):
            return

        count = 0  # 已返回的日志数量
        skipped = 0  # 已跳过的日志数量
        entry_id = 0  # 日志条目自增ID
        current_entry = None  # 当前正在构建的日志条目
        buffer: list[LogEntry] = []

        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stripped_line = line.rstrip('\n\r')

                # 检测是否是新的日志条目（以时间戳开头）
                is_new_entry = detect_format(stripped_line) is not None

                if is_new_entry:
                    # 如果有正在构建的条目，先加入缓冲
                    if current_entry is not None:
                        if not filters or self._match_filters(current_entry, filters):
                            buffer.append(current_entry)

                        # 保持缓冲大小不超过 limit + offset
                        target_size = (limit or len(buffer)) + offset
                        if len(buffer) > target_size:
                            buffer.pop(0)

                    # 解析新日志条目
                    new_entry = self.parse_line(stripped_line, entry_id + 1)
                    if new_entry is not None:
                        entry_id += 1
                    current_entry = new_entry
                else:
                    # 这是一个继续行（堆栈跟踪、多行消息等）
                    if current_entry is not None and stripped_line:
                        current_entry.message += '\n' + stripped_line

            # 处理最后一个条目
            if current_entry is not None:
                if not filters or self._match_filters(current_entry, filters):
                    buffer.append(current_entry)
                    target_size = (limit or len(buffer)) + offset
                    if len(buffer) > target_size:
                        buffer.pop(0)

        if order == "desc":
            buffer.reverse()

        for entry in buffer:
            if skipped < offset:
                skipped += 1
                continue
            yield entry
            count += 1
            if limit and count >= limit:
                break

    def parse_line(self, line: str, entry_id: int) -> Optional[LogEntry]:
        """
        解析单行日志

        自动检测格式（JSON 或 PLAIN），解析为 LogEntry 对象。

        Args:
            line: 日志字符串
            entry_id: 自增ID（作为 LogEntry 的 id）

        Returns:
            LogEntry 对象，解析失败返回 None
        """
        line = line.strip()
        if not line:
            return None

        # 检测格式
        format_type = detect_format(line)

        if format_type == 'json':
            return self.parse_json_line(line, entry_id)
        elif format_type == 'plain':
            return self.parse_plain_line(line, entry_id)
        else:
            # 无法识别的格式，尝试按普通文本处理
            return self._parse_fallback(line, entry_id)

    def parse_json_line(self, line: str, entry_id: int) -> Optional[LogEntry]:
        """
        解析 JSON 格式的日志行

        Args:
            line: JSON 格式的日志字符串
            entry_id: 日志条目 ID

        Returns:
            LogEntry 对象，解析失败返回 None
        """
        log_dict = parse_json(line)
        if log_dict is None:
            return None

        return self._dict_to_entry(log_dict, entry_id)

    def parse_plain_line(self, line: str, entry_id: int) -> Optional[LogEntry]:
        """
        解析 PLAIN 格式的日志行

        Args:
            line: PLAIN 格式的日志字符串
            entry_id: 日志条目 ID

        Returns:
            LogEntry 对象，解析失败返回 None
        """
        log_dict = parse_plain(line)
        if log_dict is None:
            return None

        return self._dict_to_entry(log_dict, entry_id)

    def _dict_to_entry(self, log_dict: Dict, entry_id: int) -> Optional[LogEntry]:
        """
        将日志字典转换为 LogEntry 对象

        Args:
            log_dict: 日志数据字典
            entry_id: 日志条目 ID

        Returns:
            LogEntry 对象
        """
        try:
            # 解析时间戳
            timestamp_str = log_dict.get('timestamp', '')
            if isinstance(timestamp_str, str):
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            else:
                timestamp = datetime.now()

            # 提取其他字段
            level = log_dict.get('level', 'INFO')
            logger_name = log_dict.get('logger', '')
            message = log_dict.get('message', '')

            # 提取可选字段
            username = log_dict.get('username')
            user_id = log_dict.get('user_id')
            account_id = log_dict.get('account_id')
            ip_address = log_dict.get('ip_address')
            request_path = log_dict.get('request_path')

            # 提取额外字段
            extra = {k: v for k, v in log_dict.items()
                     if k not in ['timestamp', 'level', 'logger', 'message',
                                  'username', 'user_id', 'account_id',
                                  'ip_address', 'request_path']}

            return LogEntry(
                id=entry_id,
                timestamp=timestamp,
                level=level,
                logger_name=logger_name,
                message=message,
                username=username,
                user_id=user_id,
                account_id=account_id,
                ip_address=ip_address,
                request_path=request_path,
                **extra
            )
        except (ValueError, KeyError):
            # 解析失败
            return None

    def _parse_fallback(self, line: str, entry_id: int) -> Optional[LogEntry]:
        """
        无法识别格式时的降级处理

        尽量从日志行中提取基本信息（时间、级别、消息）。

        Args:
            line: 日志字符串
            entry_id: 日志条目 ID

        Returns:
            LogEntry 对象，提取失败返回 None
        """
        # 简单处理：将整行作为消息
        return LogEntry(
            id=entry_id,
            timestamp=datetime.now(),
            level='INFO',
            logger_name='unknown',
            message=line
        )

    def _match_filters(self, entry: LogEntry, filters: Dict) -> bool:
        """
        检查日志条目是否匹配过滤条件

        Args:
            entry: LogEntry 对象
            filters: 过滤条件字典

        Returns:
            是否匹配

        Example:
            >>> filters = {'level': 'ERROR', 'type': '业务日志'}
            >>> self._match_filters(entry, filters)
            True
        """
        for key, value in filters.items():
            if key == 'level':
                if entry.level != value:
                    return False

            elif key == 'type':
                if entry.get_type() != value:
                    return False

            elif key == 'source':
                if entry.get_source() != value:
                    return False

            elif key == 'account_type':
                # 账户类型过滤
                if not self._match_account_type(entry, value):
                    return False

            elif key == 'logger':
                if entry.logger_name != value:
                    return False

            elif key == 'username':
                if entry.username != value:
                    return False

            elif key == 'ip':
                if entry.ip_address != value:
                    return False

        return True

    def _match_account_type(self, entry: LogEntry, account_type: str) -> bool:
        """
        检查账户类型是否匹配

        Args:
            entry: LogEntry 对象
            account_type: 账户类型（'superadmin' | 'admin' | 'user' | 'system'）

        Returns:
            是否匹配
        """
        account_id = entry.account_id

        if account_type == 'superadmin':
            return account_id is not None and 1 <= account_id <= 10
        elif account_type == 'admin':
            return account_id is not None and 11 <= account_id <= 1000
        elif account_type == 'user':
            return account_id is not None and account_id >= 1001
        elif account_type == 'system':
            return account_id is None
        else:
            return False

    def count(self, filters: Optional[Dict] = None) -> int:
        """
        统计日志总数（应用过滤条件）

        Args:
            filters: 过滤条件字典

        Returns:
            日志总数
        """
        count = 0
        for _ in self.parse_file(filters=filters):
            count += 1
        return count

    def get_unique_sources(self, limit: int = 20) -> List[str]:
        """
        获取所有唯一的日志来源

        用于动态生成"来源过滤器"的选项。

        Args:
            limit: 返回的最大数量

        Returns:
            来源列表（去重后）

        Example:
            >>> parser.get_unique_sources()
            ['accounts.services', 'system.apps', 'django.request', ...]
        """
        sources = set()
        for entry in self.parse_file():
            sources.add(entry.get_source())
            if len(sources) >= limit:
                break
        return sorted(list(sources))
