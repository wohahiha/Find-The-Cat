"""
日志格式转换模块

提供 JSON 和 PLAIN 格式之间的互相转换功能，符合 FTC 日志标准。
"""
import json
import re
from datetime import datetime
from typing import Dict, Optional


def to_json(log_dict: Dict) -> str:
    """
    将日志字典转换为 JSON 格式字符串

    Args:
        log_dict: 日志数据字典，包含标准字段

    Returns:
        JSON 格式的日志字符串（单行，无缩进）

    Example:
        >>> log = {
        ...     'timestamp': '2025-11-28 16:57:25',
        ...     'level': 'INFO',
        ...     'logger': 'apps.accounts.services',
        ...     'message': '用户登录成功',
        ...     'username': 'admin',
        ...     'account_id': 1,
        ...     'ip_address': '127.0.0.1',
        ...     'request_path': '/api/accounts/auth/login/'
        ... }
        >>> to_json(log)
        '{"timestamp":"2025-11-28 16:57:25","level":"INFO",...}'
    """
    # 确保时间戳是字符串格式
    if isinstance(log_dict.get('timestamp'), datetime):
        log_dict = log_dict.copy()
        log_dict['timestamp'] = log_dict['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

    # 转换为 JSON 字符串（单行，无缩进）
    return json.dumps(log_dict, ensure_ascii=False, separators=(',', ':'))


def to_plain(log_dict: Dict) -> str:
    """
    将日志字典转换为 PLAIN 格式字符串

    格式：{timestamp} {level} {logger} {message} [{username}|{account_id}|{ip_address}|{request_path}]

    Args:
        log_dict: 日志数据字典，包含标准字段

    Returns:
        PLAIN 格式的日志字符串

    Example:
        >>> log = {
        ...     'timestamp': '2025-11-28 16:57:25',
        ...     'level': 'INFO',
        ...     'logger': 'apps.accounts.services',
        ...     'message': '用户登录成功',
        ...     'username': 'admin',
        ...     'account_id': 1,
        ...     'ip_address': '127.0.0.1',
        ...     'request_path': '/api/accounts/auth/login/'
        ... }
        >>> to_plain(log)
        '2025-11-28 16:57:25 INFO apps.accounts.services 用户登录成功 [admin|1|127.0.0.1|/api/accounts/auth/login/]'
    """
    # 提取必需字段
    timestamp = log_dict.get('timestamp', '')
    if isinstance(timestamp, datetime):
        timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

    level = log_dict.get('level', 'INFO')
    logger = log_dict.get('logger', '')
    message = log_dict.get('message', '')

    # 提取可选字段（上下文信息）
    username = log_dict.get('username') or '-'
    account_id = str(log_dict.get('account_id')) if log_dict.get('account_id') is not None else '-'
    ip_address = log_dict.get('ip_address') or '-'
    request_path = log_dict.get('request_path') or '-'

    # 拼接 PLAIN 格式字符串
    context = f"[{username}|{account_id}|{ip_address}|{request_path}]"
    return f"{timestamp} {level} {logger} {message} {context}"


def parse_json(json_str: str) -> Optional[Dict]:
    """
    解析 JSON 格式的日志字符串

    Args:
        json_str: JSON 格式的日志字符串

    Returns:
        日志数据字典，解析失败返回 None

    Example:
        >>> json_str = '{"timestamp":"2025-11-28 16:57:25","level":"INFO","logger":"apps.accounts.services",...}'
        >>> parse_json(json_str)
        {'timestamp': '2025-11-28 16:57:25', 'level': 'INFO', ...}
    """
    try:
        log_dict = json.loads(json_str)

        # 验证必需字段
        required_fields = ['timestamp', 'level', 'logger', 'message']
        if not all(field in log_dict for field in required_fields):
            return None

        return log_dict
    except (json.JSONDecodeError, ValueError):
        return None


def parse_plain(plain_str: str) -> Optional[Dict]:
    """
    解析 PLAIN 格式的日志字符串

    格式：{timestamp} {level} {logger} {message} [{username}|{account_id}|{ip_address}|{request_path}]

    Args:
        plain_str: PLAIN 格式的日志字符串

    Returns:
        日志数据字典，解析失败返回 None

    Example:
        >>> plain_str = '2025-11-28 16:57:25 INFO apps.accounts.services 用户登录成功 [admin|1|127.0.0.1|/api/accounts/auth/login/]'
        >>> parse_plain(plain_str)
        {'timestamp': '2025-11-28 16:57:25', 'level': 'INFO', ...}
    """
    try:
        # 正则表达式匹配 PLAIN 格式
        # 格式：timestamp level logger message [context]
        pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(\S+)\s+(.+?)\s+\[(.+?)\]$'
        match = re.match(pattern, plain_str.strip())

        if not match:
            # 尝试匹配不带上下文的格式
            pattern_no_context = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(\S+)\s+(.+)$'
            match = re.match(pattern_no_context, plain_str.strip())
            if not match:
                return None

            timestamp, level, logger, message = match.groups()
            context = None
        else:
            timestamp, level, logger, message, context = match.groups()

        # 构建日志字典
        log_dict = {
            'timestamp': timestamp,
            'level': level,
            'logger': logger,
            'message': message.strip(),
        }

        # 解析上下文信息
        if context:
            context_parts = context.split('|')
            if len(context_parts) >= 4:
                username = context_parts[0] if context_parts[0] != '-' else None
                account_id_str = context_parts[1]
                account_id = int(account_id_str) if account_id_str != '-' and account_id_str.isdigit() else None
                ip_address = context_parts[2] if context_parts[2] != '-' else None
                request_path = context_parts[3] if context_parts[3] != '-' else None

                if username:
                    log_dict['username'] = username
                if account_id is not None:
                    log_dict['account_id'] = account_id
                if ip_address:
                    log_dict['ip_address'] = ip_address
                if request_path:
                    log_dict['request_path'] = request_path

        return log_dict
    except (ValueError, IndexError):
        return None


def detect_format(line: str) -> Optional[str]:
    """
    检测日志行的格式

    Args:
        line: 日志字符串

    Returns:
        'json' | 'plain' | None（无法识别）

    Example:
        >>> detect_format('{"timestamp":"2025-11-28 16:57:25",...}')
        'json'
        >>> detect_format('2025-11-28 16:57:25 INFO ...')
        'plain'
    """
    line = line.strip()

    if not line:
        return None

    # JSON 格式：以 { 开头
    if line.startswith('{'):
        try:
            json.loads(line)
            return 'json'
        except json.JSONDecodeError:
            return None

    # PLAIN 格式：符合时间戳格式
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line):
        return 'plain'

    return None


