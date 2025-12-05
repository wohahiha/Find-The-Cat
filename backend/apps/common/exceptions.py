"""
业务异常体系（BizError）

约定与作用：
- 所有“预期内的业务错误”都继承 BizError，避免直接抛框架异常
- 统一错误码/HTTP 状态/提示语，便于前后端对齐
- 系统级错误（代码 bug、数据库故障等）由全局异常处理器按 500 处理

错误码规范：
- 0                : 成功（只出现在正常响应里）
- 40000~40099      : 通用请求 / 参数错误（Validation、BadRequest）
- 40100~40199      : 认证错误（未登录、Token 无效、登录失败等）
- 40300~40399      : 权限错误（无权限访问某资源/操作）
- 40400~40499      : 资源不存在（用户、比赛、题目等）
- 40900~40999      : 资源冲突（重复报名、重复加入队伍等）
- 42900~42999      : 频率限制（节流 / 风控）
- 46000~46099      : 比赛状态相关错误（未开始、已结束、封榜期间限制等）
- 47000~47099      : 队伍/成员相关错误（队伍已满、已在队伍中等）
- 48000~48099      : 题目 / Flag 相关错误（题目不可见、Flag 已解出等）
- 50300~50399      : 基础设施/第三方依赖不可用（缓存、消息队列等）

使用方式：
- 业务层抛 BizError 或子类；全局异常处理器读取 exc.code/message/http_status/extra 构造统一响应
"""


class BizError(Exception):
    """
    所有业务异常的基类

    设计要点：
    - 不耦合 DRF / Response，只是纯数据和语义；
    - 子类只需覆盖 default_code / default_message / http_status；
    - 也可以在 __init__ 时传入自定义 message / code / extra 做覆盖
    """

    #: 子类可覆盖的默认错误码
    default_code: int = 40000

    #: 子类可覆盖的默认提示信息
    default_message: str = "业务错误"

    #: 子类可覆盖的建议 HTTP 状态码（交给异常处理器用）
    http_status: int = 400

    def __init__(self, message: str | None = None, code: int | None = None, *, extra: dict | None = None):
        self.code = code if code is not None else self.default_code
        self.message = message if message is not None else self.default_message
        self.extra = extra or {}
        super().__init__(self.message)

    def __str__(self) -> str:  # 方便日志输出
        return f"[{self.code}] {self.message}"


# ======================
# 通用类错误
# ======================

class BadRequestError(BizError):
    """
    通用的 400 错误：
    - 无法解析的请求
    - 请求格式错误/缺少头信息等
    """
    default_code = 40001
    default_message = "错误的请求"
    http_status = 400


class ValidationError(BizError):
    """
    参数校验 / 请求数据不合法：
    - 缺少必要字段
    - 字段格式错误
    """
    default_code = 40002
    default_message = "请求参数不合法"
    http_status = 400


class NotFoundError(BizError):
    """
    通用资源不存在：
    - 用户不存在
    - 比赛/题目不存在
    - 某个 ID 对应的资源未找到
    """
    default_code = 40400
    default_message = "资源不存在"
    http_status = 404


class ConflictError(BizError):
    """
    资源冲突：
    - 已存在同名对象
    - 当前状态下不允许重复操作（重复报名、重复提交等）
    """
    default_code = 40900
    default_message = "资源冲突"
    http_status = 409


class OperationNotAllowedError(BizError):
    """
    当前状态不允许的操作：
    - 资源被锁定或处于不可变更状态
    """
    default_code = 40910
    default_message = "当前状态不允许执行该操作"
    http_status = 409


class ResourceLockedError(BizError):
    """
    资源被占用或锁定：
    - 需要等待释放后再操作
    """
    default_code = 40911
    default_message = "资源被占用，请稍后重试"
    http_status = 409


class RateLimitError(BizError):
    """
    触发频率限制 / 风控：
    - 提交太频繁
    - 登录尝试过多
    """
    default_code = 42900
    default_message = "请求过于频繁，请稍后再试"
    http_status = 429


# ======================
# 认证 / 授权相关
# ======================

class AuthError(BizError):
    """
    认证相关错误（登录、Token 等）：
    - 统一归类为 401xx
    """
    default_code = 40100
    default_message = "认证失败"
    http_status = 401


class InvalidCredentialsError(AuthError):
    """
    用户名 / 密码错误、或帐号状态异常导致无法登录
    """
    default_code = 40101
    default_message = "用户名或密码错误"


class TokenError(AuthError):
    """
    Token 无效 / 过期 / 被吊销
    """
    default_code = 40102
    default_message = "登录状态已失效，请重新登录"


class AccountInactiveError(AuthError):
    """
    账户处于停用或失效状态，禁止登录
    """
    default_code = 40103
    default_message = "账户失效，请联系管理员"


