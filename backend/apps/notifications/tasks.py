from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import User
from apps.contests.models import Contest, ContestParticipant
from apps.contests.repo import ContestRepo, ContestParticipantRepo, TeamMemberRepo, TeamRepo
from apps.notifications.models import Notification
from apps.notifications.services import fanout_notifications, build_dedup_key


def _notify_participants(contest, *, type: str, title: str, body: str, bucket: str) -> None:
    """对有效报名选手推送通知"""
    participant_repo = ContestParticipantRepo()
    participants = list(participant_repo.filter(contest=contest, is_valid=True).select_related("user"))
    if not participants:
        return
    users = [p.user for p in participants if getattr(p, "user", None)]
    dedup = build_dedup_key(type=type, contest=contest, bucket=bucket)
    fanout_notifications(
        users,
        type=type,
        title=title,
        body=body,
        payload={"contest": contest.slug},
        contest=contest,
        dedup_key=dedup,
    )


def _notify_all_active_users(*, type: str, title: str, body: str, bucket: str, payload: dict | None = None) -> None:
    """向所有活跃非管理员用户广播通知（适用于公开广播类事件）"""
    users = list(User.objects.filter(is_active=True, is_staff=False))
    if not users:
        return
    dedup = build_dedup_key(type=type, bucket=bucket)
    fanout_notifications(
        users,
        type=type,
        title=title,
        body=body,
        payload=payload or {},
        dedup_key=dedup,
    )


@shared_task(name="notifications.scan_contests")
def scan_contests_for_notifications():
    """周期扫描比赛时间窗口，生成系统提醒"""
    now = timezone.now()
    repo = ContestRepo()
    # 配置提前量（秒）
    start_soon_delta = int(getattr(settings, "NOTIFY_CONTEST_START_SOON_SECONDS", 3600))
    freeze_soon_delta = int(getattr(settings, "NOTIFY_CONTEST_FREEZE_SOON_SECONDS", 900))
    reg_deadline_delta = int(getattr(settings, "NOTIFY_CONTEST_REG_DEADLINE_SOON_SECONDS", 3600))
    ending_soon_delta = int(getattr(settings, "NOTIFY_CONTEST_ENDING_SOON_SECONDS", 1800))
    roster_min_members = int(getattr(settings, "NOTIFY_TEAM_MIN_MEMBERS", 2))

    contests = repo.filter()  # 过滤全部比赛，后续按时间窗口筛选
    for contest in contests:
        slug = getattr(contest, "slug", "")
        # 报名开启（公开广播）
        reg_start = getattr(contest, "registration_start_time", None)
        if reg_start and reg_start <= now <= reg_start + timedelta(minutes=5):
            _notify_all_active_users(
                type=Notification.Type.CONTEST_REG_OPEN,
                title=f"{contest.name} 报名开启",
                body=f"报名截止：{getattr(contest, 'registration_end_time', '') or contest.start_time}",
                bucket=f"{slug}-reg-open",
                payload={"contest": contest.slug},
            )
        # 开赛前提醒
        if contest.start_time and now <= contest.start_time <= now + timedelta(seconds=start_soon_delta):
            bucket = contest.start_time.isoformat(timespec="minutes")
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_UPCOMING,
                title=f"{contest.name} 即将开赛",
                body=f"开赛时间：{contest.start_time}",
                bucket=bucket,
            )
        # 比赛开始
        if contest.start_time and contest.start_time <= now <= contest.start_time + timedelta(minutes=5):
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_STARTED,
                title=f"{contest.name} 已开赛",
                body=f"比赛已开始，结束时间：{contest.end_time}",
                bucket="started",
            )
        # 封榜前提醒
        if contest.freeze_time and now <= contest.freeze_time <= now + timedelta(seconds=freeze_soon_delta):
            bucket = contest.freeze_time.isoformat(timespec="minutes")
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_FREEZE_SOON,
                title=f"{contest.name} 即将封榜",
                body=f"封榜时间：{contest.freeze_time}",
                bucket=bucket,
            )
        # 封榜生效
        if contest.freeze_time and contest.freeze_time <= now <= contest.freeze_time + timedelta(minutes=5):
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_FREEZE,
                title=f"{contest.name} 榜单已冻结",
                body="封榜后提交仍可判题，榜单解冻后更新",
                bucket="freeze",
            )
        # 报名截止前提醒
        reg_end = getattr(contest, "registration_end_time", None)
        if reg_end and now <= reg_end <= now + timedelta(seconds=reg_deadline_delta):
            bucket = reg_end.isoformat(timespec="minutes")
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_REG_DEADLINE_SOON,
                title=f"{contest.name} 报名即将截止",
                body=f"报名截止：{reg_end}",
                bucket=bucket,
            )
            # 队伍人数预警（团队赛）
            if contest.is_team_based:
                _notify_roster_warning(contest, bucket=bucket, min_members=roster_min_members)
        # 比赛结束前提醒
        if contest.end_time and now <= contest.end_time <= now + timedelta(seconds=ending_soon_delta):
            bucket = contest.end_time.isoformat(timespec="minutes")
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_ENDING_SOON,
                title=f"{contest.name} 即将结束",
                body=f"结束时间：{contest.end_time}",
                bucket=bucket,
            )
        # 比赛结束
        if contest.end_time and contest.end_time <= now <= contest.end_time + timedelta(minutes=5):
            _notify_participants(
                contest,
                type=Notification.Type.CONTEST_ENDED,
                title=f"{contest.name} 已结束",
                body="感谢参赛，请关注榜单和成绩",
                bucket="ended",
            )
        # 报名失效/未组队处理
        if contest.is_team_based and reg_end and now >= reg_end:
            _invalidate_unteamed(contest)


