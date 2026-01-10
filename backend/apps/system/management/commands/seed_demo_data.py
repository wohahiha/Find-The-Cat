from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.utils import assign_default_admin_permissions, assign_default_user_permissions
from apps.contests.models import (
    Contest,
    ContestAnnouncement,
    Team,
    TeamMember,
    ContestParticipant,
)
from apps.challenges.models import Challenge, ChallengeCategory, ChallengeHint
from apps.machines.models import ChallengeMachineConfig, MachineInstance
from apps.submissions.models import Submission
from apps.problem_bank.models import BankAttachment, BankCategory, BankChallenge, BankHint, ProblemBank


class Command(BaseCommand):
    help = "清空旧示例数据并创建一批完整的演示数据（用户/比赛/公告/题目/靶机/战队）"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("开始清理旧数据并创建演示数据..."))
        with transaction.atomic():
            self._cleanup()
            users = self._create_users()
            contests = self._create_contests(users)
            self._create_challenges_and_machines(contests, users)
            self._create_announcements(contests)
            self._create_teams_and_participants(contests, users)
            self._create_problem_banks(users)
        self.stdout.write(self.style.SUCCESS("演示数据已创建完成。"))
        self.stdout.write(self.style.WARNING("示例普通用户账号：player1@example.com / 密码：P@ssw0rd!"))

    def _cleanup(self):
        # 清理业务数据，保留超管账号
        MachineInstance.objects.all().delete()
        ChallengeMachineConfig.objects.all().delete()
        Submission.objects.all().delete()
        Challenge.objects.all().delete()
        ChallengeCategory.objects.all().delete()
        ContestAnnouncement.objects.all().delete()
        TeamMember.objects.all().delete()
        Team.objects.all().delete()
        ContestParticipant.objects.all().delete()
        Contest.objects.all().delete()
        BankChallenge.objects.all().delete()
        ProblemBank.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def _create_users(self):
        demo_users = [
            # 10 普通用户
            {"username": "player1", "email": "player1@example.com", "nickname": "Alice Chen", "password": "P@ssw0rd!", "organization": "Blue Hats", "country": "CN", "bio": "专注 Web 安全，常驻红队。", "avatar": "https://avatars.githubusercontent.com/u/1?v=4"},
            {"username": "player2", "email": "player2@example.com", "nickname": "Bob Li", "password": "P@ssw0rd!", "organization": "RedOps", "country": "SG", "bio": "喜欢 Pwn & Kernel，偶尔打比赛。", "avatar": "https://avatars.githubusercontent.com/u/2?v=4"},
            {"username": "player3", "email": "player3@example.com", "nickname": "Carol Wu", "password": "P@ssw0rd!", "organization": "0xLions", "country": "US", "bio": "逆向 & Crypto 爱好者。", "avatar": "https://avatars.githubusercontent.com/u/3?v=4"},
            {"username": "player4", "email": "player4@example.com", "nickname": "Dave Ho", "password": "P@ssw0rd!", "organization": "Team Shadows", "country": "JP", "bio": "全能型选手，常年陪练。", "avatar": "https://avatars.githubusercontent.com/u/4?v=4"},
            {"username": "player5", "email": "player5@example.com", "nickname": "Eve Zhang", "password": "P@ssw0rd!", "organization": "SkySec", "country": "DE", "bio": "热爱 Web & Misc。", "avatar": "https://avatars.githubusercontent.com/u/5?v=4"},
            {"username": "player6", "email": "player6@example.com", "nickname": "Frank Yu", "password": "P@ssw0rd!", "organization": "NightSec", "country": "AU", "bio": "做题刷榜两不误。", "avatar": "https://avatars.githubusercontent.com/u/6?v=4"},
            {"username": "player7", "email": "player7@example.com", "nickname": "Grace Lin", "password": "P@ssw0rd!", "organization": "ByteCats", "country": "FR", "bio": "喜欢 Misc 与取证。", "avatar": "https://avatars.githubusercontent.com/u/7?v=4"},
            {"username": "player8", "email": "player8@example.com", "nickname": "Henry Gao", "password": "P@ssw0rd!", "organization": "SecOps", "country": "BR", "bio": "Pwn 选手，爱打大型赛。", "avatar": "https://avatars.githubusercontent.com/u/8?v=4"},
            {"username": "player9", "email": "player9@example.com", "nickname": "Ivy Sun", "password": "P@ssw0rd!", "organization": "NullByte", "country": "CA", "bio": "Crypto 研究狗。", "avatar": "https://avatars.githubusercontent.com/u/9?v=4"},
            {"username": "player10", "email": "player10@example.com", "nickname": "Jack Ma", "password": "P@ssw0rd!", "organization": "Rooters", "country": "IN", "bio": "逆向/安卓安全。", "avatar": "https://avatars.githubusercontent.com/u/10?v=4"},
            # 5 管理员（非超管），用于不同比赛
            {"username": "admin1", "email": "admin1@example.com", "nickname": "Contest Admin 1", "password": "P@ssw0rd!", "organization": "FTC", "country": "CN", "bio": "赛事管理员", "avatar": "https://avatars.githubusercontent.com/u/11?v=4", "is_staff": True},
            {"username": "admin2", "email": "admin2@example.com", "nickname": "Contest Admin 2", "password": "P@ssw0rd!", "organization": "FTC", "country": "CN", "bio": "赛事管理员", "avatar": "https://avatars.githubusercontent.com/u/12?v=4", "is_staff": True},
            {"username": "admin3", "email": "admin3@example.com", "nickname": "Contest Admin 3", "password": "P@ssw0rd!", "organization": "FTC", "country": "CN", "bio": "赛事管理员", "avatar": "https://avatars.githubusercontent.com/u/13?v=4", "is_staff": True},
            {"username": "admin4", "email": "admin4@example.com", "nickname": "Contest Admin 4", "password": "P@ssw0rd!", "organization": "FTC", "country": "CN", "bio": "赛事管理员", "avatar": "https://avatars.githubusercontent.com/u/14?v=4", "is_staff": True},
            {"username": "admin5", "email": "admin5@example.com", "nickname": "Contest Admin 5", "password": "P@ssw0rd!", "organization": "FTC", "country": "CN", "bio": "赛事管理员", "avatar": "https://avatars.githubusercontent.com/u/15?v=4", "is_staff": True},
            # 5 额外普通用户，补足 20+
            {"username": "player11", "email": "player11@example.com", "nickname": "Kiki", "password": "P@ssw0rd!", "organization": "BugHunters", "country": "UK", "bio": "Web 挖洞", "avatar": "https://avatars.githubusercontent.com/u/16?v=4"},
            {"username": "player12", "email": "player12@example.com", "nickname": "Leo", "password": "P@ssw0rd!", "organization": "pwned", "country": "US", "bio": "堆风控", "avatar": "https://avatars.githubusercontent.com/u/17?v=4"},
            {"username": "player13", "email": "player13@example.com", "nickname": "Mia", "password": "P@ssw0rd!", "organization": "KeySec", "country": "SG", "bio": "密码学爱好者", "avatar": "https://avatars.githubusercontent.com/u/18?v=4"},
            {"username": "player14", "email": "player14@example.com", "nickname": "Nina", "password": "P@ssw0rd!", "organization": "SecGirls", "country": "CN", "bio": "逆向萌新", "avatar": "https://avatars.githubusercontent.com/u/19?v=4"},
            {"username": "player15", "email": "player15@example.com", "nickname": "Oscar", "password": "P@ssw0rd!", "organization": "NightShift", "country": "AU", "bio": "运维安全", "avatar": "https://avatars.githubusercontent.com/u/20?v=4"},
            {"username": "player16", "email": "player16@example.com", "nickname": "Pete", "password": "P@ssw0rd!", "organization": "Trace", "country": "US", "bio": "取证/日志分析", "avatar": "https://avatars.githubusercontent.com/u/21?v=4"},
            {"username": "player17", "email": "player17@example.com", "nickname": "Quinn", "password": "P@ssw0rd!", "organization": "CryptoGang", "country": "FR", "bio": "侧信道研究", "avatar": "https://avatars.githubusercontent.com/u/22?v=4"},
            {"username": "player18", "email": "player18@example.com", "nickname": "Rex", "password": "P@ssw0rd!", "organization": "Pentesters", "country": "SE", "bio": "渗透测试", "avatar": "https://avatars.githubusercontent.com/u/23?v=4"},
            {"username": "player19", "email": "player19@example.com", "nickname": "Sara", "password": "P@ssw0rd!", "organization": "FlySec", "country": "CN", "bio": "CTF 练习生", "avatar": "https://avatars.githubusercontent.com/u/24?v=4"},
            {"username": "player20", "email": "player20@example.com", "nickname": "Tom", "password": "P@ssw0rd!", "organization": "Hackers", "country": "US", "bio": "全栈安全", "avatar": "https://avatars.githubusercontent.com/u/25?v=4"},
        ]
        created = {}
        for item in demo_users:
            user = User(
                username=item["username"],
                email=item["email"],
                nickname=item["nickname"],
                organization=item["organization"],
                country=item["country"],
                bio=item["bio"],
                avatar=item["avatar"],
                is_email_verified=True,
                is_staff=item.get("is_staff", False),
                is_superuser=item.get("is_superuser", False),
                account_type=User.AccountType.ADMIN if item.get("is_staff") else User.AccountType.USER,
            )
            user.set_password(item["password"])
            user.save()
            if user.account_type == User.AccountType.ADMIN and not user.is_superuser:
                assign_default_admin_permissions(user)
            elif user.account_type == User.AccountType.USER:
                assign_default_user_permissions(user)
            created[item["username"]] = user
        return created

    def _create_contests(self, users):
        now = timezone.now()
        base_contests = [
            ("winter-ctf", "冬季攻防赛", -1, 2, True),
            ("spring-newbie", "春季新手赛", 5, 8, True),
            ("summer-webcup", "夏季 Web Cup", 8, 10, True),
            ("autumn-open", "秋季公开赛", -30, -25, False),
            ("city-invite", "城市邀请赛", 3, 6, True),
            ("red-team-show", "红队挑战赛", -2, 1, True),
            ("solo-sprint", "个人极速赛", 1, 2, False),
            ("crypto-carnival", "密码嘉年华", 4, 7, False),
            ("forensics-festival", "取证嘉年华", -5, -2, True),
            ("weekend-misc", "周末杂项赛", 0, 1, False),
            ("reverse-rumble", "逆向对决", 6, 9, True),
            ("pwn-prime", "Pwn 极客赛", 10, 13, True),
            ("web-wave", "Web 狂潮", -3, 0, True),
            ("newbie-cup-2", "新手杯第二季", 12, 15, True),
            ("winter-individual", "冬季个人练习赛", -6, -4, False),
            ("team-scrimmage", "组队练兵赛", 2, 4, True),
            ("global-open", "全球公开赛", 15, 20, True),
            ("speed-run", "极速短赛", -12, -11, False),
            ("midnight-hack", "午夜挑战赛", 18, 21, True),
            ("ctf-classic", "经典重现赛", -15, -10, False),
        ]
        data = []
        for slug, name, start_offset, end_offset, is_team in base_contests:
            data.append(
                {
                    "name": name,
                    "slug": slug,
                    "description": f"{name} 示例赛事，包含五类题目与公告。",
                    "visibility": Contest.Visibility.PUBLIC,
                    "start_time": now + timedelta(days=start_offset),
                    "end_time": now + timedelta(days=end_offset),
                    "freeze_time": now + timedelta(days=end_offset - 1) if start_offset < 0 else None,
                    "registration_start_time": now + timedelta(days=start_offset - 5),
                    "registration_end_time": now + timedelta(days=start_offset - 1),
                    "is_team_based": is_team,
                    "max_team_members": 4 if is_team else 1,
                }
            )
        contests = {}
        for item in data:
            contests[item["slug"]] = Contest.objects.create(**item)
        return contests

    def _create_challenges_and_machines(self, contests, users):
        author = users["player1"]
        base_categories = [
            ("web", "Web", "Web 安全与漏洞利用"),
            ("pwn", "Pwn", "二进制漏洞利用"),
            ("reverse", "Reverse", "逆向工程"),
            ("crypto", "Crypto", "密码学相关"),
            ("misc", "Misc", "综合/杂项"),
        ]

        for contest in contests.values():
            categories = {}
            for slug, name, desc in base_categories:
                categories[slug] = ChallengeCategory.objects.create(
                    contest=contest, name=name, slug=slug, description=desc
                )

            for cat_slug, cat_name, _ in base_categories:
                for i in range(1, 4):
                    chal = Challenge.objects.create(
                        contest=contest,
                        category=categories[cat_slug],
                        title=f"{cat_name} Challenge {i}",
                        slug=f"{contest.slug}-{cat_slug}-{i}",
                        short_description=f"{cat_name} 示例题目 {i}",
                        content=f"{cat_name} 题面 {i}，请按照提示获取 flag。",
                        difficulty=Challenge.Difficulty.MEDIUM,
                        base_points=100 + i * 50,
                        flag=f"FLAG{{{contest.slug}_{cat_slug}_{i}}}",
                        flag_type=Challenge.FlagType.STATIC,
                        flag_case_insensitive=True,
                        dynamic_prefix="FLAG",
                        scoring_mode=Challenge.ScoringMode.FIXED,
                        decay_type=Challenge.DecayType.PERCENTAGE,
                        decay_factor=0.9,
                        min_score=80,
                        blood_reward_type=Challenge.BloodRewardType.NONE,
                        blood_reward_count=0,
                        blood_bonus_points=[],
                        author=author,
                        has_machine=(cat_slug == "web"),
                        is_active=True,
                    )
                    # 提示：1 条免费 + 1 条扣分
                    ChallengeHint.objects.create(
                        challenge=chal,
                        title="免费提示",
                        content=f"{cat_name} 第 {i} 题的免费提示：关注输入验证和基本信息收集。",
                        is_free=True,
                        cost=0,
                        order=1,
                    )
                    ChallengeHint.objects.create(
                        challenge=chal,
                        title="扣分提示",
                        content=f"{cat_name} 第 {i} 题的扣分提示：尝试查看 {cat_name.lower()} 典型漏洞利用思路。",
                        is_free=False,
                        cost=10,
                        order=2,
                    )
                    if cat_slug == "web":
                        ChallengeMachineConfig.objects.create(
                            challenge=chal,
                            image="nginx:alpine",
                            container_port=80,
                            max_instances_per_user=1,
                            max_runtime_minutes=60,
                            environment={"FLAG": f"DEMO{{{contest.slug}_{chal.slug}_FLAG}}"},
                        )

    def _create_announcements(self, contests):
        template_entries = [
            ("赛程提示", "赛事正在进行，请关注封榜时间与公告。"),
            ("新增题库挑战", "新增多道 Web/Pwn/Reverse 题目，包含靶机。"),
            ("报名提醒", "报名截止前请确认队伍人数与资料，避免报名无效。"),
            ("环境说明", "所有 Web 题提供独立靶机，请按题面描述启动。"),
            ("榜单信息", "封榜期间提交仍会记录，排名在赛后解封。"),
        ]
        now = timezone.now()
        for contest in contests.values():
            for idx, (title, summary) in enumerate(template_entries[:3], start=1):
                ContestAnnouncement.objects.create(
                    contest=contest,
                    title=f"{contest.name} · {title}",
                    summary=summary,
                    content=summary,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )

    def _create_teams_and_participants(self, contests, users):
        """
        创建团队、成员及报名记录，确保：
        - 每个团队赛有多支队伍，用户均分进队
        - 每个用户至少报名一场比赛
        - 每个比赛至少一个管理员（staff）报名
        """
        now = timezone.now()
        normal_users = [u for u in users.values() if not u.is_staff]
        admin_users = [u for u in users.values() if u.is_staff]

        # 先为所有用户分配至少一场参赛
        personal_contests = [c for c in contests.values() if not c.is_team_based]
        team_contests = [c for c in contests.values() if c.is_team_based]

        # 为个人赛创建报名（循环分配，至少一场）
        for idx, user in enumerate(normal_users):
            contest = personal_contests[idx % len(personal_contests)]
            ContestParticipant.objects.create(
                contest=contest,
                user=user,
                status=ContestParticipant.Status.RUNNING if contest.has_started else ContestParticipant.Status.REGISTERED,
                is_valid=True,
                created_at=now,
                updated_at=now,
            )

        # 为团队赛创建队伍与成员，保证覆盖所有用户
        user_cycle = normal_users.copy()
        team_slug_counter = 1
        for contest in team_contests:
            teams = []
            for t in range(3):
                captain = user_cycle[t % len(user_cycle)]
                team = Team.objects.create(
                    contest=contest,
                    name=f"{contest.slug}-team-{t+1}",
                    slug=f"{contest.slug}-team-{t+1}",
                    description=f"{contest.name} 示例队伍 {t+1}",
                    captain=captain,
                    invite_token=f"{contest.slug}-token-{team_slug_counter}",
                )
                team_slug_counter += 1
                teams.append(team)

            # 分配成员（每队最多 4 人）
            for team in teams:
                members = []
                for _ in range(4):
                    user = user_cycle.pop(0)
                    members.append(
                        TeamMember(team=team, user=user, role=TeamMember.Role.MEMBER)
                    )
                    # 轮回用户列表
                    user_cycle.append(user)
                TeamMember.objects.bulk_create(members)
                # 队长记录
                TeamMember.objects.get_or_create(team=team, user=team.captain, defaults={"role": TeamMember.Role.CAPTAIN})

                # 队伍成员报名
                for member in members:
                    ContestParticipant.objects.get_or_create(
                        contest=contest,
                        user=member.user,
                        defaults={
                            "status": ContestParticipant.Status.RUNNING if contest.has_started else ContestParticipant.Status.REGISTERED,
                            "is_valid": True,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )

        # 为每个比赛添加一个管理员报名（确保非超管管理员存在）
        for idx, contest in enumerate(contests.values()):
            admin = admin_users[idx % len(admin_users)] if admin_users else None
            if admin:
                ContestParticipant.objects.get_or_create(
                    contest=contest,
                    user=admin,
                    defaults={
                        "status": ContestParticipant.Status.RUNNING if contest.has_started else ContestParticipant.Status.REGISTERED,
                        "is_valid": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                )

    def _create_problem_banks(self, users):
        """
        创建演示题库：
        - 至少 3 个题库
        - 每个题库包含 web/crypto/misc/pwn/reverse 五类
        - 每类至少 3 道题，web 题面带靶机运行提示
        """
        author = users.get("player1") or next(iter(users.values()))
        now = timezone.now()
        bank_machine_contest = Contest.objects.create(
            name="题库演练场",
            slug="bank-lab",
            description="为题库 Web 题提供靶机演示的练习比赛（个人赛）。",
            visibility=Contest.Visibility.PUBLIC,
            start_time=now - timedelta(days=3),
            end_time=now + timedelta(days=60),
            freeze_time=None,
            registration_start_time=now - timedelta(days=5),
            registration_end_time=now + timedelta(days=55),
            is_team_based=False,
            max_team_members=1,
        )
        bank_machine_categories = {}
        base_categories = [
            ("web", "Web", "Web 安全与漏洞利用"),
            ("crypto", "Crypto", "密码学基础与应用"),
            ("misc", "Misc", "杂项技巧与综合玩法"),
            ("pwn", "Pwn", "二进制漏洞利用"),
            ("reverse", "Reverse", "逆向分析与调试"),
        ]
        for slug, name, desc in base_categories:
            bank_machine_categories[slug] = ChallengeCategory.objects.create(
                contest=bank_machine_contest, name=name, slug=slug, description=desc
            )
        base_banks = [
            {
                "name": "入门演练题库",
                "slug": "starter-bank",
                "description": "面向新手的基础练习，覆盖五大方向。",
                "is_public": True,
            },
            {
                "name": "进阶综合题库",
                "slug": "advanced-bank",
                "description": "进阶综合演练，适合有一定经验的选手复盘。",
                "is_public": True,
            },
            {
                "name": "攻防演示题库",
                "slug": "blue-red-bank",
                "description": "偏实战场景的演示题库，便于演示攻防流程。",
                "is_public": True,
            },
        ]
        difficulty_cycle = [
            BankChallenge.Difficulty.EASY,
            BankChallenge.Difficulty.MEDIUM,
            BankChallenge.Difficulty.HARD,
        ]

        for bank_meta in base_banks:
            bank = ProblemBank.objects.create(**bank_meta)
            categories = {}
            for slug, name, desc in base_categories:
                categories[slug] = BankCategory.objects.create(bank=bank, name=name, slug=slug)

            for cat_slug, cat_name, desc in base_categories:
                for idx in range(1, 4):
                    slug = f"{bank.slug}-{cat_slug}-{idx}"
                    difficulty = difficulty_cycle[(idx - 1) % len(difficulty_cycle)]
                    flag = f"PB{{{bank.slug}_{cat_slug}_{idx}}}"
                    content = [
                        f"{cat_name} 示例题目 {idx}",
                        desc,
                        "请根据题面提示提交正确的 Flag。",
                    ]
                    if cat_slug == "web":
                        content.append(
                            "靶机提示：使用 nginx:alpine 镜像演示，示例命令 "
                            "`docker run --rm -p 8080:80 -e FLAG=DEMO_FLAG nginx:alpine`，"
                            "平台会为正式赛题配置 ChallengeMachineConfig。"
                        )
                    machine_contest_slug = ""
                    machine_challenge_slug = ""
                    # Web 题创建对应的比赛题目与靶机配置，便于前端与机器服务复用
                    if cat_slug == "web":
                        contest_category = bank_machine_categories.get(cat_slug)
                        machine_challenge_slug = f"{bank.slug}-{cat_slug}-{idx}-lab"
                        mirror_challenge = Challenge.objects.create(
                            contest=bank_machine_contest,
                            category=contest_category,
                            title=f"{cat_name} 演练题 {idx} ({bank.slug})",
                            slug=machine_challenge_slug,
                            short_description=f"{cat_name} 题库演练靶机 {idx}",
                            content="\n\n".join(content),
                            difficulty=Challenge.Difficulty.MEDIUM,
                            base_points=200,
                            flag=f"PB-LAB{{{bank.slug}_{cat_slug}_{idx}}}",
                            flag_type=Challenge.FlagType.STATIC,
                            flag_case_insensitive=True,
                            dynamic_prefix="FLAG",
                            scoring_mode=Challenge.ScoringMode.FIXED,
                            decay_type=Challenge.DecayType.PERCENTAGE,
                            decay_factor=0.9,
                            min_score=120,
                            blood_reward_type=Challenge.BloodRewardType.NONE,
                            blood_reward_count=0,
                            blood_bonus_points=[],
                            author=author,
                            has_machine=True,
                            is_active=True,
                        )
                        ChallengeMachineConfig.objects.create(
                            challenge=mirror_challenge,
                            image="nginx:alpine",
                            container_port=80,
                            max_instances_per_user=1,
                            max_runtime_minutes=60,
                            environment={"FLAG": f"PB-LAB{{{bank.slug}_{cat_slug}_{idx}}}"},
                            extend_minutes_default=30,
                            extend_max_times=3,
                            extend_threshold_minutes=10,
                        )
                        machine_contest_slug = bank_machine_contest.slug
                    challenge = BankChallenge.objects.create(
                        bank=bank,
                        category=categories[cat_slug],
                        title=f"{cat_name} 题库题 {idx}",
                        slug=slug,
                        short_description=f"{cat_name} 方向示例题 {idx}",
                        content="\n\n".join(content),
                        difficulty=difficulty,
                        flag=flag,
                        flag_case_insensitive=True,
                        flag_type=BankChallenge.FlagType.STATIC,
                        dynamic_prefix="FLAG",
                        is_active=True,
                        author=author,
                        machine_contest_slug=machine_contest_slug,
                        machine_challenge_slug=machine_challenge_slug,
                    )

                    if cat_slug == "web":
                        BankHint.objects.create(
                            challenge=challenge,
                            title="靶机启动方式",
                            content="本地可用 docker run --rm -p 8080:80 -e FLAG=DEMO_FLAG nginx:alpine 进行演示。",
                            order=1,
                            is_free=True,
                            cost=0,
                        )
                        BankAttachment.objects.create(
                            challenge=challenge,
                            name="示例环境说明",
                            url="https://hub.docker.com/_/nginx",
                            order=1,
                        )
                    # 通用提示：免费 + 扣分（题库不扣分，仅用于区分标签）
                    BankHint.objects.create(
                        challenge=challenge,
                        title="免费提示",
                        content=f"{cat_name} 第 {idx} 题的免费提示：关注基础信息收集与输入验证。",
                        order=2,
                        is_free=True,
                        cost=0,
                    )
                    BankHint.objects.create(
                        challenge=challenge,
                        title="扣分提示",
                        content=f"{cat_name} 第 {idx} 题的扣分提示：尝试更深入的漏洞利用或变体思路。",
                        order=3,
                        is_free=False,
                        cost=10,
                    )