class CaptchaValidationError(AuthError):
    """
    登录/敏感操作的图形验证码错误：
    - 验证码不存在/过期
    - 验证码输入错误
    """
    default_code = 40104
    default_message = "验证码错误，请刷新后重试"
    http_status = 400


class EmailNotVerifiedError(AuthError):
    """
    邮箱尚未完成验证：
    - 登录、重置密码等敏感操作需要确保邮箱已通过验证码校验
    """
    default_code = 40105
    default_message = "邮箱未验证，请先完成邮箱验证"
    http_status = 400


class AccountBannedError(AuthError):
    """
    账户因风控/封禁被禁止登录
    """
    default_code = 40106
    default_message = "账户已被封禁，暂无法登录"
    http_status = 403


class PermissionDeniedError(BizError):
    """
    权限不足：
    - 角色不够（普通用户访问管理员接口）
    - 不是资源拥有者（访问别人队伍 / 别人提交等）
    """
    default_code = 40300
    default_message = "无权限进行该操作"
    http_status = 403


# ======================
# 比赛领域错误
# ======================

class ContestError(BizError):
    """比赛相关通用错误基类"""
    default_code = 46000
    default_message = "比赛相关错误"
    http_status = 400


class ContestNotStartedError(ContestError):
    """比赛未开始"""
    default_code = 46001
    default_message = "比赛尚未开始，当前不可提交"


class ContestEndedError(ContestError):
    """比赛已结束"""
    default_code = 46002
    default_message = "比赛已结束，提交不再计分"


class ContestFrozenError(ContestError):
    """比赛因特殊原因冻结"""
    default_code = 46003
    default_message = "比赛因特殊原因已冻结"


class ContestNotVisibleError(ContestError):
    """比赛不可见或未发布"""
    default_code = 46004
    default_message = "比赛未发布或不可见"


class ContestTeamNotAllowedError(ContestError):
    """比赛未开启组队功能"""
    default_code = 46005
    default_message = "当前比赛未开启组队功能"


class ContestJoinWindowClosedError(ContestError):
    """比赛报名/加入时间窗已关闭"""
    default_code = 46006
    default_message = "当前时间不可加入比赛或队伍"


class ContestFrozenSubmissionError(ContestError):
    """封榜期间限制提交/展示"""
    default_code = 46007
    default_message = "比赛封榜期间暂不支持该操作"


# ======================
# 队伍领域错误
# ======================

class TeamError(BizError):
    """队伍相关通用错误基类"""
    default_code = 47000
    default_message = "队伍相关错误"
    http_status = 400


class TeamAlreadyJoinedError(TeamError):
    """用户已在队伍中，不能重复加入"""
    default_code = 47001
    default_message = "你已加入其他队伍，不能重复加入"


class TeamFullError(TeamError):
    """队伍已满员"""
    default_code = 47002
    default_message = "队伍人数已满，无法加入"


class TeamNotMemberError(TeamError):
    """用户不是该队伍成员"""
    default_code = 47003
    default_message = "你不是该队伍成员，不能进行此操作"


class TeamDissolvedError(TeamError):
    """队伍已解散"""
    default_code = 47004
    default_message = "队伍已解散，无法继续操作"


class TeamCaptainRequiredError(TeamError):
    """需要队长权限"""
    default_code = 47005
    default_message = "仅队长可执行该操作"


class TeamJoinCodeInvalidError(TeamError):
    """队伍邀请码无效或过期"""
    default_code = 47006
    default_message = "队伍邀请码无效，请联系队长重新获取"


# ======================
# 账户领域错误
# ======================

class AccountError(BizError):
    """账户相关通用错误基类"""
    default_code = 40950
    default_message = "账户相关错误"
    http_status = 400


class AccountIdLimitError(AccountError):
    """
    账户ID分配达到上限：
    - 超级管理员数量已达上限（10个）
    - 普通管理员数量已达上限（990个）
    """
    default_code = 40951
    default_message = "账户ID分配已达上限，无法创建新用户"
    http_status = 400


class EmailVerificationCodeError(AccountError):
    """
    邮箱验证码错误或不存在
    """
    default_code = 40952
    default_message = "邮箱验证码错误或已失效"
    http_status = 400


class EmailAlreadyBoundError(AccountError):
    """
    邮箱已被绑定，禁止重复绑定
    """
    default_code = 40953
    default_message = "该邮箱已被绑定，请更换邮箱"
    http_status = 400


class AccountSoftDeletedError(AccountError):
    """
    账户已注销（软删除），禁止继续操作
    """
    default_code = 40954
    default_message = "账户已注销，无法完成该操作"
    http_status = 400


# ======================
# 题目领域错误
# ======================

