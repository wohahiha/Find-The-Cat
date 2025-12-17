from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.base.base_service import BaseService
from apps.common.exceptions import (
    WrongFlagError,
    ChallengeAlreadySolvedError,
    ChallengeNotAvailableError,
    ValidationError,
)
from apps.accounts.models import User
from apps.challenges.models import ChallengeSolve
from apps.challenges.repo import (
    ChallengeRepo,
    ChallengeSolveRepo,
    ChallengeHintRepo,
    ChallengeHintUnlockRepo,
)
from apps.contests.services import ContestContextService, ScoreboardService
from apps.contests.repo import TeamMemberRepo
from apps.common.infra import redis_client
from apps.common.utils.redis_keys import blood_rank_key, scoreboard_key
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.ws_utils import broadcast_notify, broadcast_contest, allow_broadcast
from apps.system.services import ConfigService
from apps.common.security import get_flag_secret

from .models import Submission
from .repo import SubmissionRepo
from .schemas import SubmissionCreateSchema

# 服务层：处理提交记录、判题与解题日志写入

logger = get_logger(__name__)


def serialize_submission(submission: Submission) -> dict:
    """提交记录序列化：返回判题状态、得分与关联实体"""
    submission_id = getattr(submission, "id", None)
    contest_slug = getattr(getattr(submission, "contest", None), "slug", None)
    challenge_slug = getattr(getattr(submission, "challenge", None), "slug", None)
    return {
        "id": submission_id,
        "contest": contest_slug,
        "challenge": challenge_slug,
        "user": getattr(submission, "user_id", None),
        "team": getattr(submission, "team_id", None),
        "status": submission.status,
        "is_correct": submission.is_correct,
        "awarded_points": getattr(submission, "awarded_points", 0),
        "bonus_points": getattr(submission, "bonus_points", 0),
        "blood_rank": getattr(submission, "blood_rank", 0),
        "message": submission.message,
        "solve_id": getattr(submission, "solve_id", None),
        "created_at": submission.created_at,
        "judged_at": submission.judged_at,
    }


