from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.base.base_service import BaseService
from apps.common.exceptions import WrongFlagError, ChallengeAlreadySolvedError, ValidationError, ChallengeNotAvailableError
from apps.accounts.models import User
from apps.challenges.models import ChallengeSolve
from apps.challenges.repo import ChallengeRepo, ChallengeSolveRepo, ChallengeHintRepo
from apps.contests.services import ContestContextService, ScoreboardService
from apps.contests.repo import TeamMemberRepo
from apps.common.infra import redis_client
from apps.common.utils.redis_keys import blood_rank_key, scoreboard_key

from .models import Submission
from .repo import SubmissionRepo
from .schemas import SubmissionCreateSchema

# 服务层：处理提交记录、判题与解题日志写入。


def serialize_submission(submission: Submission) -> dict:
    """提交记录序列化：返回判题状态、得分与关联实体。"""
    return {
        "id": submission.id,
        "contest": submission.contest.slug,
        "challenge": submission.challenge.slug,
        "user": submission.user_id,
        "team": submission.team_id,
        "status": submission.status,
        "is_correct": submission.is_correct,
        "awarded_points": submission.awarded_points,
        "blood_rank": submission.blood_rank,
        "message": submission.message,
        "solve_id": submission.solve_id,
        "created_at": submission.created_at,
        "judged_at": submission.judged_at,
    }


class SubmissionService(BaseService[Submission]):
    """
    Flag 提交服务：
    - 校验比赛状态与题目开放性。
    - 统一使用 Challenge.check_flag 判题，支持动态 Flag 与前缀。
    - 采用动态计分与提示扣分，记录血次序，正确则写入解题记录。
    - 重复正确提交记为重复并抛出业务错误；错误也会记录提交。
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
    ):
        self.contest_service = contest_service or ContestContextService()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.solve_repo = solve_repo or ChallengeSolveRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.hint_repo = hint_repo or ChallengeHintRepo()
        self.submission_repo = submission_repo or SubmissionRepo()

    def perform(self, user: User, schema: SubmissionCreateSchema) -> Submission:
        # 1) 获取比赛与题目，并校验比赛进行中
        contest = self.contest_service.get_contest(schema.contest_slug)
        self.contest_service.ensure_contest_running(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=schema.challenge_slug)
        if not challenge.is_active:
            raise ChallengeNotAvailableError(message="题目未开放")

        # 2) 获取队伍关系与是否已解出
        membership = self.member_repo.get_membership(contest=contest, user=user)
        existing_solve = self.solve_repo.get_user_solve(challenge=challenge, user=user)

        # 3) 若已解出，再次提交记为重复并抛出业务错误
        if existing_solve:
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
            raise ChallengeAlreadySolvedError(message="你已经解出该题目")

        # 4) 判题：统一使用 Challenge.check_flag
        secret = getattr(settings, "SECRET_KEY", "ftc-dynamic-flag")
        is_correct = challenge.check_flag(
            schema.flag,
            user=user,
            membership=membership,
            secret=secret,
        )

        # 5) 错误提交：记录后抛出错误
        if not is_correct:
            status = Submission.Status.REJECTED
            message = "Flag 不正确"
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
            raise WrongFlagError(message="提交内容不正确")

        # 6) 正确提交：动态计分 + 提示扣分 + 血次序
        awarded_points = self._calc_dynamic_points(challenge, contest, membership)
        hint_cost = self._calc_hint_cost(challenge, user)
        awarded_points = max(0, awarded_points - hint_cost)
        blood_rank = self._next_blood_rank(challenge)
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
                    "judged_at": timezone.now(),
                }
            )
        solve = self.solve_repo.create(
            {
                "challenge": challenge,
                "user": user,
                "team": membership.team if membership else None,
                "awarded_points": awarded_points,
            }
        )
        submission.solve = solve
        submission.save(update_fields=["solve"])
        self._invalidate_scoreboard_cache(contest.id)
        return submission

    def visible_points_for_user(self, user: User | None, contest, challenge, membership=None) -> int:
        """
        计算选手当前可获得分值：动态计分基础上扣除已解锁提示。
        - 未登录用户视为无提示扣分。
        """
        if membership is None and user is not None and getattr(user, "is_authenticated", False):
            membership = self.member_repo.get_membership(contest=contest, user=user)
        awarded_points = self._calc_dynamic_points(challenge, contest, membership)
        hint_cost = 0
        if user is not None and getattr(user, "is_authenticated", False):
            hint_cost = self._calc_hint_cost(challenge, user)
        return max(0, awarded_points - hint_cost)

    def _next_blood_rank(self, challenge) -> int:
        """
        使用 redis 计数器获取血次序，降低并发冲突。
        """
        key = blood_rank_key(challenge.id)
        try:
            # 设置短期过期，防止长期堆积（默认 30 天，可视需求调整）
            rank = redis_client.incr(key, amount=1, ex=60 * 60 * 24 * 30)
            return rank
        except Exception:
            current_solved = self.solve_repo.filter(challenge=challenge).count()
            return current_solved + 1

    def _invalidate_scoreboard_cache(self, contest_id: int) -> None:
        """正确提交后清理对应比赛的记分板缓存。"""
        try:
            ScoreboardService.invalidate_cache(contest_id)
        except Exception:
            redis_client.delete(scoreboard_key(contest_id))

    def _calc_hint_cost(self, challenge, user: User) -> int:
        """提示扣分：若仓储支持 cost_for_solver 则使用，否则为 0。"""
        if hasattr(self.hint_repo, "cost_for_solver"):
            try:
                return int(self.hint_repo.cost_for_solver(challenge=challenge, user=user))  # type: ignore[attr-defined]
            except Exception:
                return 0
        return 0

    def _calc_dynamic_points(self, challenge, contest, membership) -> int:
        """
        根据计分模式计算得分：
        - 固定模式：直接 base_points。
        - 动态模式：按队伍/个人解题数衰减，最低分不低于 min_score。
        """
        if challenge.scoring_mode == challenge.ScoringMode.FIXED:
            return challenge.base_points

        # 按团队/个人计算已解出数量
        if contest.is_team_based:
            solved_count = (
                ChallengeSolve.objects.filter(challenge=challenge)
                .exclude(team_id=None)
                .values("team_id")
                .distinct()
                .count()
            )
        else:
            solved_count = (
                ChallengeSolve.objects.filter(challenge=challenge)
                .values("user_id")
                .distinct()
                .count()
            )

        if challenge.decay_type == challenge.DecayType.PERCENTAGE:
            score = challenge.base_points * (challenge.decay_factor ** solved_count)
        else:
            score = challenge.base_points - challenge.decay_factor * solved_count

        score_int = int(round(score))
        return max(challenge.min_score, score_int)