def format_message_summary(message: str, max_length: int = 150) -> str:
    """
    智能格式化日志消息摘要

    处理不同类型的日志内容：
    1. 错误堆栈：提取最后一行错误信息
    2. JSON 日志：提取 message 字段
    3. 普通文本：去除换行和多余空格，截断

    Args:
        message: 原始日志消息
        max_length: 最大长度，默认 150 字符

    Returns:
        格式化后的消息摘要

    Example:
        >>> format_message_summary('Traceback...\\nAttributeError: xxx')
        "AttributeError: xxx"
        >>> format_message_summary('{"message": "用户登录成功", ...}')
        "用户登录成功"
        >>> format_message_summary('很长很长的消息...')
        "很长很长的消息...（截断）"
    """
    # 1. 检测是否为错误堆栈
    if 'Traceback (most recent call last)' in message:
        # 提取最后一行（通常是错误类型和消息）
        lines = message.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith(' ') and ':' in line:
                return line[:max_length]
        # 如果没有找到错误行，返回最后一行
        if lines:
            return lines[-1].strip()[:max_length]

    # 2. 检测是否为 JSON 格式
    if message.strip().startswith('{'):
        try:
            data = json.loads(message)
            if isinstance(data, dict) and 'message' in data:
                return str(data['message'])[:max_length]
        except json.JSONDecodeError:
            pass

    # 3. 普通文本：去除换行、多余空格、截断
    cleaned = ' '.join(message.split())  # 去除所有换行和多余空格
    if len(cleaned) > max_length:
        return cleaned[:max_length] + '...'
    return cleaned