class SubmissionService(BaseService[Submission]):
    """
    Flag 提交服务：
    - 校验比赛状态与题目开放性
    - 统一使用 Challenge.check_flag 判题，支持动态 Flag 与前缀
    - 采用动态计分与提示扣分，记录血次序，正确则写入解题记录
    - 重复正确提交记为重复并抛出业务错误；错误也会记录提交
    """
    atomic_enabled = False  # 自行控制事务，确保错误提交也能落库记录

    def __init__(
            self,
            contest_service: ContestContextService | None = None,
            challenge_repo: ChallengeRepo | None = None,
            solve_repo: ChallengeSolveRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
            hint_repo: ChallengeHintRepo | None = None,
            submission_repo: SubmissionRepo | None = None,
            scoreboard_service: ScoreboardService | None = None,
    ):
        """注入依赖仓储与上下文服务，便于测试时替换实现"""
        self.contest_service = contest_service or ContestContextService()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.solve_repo = solve_repo or ChallengeSolveRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        # 提示扣分需读取解锁记录，默认使用 ChallengeHintUnlockRepo 以便统计成本
        self.hint_repo = hint_repo or ChallengeHintUnlockRepo()
        self.submission_repo = submission_repo or SubmissionRepo()
        self.scoreboard_service = scoreboard_service or ScoreboardService()

    def perform(self, user: User, schema: SubmissionCreateSchema) -> Submission:
        """处理一次 Flag 提交，返回提交记录；正确会新增解题并刷新榜单"""
        # 1) 获取比赛与题目，并校验比赛进行中
        contest = self.contest_service.get_contest(schema.contest_slug)
        self.contest_service.ensure_contest_running(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=schema.challenge_slug)
        if not challenge.is_active:
            raise ChallengeNotAvailableError(message="题目未开放")

        # 2) 获取队伍关系与是否已解出
        membership = self.member_repo.get_membership(contest=contest, user=user)
        if contest.is_team_based and membership is None:
            raise ValidationError(message="该比赛为团队赛，请先加入队伍再提交")
        existing_solve = self.solve_repo.get_user_solve_with_related(challenge=challenge, user=user)

        # 3) 若已解出，再次提交记为重复并抛出业务错误
        if existing_solve:
            # 重复提交也记录，便于审计与风控
            submission = self.submission_repo.create(
                {
                    "contest": contest,
                    "challenge": challenge,
                    "user": user,
                    "team": membership.team if membership else None,
                    "flag_submitted": schema.flag,
                    "status": Submission.Status.DUPLICATE,
                    "is_correct": False,
                    "blood_rank": 0,
                    "message": "你已经解出该题目",
                    "awarded_points": 0,
                }
            )
            logger.info(
                "判题-重复提交",
                extra=logger_extra(
                    {
                        "submission_id": getattr(submission, "id", None),
                        "contest": getattr(contest, "slug", None),
                        "challenge": getattr(challenge, "slug", None),
                        "user_id": getattr(user, "id", None),
                        "team_id": getattr(membership, "team_id", None),
                    }
                ),
            )
            raise ChallengeAlreadySolvedError(message="你已经解出该题目")

        # 4) 判题：统一使用 Challenge.check_flag
        secret = get_flag_secret()
        is_correct = challenge.check_flag(
            schema.flag,
            user=user,
            membership=membership,
            secret=secret,
        )

        # 5) 错误提交：记录后抛出错误
        if not is_correct:
            status = Submission.Status.REJECTED
            # 错误提交也落库，方便后续分析与安全审计
            submission = self.submission_repo.create(
                {
                    "contest": contest,
                    "challenge": challenge,
                    "user": user,
                    "team": membership.team if membership else None,
                    "flag_submitted": schema.flag,
                    "status": status,
                    "is_correct": False,
                    "blood_rank": 0,
                    "message": "提交内容不正确",
                    "awarded_points": 0,
                }
            )
            logger.info(
                "判题-错误提交",
                extra=logger_extra(
                    {
                        "submission_id": getattr(submission, "id", None),
                        "contest": getattr(contest, "slug", None),
                        "challenge": getattr(challenge, "slug", None),
                        "user_id": getattr(user, "id", None),
                        "team_id": getattr(membership, "team_id", None),
                        "flag_length": len(schema.flag) if schema.flag else 0,
                    }
                ),
            )
            raise WrongFlagError(message="提交内容不正确")

        # 6) 正确提交：动态计分 + 提示扣分 + 血次序 + n 血奖励
        blood_rank = self._next_blood_rank(challenge)
        solved_count = self._solved_count(challenge, contest)
        base_points = self._calc_dynamic_points(challenge, solved_count)
        base_override, bonus_points = self._apply_blood_reward(
            challenge, blood_rank, include_bonus=True
        )
        if base_override is not None:
            base_points = base_override
        hint_cost = self._calc_hint_cost(challenge, user, membership)
        awarded_points = max(0, base_points - hint_cost) + bonus_points
        expected_flag = challenge.build_expected_flag(user=user, membership=membership, secret=secret)

        # 7) 事务内写入提交记录与解题记录
        with transaction.atomic():
            submission = self.submission_repo.create(
                {
                    "contest": contest,
                    "challenge": challenge,
                    "user": user,
                    "team": membership.team if membership else None,
                    "flag_submitted": expected_flag if challenge.flag_type == challenge.FlagType.DYNAMIC else schema.flag,
                    "status": Submission.Status.ACCEPTED,
                    "is_correct": True,
                    "blood_rank": blood_rank,
                    "message": "提交正确",
                    "awarded_points": awarded_points,
                    "bonus_points": bonus_points,
                    "judged_at": timezone.now(),
                }
            )
        solve = self.solve_repo.create(
            {
                "challenge": challenge,
                "user": user,
                "team": membership.team if membership else None,
                "awarded_points": awarded_points,
                "bonus_points": bonus_points,
            }
        )
        submission.solve = solve
        submission.save(update_fields=["solve"])
        # 记分板快照失效，后续重新计算
        self._invalidate_scoreboard_cache(contest.id)
        cfg_service = ConfigService()
        snapshot_limit = int(cfg_service.get("SCOREBOARD_PUSH_TOP", getattr(settings, "SCOREBOARD_PUSH_TOP", 10)) or 10)
        snapshot_payload: dict = {}
        try:
            snapshot_payload = self.scoreboard_service.build_snapshot(contest, limit=snapshot_limit)
        except Exception:
            # 榜单推送失败不阻断判题流程
            snapshot_payload = {}
        # WebSocket 通知：记分板与分数更新（附带榜单片段）
        broadcast_contest(
            getattr(contest, "slug", None),
            {
                "event": "scoreboard_updated",
                "contest": getattr(contest, "slug", None),
                "updated_at": timezone.now().isoformat(),
            },
        )
        interval_seconds = int(
            cfg_service.get(
                "SCOREBOARD_PUSH_INTERVAL_SECONDS",
                getattr(settings, "SCOREBOARD_PUSH_INTERVAL_SECONDS", 3),
            )
            or 3
        )
        if snapshot_payload.get("entries") is not None and allow_broadcast(
                f"scoreboard_snapshot:{getattr(contest, 'slug', '')}",
                interval_seconds=interval_seconds,
        ):
            broadcast_contest(
                getattr(contest, "slug", None),
                {
                    "event": "scoreboard_snapshot",
                    **snapshot_payload,
                },
            )
        broadcast_notify(
            getattr(user, "id", None),
            {
                "event": "submission_accepted",
                "contest": getattr(contest, "slug", None),
                "challenge": getattr(challenge, "slug", None),
                "awarded_points": awarded_points,
                "bonus_points": bonus_points,
                "blood_rank": blood_rank,
                "team_id": getattr(membership, "team_id", None),
            },
        )
        if blood_rank == 1:
            broadcast_contest(
                getattr(contest, "slug", None),
                {
                    "event": "first_blood",
                    "contest": getattr(contest, "slug", None),
                    "challenge": getattr(challenge, "slug", None),
                    "user_id": getattr(user, "id", None),
                    "team_id": getattr(membership, "team_id", None),
                },
            )
        logger.info(
            "判题-正确提交",
            extra=logger_extra(
                {
                    "submission_id": getattr(submission, "id", None),
                    "contest": getattr(contest, "slug", None),
                    "challenge": getattr(challenge, "slug", None),
                    "user_id": getattr(user, "id", None),
                    "team_id": getattr(membership, "team_id", None),
                    "awarded_points": awarded_points,
                    "blood_rank": blood_rank,
                    "bonus_points": bonus_points,
                    "hint_cost": hint_cost,
                }
            ),
        )
        return submission

    def visible_points_for_user(self, user: User | None, contest, challenge, membership=None) -> int:
        """
        计算选手当前可获得分值：动态计分基础上扣除已解锁提示
        - 未登录用户视为无提示扣分
        """
        # 若未传 membership，尝试在已登录上下文下查队伍关系
        if membership is None and user is not None and getattr(user, "is_authenticated", False):
            membership = self.member_repo.get_membership(contest=contest, user=user)
        solved_count = self._solved_count(challenge, contest)
        predicted_rank = solved_count + 1
        base_points = self._calc_dynamic_points(challenge, solved_count)
        base_override, _ = self._apply_blood_reward(
            challenge, predicted_rank, include_bonus=False
        )
        if base_override is not None:
            base_points = base_override
        hint_cost = 0
        if user is not None and getattr(user, "is_authenticated", False):
            hint_cost = self._calc_hint_cost(challenge, user, membership)
        return max(0, base_points - hint_cost)

    @staticmethod
    def _next_blood_rank(challenge) -> int:
        """
        使用 redis 计数器获取血次序，降低并发冲突
        """
        key = blood_rank_key(challenge.id)
        try:
            # 设置短期过期，防止长期堆积（默认 30 天，可视需求调整）
            rank = redis_client.incr(key, amount=1, ex=60 * 60 * 24 * 30)
            return rank
        except Exception:
            # 回退到数据库计数，避免缓存异常导致阻断
            current_solved = ChallengeSolve.objects.filter(challenge=challenge).count()
            return current_solved + 1

    @staticmethod
    def _invalidate_scoreboard_cache(contest_id: int) -> None:
        """正确提交后清理对应比赛的记分板缓存"""
        try:
            ScoreboardService.invalidate_cache(contest_id)
        except Exception:
            # 缓存不可用时退化为直接删除 key，保证榜单可重新生成
            redis_client.delete(scoreboard_key(contest_id))

    def _calc_hint_cost(self, challenge, user: User, membership=None) -> int:
        """提示扣分：若仓储支持 cost_for_solver 则使用，否则为 0"""
        if hasattr(self.hint_repo, "cost_for_solver"):
            try:
                team = getattr(membership, "team", None) if membership else None
                return int(self.hint_repo.cost_for_solver(
                    challenge=challenge,
                    user=user,
                    team=team,
                ))  # type: ignore[attr-defined]
            except Exception:
                return 0
        return 0

    @staticmethod
    def _solved_count(challenge, contest) -> int:
        """
        统计当前题目已解出的数量：
        - 组队赛按队伍去重
        - 个人赛按用户去重
        """
        if contest.is_team_based:
            return (
                ChallengeSolve.objects.filter(challenge=challenge)
                .exclude(team_id=None)
                .values("team_id")
                .distinct()
                .count()
            )
        return (
            ChallengeSolve.objects.filter(challenge=challenge)
            .values("user_id")
            .distinct()
            .count()
        )

    @staticmethod
    def _apply_blood_reward(challenge, blood_rank: int | None, *, include_bonus: bool) -> tuple[int | None, int]:
        """
        n 血奖励处理：
        - 返回 base_points 覆盖值（用于不衰减）与额外加分
        - include_bonus=False 时，仅处理不衰减，不计算加分
        """
        if not blood_rank or blood_rank <= 0:
            return None, 0
        reward_type = getattr(challenge, "blood_reward_type", None)
        reward_count = int(getattr(challenge, "blood_reward_count", 0) or 0)
        if reward_type in (None, challenge.BloodRewardType.NONE) or reward_count <= 0:
            return None, 0
        # 不衰减：仅动态分值生效
        if (
                reward_type == challenge.BloodRewardType.NO_DECAY
                and challenge.scoring_mode == challenge.ScoringMode.DYNAMIC
                and blood_rank <= reward_count
        ):
            return challenge.base_points, 0
        # 加分模式
        if include_bonus and reward_type == challenge.BloodRewardType.BONUS and blood_rank <= reward_count:
            bonuses = list(getattr(challenge, "blood_bonus_points", []) or [])
            try:
                bonus_points = int(bonuses[blood_rank - 1])
            except Exception:
                bonus_points = 0
            return None, max(0, bonus_points)
        return None, 0

    @staticmethod
    def _calc_dynamic_points(challenge, solved_count: int) -> int:
        """
        根据计分模式计算得分：
        - 固定模式：直接 base_points
        - 动态模式：按队伍/个人解题数衰减，最低分不低于 min_score
        """
        if challenge.scoring_mode == challenge.ScoringMode.FIXED:
            return challenge.base_points

        if challenge.decay_type == challenge.DecayType.PERCENTAGE:
            score = challenge.base_points * (challenge.decay_factor ** solved_count)
        else:
            score = challenge.base_points - challenge.decay_factor * solved_count

        score_int = int(round(score))
        return max(challenge.min_score, score_int)