def _invalidate_unteamed(contest: Contest):
    """报名已截止后，将未组队的报名标记失效并通知"""
    participant_repo = ContestParticipantRepo()
    member_repo = TeamMemberRepo()
    participants = list(
        participant_repo.filter(
            contest=contest,
            is_valid=True,
            status__in=[ContestParticipant.Status.REGISTERED, ContestParticipant.Status.RUNNING],
        ).select_related("user")
    )
    for p in participants:
        if member_repo.get_membership(contest=contest, user=p.user):
            continue
        p.is_valid = False
        p.save(update_fields=["is_valid"])
        dedup = build_dedup_key(
            type=Notification.Type.CONTEST_REG_INVALIDATED,
            contest=contest,
            bucket="invalidated",
            extra=str(getattr(p, "id", None)),
        )
        fanout_notifications(
            [p.user],
            type=Notification.Type.CONTEST_REG_INVALIDATED,
            title=f"{contest.name} 报名失效",
            body="未组队导致报名失效",
            payload={"contest": contest.slug},
            contest=contest,
            dedup_key=dedup,
        )


def _notify_roster_warning(contest: Contest, *, bucket: str, min_members: int) -> None:
    """队伍人数预警（未达最低人数或超出上限）"""
    team_repo = TeamRepo()
    member_repo = TeamMemberRepo()
    teams = team_repo.filter(contest=contest, is_active=True).select_related("contest")
    for team in teams:
        count = team.member_count
        warn = False
        reason = ""
        if count < min_members:
            warn = True
            reason = f"队伍人数不足（当前 {count} 人，至少 {min_members} 人）"
        elif count > contest.max_team_members:
            warn = True
            reason = f"队伍人数超限（当前 {count} 人，上限 {contest.max_team_members} 人）"
        if not warn:
            continue
        members = list(member_repo.active_members(team))
        if not members:
            continue
        dedup = build_dedup_key(
            type=Notification.Type.TEAM_ROSTER_WARNING,
            contest=contest,
            team=team,
            bucket=bucket,
        )
        fanout_notifications(
            [m.user for m in members if getattr(m, "user", None)],
            type=Notification.Type.TEAM_ROSTER_WARNING,
            title=reason,
            body=contest.name,
            payload={
                "contest": contest.slug,
                "team": team.slug,
                "team_id": getattr(team, "id", None),
                "member_count": count,
            },
            contest=contest,
            team=team,
            dedup_key=dedup,
        )
