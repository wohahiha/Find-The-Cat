"""
业务异常体系（BizError）

约定：
- 所有“预期内的业务错误”都继承 BizError；
- 系统级错误（代码 bug、数据库挂了等）让全局异常处理器按 500 处理。

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

注意：
- 全局异常处理器只需要判断 isinstance(exc, BizError)，
  然后读取 exc.code / exc.message / exc.http_status / exc.extra 即可构造统一响应。
"""


class BizError(Exception):
    """
    所有业务异常的基类。

    设计要点：
    - 不耦合 DRF / Response，只是纯数据和语义；
    - 子类只需覆盖 default_code / default_message / http_status；
    - 也可以在 __init__ 时传入自定义 message / code / extra 做覆盖。
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
    用户名 / 密码错误、或帐号状态异常导致无法登录。
    """
    default_code = 40101
    default_message = "用户名或密码错误"


class TokenError(AuthError):
    """
    Token 无效 / 过期 / 被吊销。
    """
    default_code = 40102
    default_message = "登录状态已失效，请重新登录"


class AccountInactiveError(AuthError):
    """
    账户处于停用或失效状态，禁止登录。
    """
    default_code = 40103
    default_message = "账户失效，请联系管理员"


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
# 工具函数
# ======================

def require(condition: bool, error: BizError) -> None:
    """
    小工具：用于在业务代码中快速断言业务条件。

    用法：
        require(user.is_active, AuthError("帐号已被禁用"))
    """
    if not condition:
        raise error