class ChallengeError(BizError):
    """题目相关通用错误基类"""
    default_code = 48000
    default_message = "题目相关错误"
    http_status = 400


class ChallengeNotAvailableError(ChallengeError):
    """
    题目不可用：
    - 未发布 / 已隐藏 / 不属于当前比赛 / 不在可见范围
    """
    default_code = 48001
    default_message = "当前题目暂不可用"


class ChallengeAlreadySolvedError(ChallengeError):
    """
    题目已经被当前用户/队伍解出：
    - 通常用于阻止重复计分
    """
    default_code = 48002
    default_message = "该题已解出，无需重复提交"


class ChallengeNotInContestError(ChallengeError):
    """题目不属于当前比赛"""
    default_code = 48003
    default_message = "当前比赛未包含该题目"


class ChallengeHiddenError(ChallengeError):
    """题目未发布或已隐藏"""
    default_code = 48004
    default_message = "题目未发布或不可见"


class HintLockedError(ChallengeError):
    """提示未解锁"""
    default_code = 48005
    default_message = "提示未解锁，暂不可查看"


class AttachmentNotAccessibleError(ChallengeError):
    """附件不存在或无权限访问"""
    default_code = 48006
    default_message = "附件不可访问"


# ======================
# Flag 领域错误
# ======================

class FlagError(ChallengeError):
    """Flag 相关错误基类"""
    default_code = 48010
    default_message = "Flag 提交相关错误"


class FlagFormatError(FlagError):
    """Flag 格式不符合规则（例如缺少前缀/不合法字符等）"""
    default_code = 48011
    default_message = "Flag 格式不正确"


class WrongFlagError(FlagError):
    """Flag 值错误"""
    default_code = 48012
    default_message = "Flag 不正确，请继续努力"


# ======================
# 提交领域错误
# ======================

class SubmissionError(BizError):
    """提交相关通用错误基类"""
    default_code = 48100
    default_message = "提交相关错误"
    http_status = 400


class SubmissionDuringFreezeError(SubmissionError):
    """封榜期间不允许提交或展示"""
    default_code = 48101
    default_message = "封榜期间暂不允许提交"


class SubmissionRateLimitError(SubmissionError):
    """提交频率限制"""
    default_code = 48102
    default_message = "提交过于频繁，请稍后再试"


# ======================
# 基础设施 / 第三方服务错误
# ======================

class InfrastructureError(BizError):
    """
    基础设施或第三方依赖不可用：
    - 缓存 / 队列 / 邮件等依赖故障
    """
    default_code = 50300
    default_message = "系统服务暂时不可用，请稍后重试"
    http_status = 503


class CacheUnavailableError(InfrastructureError):
    """
    缓存（Redis 等）不可用：
    - 连接失败 / 超时 / 未启动
    """
    default_code = 50301
    default_message = "缓存服务暂时不可用，请稍后重试"
    http_status = 503


class QueueUnavailableError(InfrastructureError):
    """
    消息队列不可用（如 Celery Broker）
    """
    default_code = 50302
    default_message = "消息队列暂时不可用，请稍后重试"
    http_status = 503


class StorageUnavailableError(InfrastructureError):
    """
    文件存储不可用（本地/对象存储）
    """
    default_code = 50303
    default_message = "文件存储服务暂时不可用，请稍后重试"
    http_status = 503


class EmailSendError(InfrastructureError):
    """
    邮件发送失败
    """
    default_code = 50304
    default_message = "邮件发送失败，请稍后重试"
    http_status = 503


# ======================
# 靶机领域错误
# ======================

class MachineError(BizError):
    """靶机相关通用错误基类"""
    default_code = 49000
    default_message = "靶机相关错误"
    http_status = 400


class MachineAlreadyRunningError(MachineError):
    """同一题目已有运行中的实例"""
    default_code = 49001
    default_message = "已有运行中的靶机实例，请勿重复创建"


class MachinePortUnavailableError(MachineError):
    """端口分配失败或占用"""
    default_code = 49002
    default_message = "靶机端口分配失败，请稍后重试"


class MachineQuotaExceededError(MachineError):
    """实例数量超出配额"""
    default_code = 49003
    default_message = "靶机实例数量已达上限"


class MachineImageNotFoundError(MachineError):
    """容器镜像不存在"""
    default_code = 49004
    default_message = "靶机镜像不存在，请联系管理员"


class MachineStartRateLimitError(MachineError):
    """靶机启动节流"""
    default_code = 49005
    default_message = "启动过于频繁，请稍后再试"


# ======================
# 工具函数
# ======================

def require(condition: bool, error: BizError) -> None:
    """
    小工具：用于在业务代码中快速断言业务条件

    用法：
        require(user.is_active, AuthError("帐号已被禁用"))
    """
    if not condition:
        raise error
