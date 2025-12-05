# -*- coding: utf-8 -*-
"""
WebSocket 事件规范（供前后端对齐）：
- 列出主要事件、必选字段、可选字段与说明，避免魔法字符串
- 如需新增事件，请在此处补充，保持中文说明
"""

from __future__ import annotations

EVENT_SCHEMAS: list[dict] = [
    {
        "event": "scoreboard_updated",
        "required": ["contest", "updated_at"],
        "optional": ["seq"],
        "desc": "记分板数据有更新，前端可触发刷新或等待 snapshot",
    },
    {
        "event": "scoreboard_snapshot",
        "required": ["contest", "entries"],
        "optional": ["top_limit", "generated_at", "ignore_freeze", "seq"],
        "desc": "推送榜单前 N 名片段，减少前端额外拉取",
    },
    {
        "event": "submission_accepted",
        "required": ["contest", "challenge", "awarded_points"],
        "optional": ["bonus_points", "blood_rank", "team_id", "seq"],
        "desc": "选手提交正确后的个人通知",
    },
    {
        "event": "first_blood",
        "required": ["contest", "challenge", "user_id"],
        "optional": ["team_id", "seq"],
        "desc": "首血广播",
    },
    {
        "event": "announcement_published",
        "required": ["contest", "announcement_id", "title"],
        "optional": ["seq"],
        "desc": "比赛公告发布",
    },
    {
        "event": "challenge_created",
        "required": ["contest", "challenge", "data"],
        "optional": ["seq"],
        "desc": "题目创建/上线，data 为题目简要信息",
    },
    {
        "event": "challenge_updated",
        "required": ["contest", "challenge", "data"],
        "optional": ["operator_id", "seq"],
        "desc": "题目更新（分值/状态/内容），data 为题目简要信息",
    },
    {
        "event": "hint_unlocked",
        "required": ["contest", "challenge", "hint_id"],
        "optional": ["user_id", "team_id", "cost", "hint", "seq"],
        "desc": "提示被解锁，个人组包含完整提示，比赛组仅附简要信息",
    },
    {
        "event": "team_created",
        "required": ["contest", "team", "team_id", "member_count", "member"],
        "optional": ["seq"],
        "desc": "队伍创建，附带成员快照（截断）",
    },
    {
        "event": "team_joined",
        "required": ["contest", "team", "team_id", "user_id", "member_count", "member"],
        "optional": ["members", "has_more_members", "seq"],
        "desc": "加入队伍，含加入成员信息与成员快照",
    },
    {
        "event": "team_left",
        "required": ["contest", "team", "team_id", "user_id", "member_count", "member"],
        "optional": ["members", "has_more_members", "seq"],
        "desc": "退出队伍，含退出成员信息与成员快照",
    },
    {
        "event": "team_disbanded",
        "required": ["contest", "team", "team_id"],
        "optional": ["members", "member_count", "seq"],
        "desc": "队伍解散，附带成员列表（截断）",
    },
    {
        "event": "team_invite_reset",
        "required": ["contest", "team", "team_id", "invite_token"],
        "optional": ["member_count", "seq"],
        "desc": "队伍邀请码重置",
    },
    {
        "event": "team_transferred",
        "required": ["contest", "team", "team_id", "old_captain", "new_captain"],
        "optional": ["members", "member_count", "member", "seq"],
        "desc": "队长移交",
    },
    {
        "event": "machine_started",
        "required": ["contest", "challenge", "machine_id", "port", "status"],
        "optional": ["user_id", "team_id", "host", "heartbeat_at", "seq"],
        "desc": "靶机启动成功",
    },
    {
        "event": "machine_stopped",
        "required": ["contest", "challenge", "machine_id", "status"],
        "optional": ["user_id", "team_id", "port", "host", "heartbeat_at", "seq"],
        "desc": "靶机停止/销毁",
    },
    {
        "event": "machine_failed",
        "required": ["contest", "challenge", "port", "status"],
        "optional": ["heartbeat_at", "seq"],
        "desc": "靶机启动失败广播（不含用户信息）",
    },
    {
        "event": "machine_status",
        "required": ["contest", "challenge", "machine_id", "status"],
        "optional": ["user_id", "team_id", "port", "host", "heartbeat_at", "reason", "seq"],
        "desc": "靶机状态心跳/变更",
    },
    {
        "event": "force_logout",
        "required": ["reason"],
        "optional": ["seq"],
        "desc": "后台封禁/权限变更强制下线，前端应断开并跳转登录",
    },
]

