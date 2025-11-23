from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.common.base.base_service import BaseService
from apps.common.exceptions import WrongFlagError, ChallengeAlreadySolvedError, ValidationError, ChallengeNotAvailableError
from apps.accounts.models import User
from apps.challenges.models import ChallengeSolve
from apps.challenges.repo import ChallengeRepo, ChallengeSolveRepo
from apps.machines.repo import MachineRepo
from apps.common.infra import redis_client
from apps.contests.services import ContestContextService
from apps.contests.repo import TeamMemberRepo

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
    - 校验比赛状态与题目可用性。
    - 判题并记录 Submission；首次正确则写入 ChallengeSolve。
    - 重复正确提交记录为重复状态并抛出业务错误。
    """
    atomic_enabled = False  # 自行控制事务，确保错误提交也能落库记录

    def __init__(
        self,
        contest_service: ContestContextService | None = None,
        challenge_repo: ChallengeRepo | None = None,
        solve_repo: ChallengeSolveRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
        submission_repo: SubmissionRepo | None = None,
    ):
        self.contest_service = contest_service or ContestContextService()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.solve_repo = solve_repo or ChallengeSolveRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.submission_repo = submission_repo or SubmissionRepo()
        self.machine_repo = MachineRepo()

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

        # 3) 判题
        # 动态 flag：需匹配用户运行实例的动态 flag；否则使用题目校验
        if challenge.flag_type == challenge.FlagType.DYNAMIC:
            instance = self.machine_repo.running_for_user(contest=contest, challenge=challenge, user=user)
            if not instance or not instance.dynamic_flag:
                raise ValidationError(message="请先启动靶机后再提交动态 Flag")
            is_correct = schema.flag.strip() == instance.dynamic_flag
            dynamic_flag_used = instance.dynamic_flag
        else:
            is_correct = challenge.check_flag(schema.flag)
            dynamic_flag_used = ""
        status = Submission.Status.ACCEPTED if is_correct else Submission.Status.REJECTED
        message = "Flag 正确" if is_correct else "Flag 不正确"
        awarded_points = challenge.base_points if is_correct else 0
        # 记录当前血次序：正确提交前统计
        blood_rank = 0
        if is_correct:
            blood_rank = self._next_blood_rank(challenge)

        # 4) 若已解出，再次提交记为重复并抛出业务错误
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

        # 5) 错误提交：记录后抛出错误
        if not is_correct:
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
                    "message": message,
                    "awarded_points": 0,
                }
            )
            raise WrongFlagError(message="Flag 不正确")

        # 6) 正确提交：事务内写入提交记录与解题记录
        with transaction.atomic():
            submission = self.submission_repo.create(
                {
                    "contest": contest,
                    "challenge": challenge,
                    "user": user,
                    "team": membership.team if membership else None,
                    "flag_submitted": dynamic_flag_used or schema.flag,
                    "status": status,
                    "is_correct": True,
                    "blood_rank": blood_rank,
                    "message": message,
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
        return submission

    def _next_blood_rank(self, challenge) -> int:
        """
        使用 redis 计数器获取血次序，降低并发冲突。
        """
        key = f"challenge:{challenge.id}:blood_rank"
        try:
            # 设置短期过期，防止长期堆积（默认 30 天，可视需求调整）
            rank = redis_client.incr(key, amount=1, ex=60 * 60 * 24 * 30)
            return rank
        except Exception:
            current_solved = self.solve_repo.filter(challenge=challenge).count()
            return current_solved + 1
