# **AGENTS.md**

> **本文件用于统一整个代码生成代理（Codex）的行为规范，确保在本项目中自动生成的所有代码均满足：可维护、高内聚、低耦合、可扩展，并严格遵守
FTC 项目的技术架构与 SRS 定义**

------

## 0. 总则

1. 本仓库为 **Find The Cat（FTC）CTF 竞赛平台后端**，基于 **Django + DRF** 实现，采用分层和模块化设计
2. **一切业务行为必须严格对齐 SRS 与需求文档**，不得凭空臆造需求
3. 所有新增代码必须：
    - 使用 **简体中文注释**（必要技术术语保留英文）；
    - 遵守统一的 **错误处理、权限、限流、响应格式**；
    - 保持 **高内聚，低耦合**
4. 不确定的地方，宁可 **保守、留 TODO 注释**，也不要拍脑袋造协议或字段

------

## 1. **项目结构与生成规则**

### 1.1 顶层目录说明

本项目采用 Django + DRF + Vue 的前后端分离架构，后端结构如下（已包含当前进度中的新增文件、迁移与模板覆盖）：

```
FTC/                          # Django 项目根目录
│
├─ AGENTS.md                  # 本文件
├─ manage.py                  # Django 启动脚本
├─ .env                       # 环境变量文件（SECRET_KEY、DB 配置等）
├─ db.sqlite3                 # 开发环境数据库（正式环境建议 PostgreSQL）
├─ schema.yaml                # API schema 草稿（持续迭代）
├─ logs/
│   └─ ftc.log                # 统一日志输出
│
├─ Config/                    # Django 项目配置包
│   ├─ __init__.py
│   ├─ settings.py            # 全局配置（数据库/DRF/JWT/异常处理/限流/日志/Celery、本地化）
│   ├─ urls.py                # 全局路由入口（accounts/contests/submissions/machines/captcha/schema）
│   ├─ celery.py              # Celery 应用与 beat 调度（靶机清理）
│   ├─ asgi.py                # ASGI 网关（未来接入 WebSocket）
│   └─ wsgi.py                # WSGI 网关（部署时使用）
│
├─ apps/                      # 所有业务模块（分 app）
│   ├─ __init__.py
│   ├─ common/                # 通用基础设施层（全局复用）
│   │   ├─ base/              # 基类：仓储/服务/Schema
│   │   ├─ infra/             # docker_manager、email_sender、file_storage、jwt_provider、logger、redis_client
│   │   ├─ utils/             # crypto/helpers/redis_keys/request_context/time/validators
│   │   ├─ authentication.py  # JWT 认证入口
│   │   ├─ exception_handler.py # 全局异常处理器
│   │   ├─ exceptions.py      # 业务异常体系
│   │   ├─ middleware.py      # 请求上下文写入，配合日志过滤
│   │   ├─ openapi.py         # JWT 文档扩展（drf-spectacular）
│   │   ├─ pagination.py      # 统一分页器
│   │   ├─ permission_sets.py # 默认权限集声明与标签
│   │   ├─ permissions.py     # 自定义权限
│   │   ├─ response.py        # 统一 API 响应格式
│   │   ├─ throttles.py       # 自定义限速
│   │   └─ tests_utils.py     # 测试辅助工具
│   │
│   ├─ accounts/              # 用户与认证模块
│   │   ├─ admin.py           # Django admin 注册与展示
│   │   ├─ apps.py            # Django app 配置
│   │   ├─ backends.py        # 认证后端（后台登录异常提示）
│   │   ├─ models.py          # 用户、邮箱验证码、发信账号
│   │   ├─ repo.py            # 账号数据访问层
│   │   ├─ schemas.py         # Serializer（注册/登录/资料/邮箱验证码）
│   │   ├─ services.py        # 账号业务逻辑（验证码、注册、登录、资料、密码/邮箱变更、注销）
│   │   ├─ signals.py         # 信号占位
│   │   ├─ tests.py           # 账号 API/流程测试
│   │   ├─ urls.py            # 账号路由配置
│   │   ├─ utils.py           # 权限组分配等工具
│   │   ├─ views.py           # 账号接口层
│   │   └─ migrations/0001_...0009_*.py
│   │
│   ├─ contests/              # 比赛管理（比赛、公告、队伍、记分板、导出）
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py          # Contest、Team、ContestAnnouncement、ContestScoreboard
│   │   ├─ repo.py            # 比赛、公告、队伍仓储
│   │   ├─ schemas.py         # 比赛/公告/队伍序列化与校验
│   │   ├─ services.py        # 比赛状态、公告发布、队伍生命周期、记分板、导出
│   │   ├─ tests.py           # 比赛与队伍 API 测试
│   │   ├─ urls.py            # 比赛路由（嵌套挑战路由）
│   │   ├─ views.py           # 比赛与队伍接口
│   │   └─ migrations/0001_...0004_*.py
│   │
│   ├─ challenges/            # 题目与题库
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ attachment_service.py  # 附件上传封装
│   │   ├─ crud_service.py        # 题目创建/更新（含子任务、附件、提示）
│   │   ├─ hint_service.py        # 提示列表与解锁
│   │   ├─ models.py              # Challenge/Category/Task/Attachment/Hint/HintUnlock/Solve
│   │   ├─ repo.py                # 题目与附件/子任务/提示仓储
│   │   ├─ schemas.py             # 题目/Flag/提示入参校验
│   │   ├─ serializers.py         # 序列化工具
│   │   ├─ services.py            # 服务聚合入口
│   │   ├─ tests.py               # 题目与提示 API 测试
│   │   ├─ urls.py                # 题目路由（嵌套 contests 下）
│   │   ├─ views.py               # 题目接口
│   │   ├─ static/challenges/js/challenge_admin.js # 后台表单增强
│   │   └─ migrations/0001_...0006_*.py
│   │
│   ├─ submissions/           # Flag 提交（记录、判题日志、排行榜失效）
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py
│   │   ├─ repo.py
│   │   ├─ schemas.py
│   │   ├─ services.py        # 判题、血次序、动态计分、提示扣分、记分板缓存失效
│   │   ├─ tests.py
│   │   ├─ urls.py
│   │   ├─ views.py
│   │   └─ migrations/0001_...0003_*.py
│   │
│   ├─ machines/              # 靶机实例管理（Docker 容器）
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py          # MachineInstance（已移除动态 Flag 字段）
│   │   ├─ repo.py
│   │   ├─ schemas.py
│   │   ├─ services.py        # 启停靶机、端口分配、防重复实例
│   │   ├─ tasks.py           # Celery 定时清理超时实例
│   │   ├─ tests.py
│   │   ├─ urls.py
│   │   ├─ views.py
│   │   └─ migrations/0001_...0003_*.py
│   │
│   └─ ...                    # 未来按 SRS 拓展
│
├─ locale/                    # 自定义翻译目录（覆盖后台 JS 文本）
│   └─ zh_Hans/
│       └─ LC_MESSAGES/
│           ├─ djangojs.po
│           └─ djangojs.mo
│
├─ templates/                 # 模板覆盖（Django Admin / Spectacular 预留）
│   ├─ admin/
│   │   ├─ actions.html       # 批量操作区域布局覆盖
│   │   ├─ base_site.html     # 后台首页标题/切换账户入口
│   │   └─ auth/
│   │       └─ user/
│   │           └─ add_form.html  # 新增用户页提示文案覆盖
│   └─ drf_spectacular/       # Swagger/Redoc 模板覆盖预留
│
├─ media/                     # 用户上传文件（题目附件等）
│   └─ attachments/
│
├─ docs/                      # 项目文档（SRS、设计文档等）
│   ├─ Find The Cat 需求分析与设计.md
│   └─ FTC 软件需求规格说明书.docx
│
└─ FTCVenv/                   # Python 虚拟环境（可忽略）
```

生成顺序必须严格遵守 SRS 模块顺序：

> **accounts → contests → challenges → submissions → machines**

如当前模块不存在（如 contests/），Codex 必须自动创建目录和基础文件

------

## 2. **Codex 行为规范（核心规则）**

### 2.1 关键原则

**Codex 必须：**

1. **先使用基础设施层，再写业务层代码**
   所有业务模块均必须基于：
    - `apps/common/base/`
    - `apps/common/infra/`
    - `apps/common/utils/`
    - `apps/common/exceptions.py`
    - `apps/common/permissions.py`
    - `apps/common/response.py`
2. **所有代码文件均需使用中文注释**
3. 业务接口统一使用：
    - 权限：`IsAuthenticated`、`IsAdmin`、`IsOwner`、`IsSelf` 等
    - 统一响应：`success/created/fail/page_success`
    - 异常：必须抛 `BizError` 子类，而不是 Django/DRF 默认异常
4. 控制器(ViewSet) 必须遵守：
    - RESTful 风格
    - 不直接返回 DRF Response，统一调用 `success()`
    - 业务错误使用异常体系（如 WrongFlagError、ContestNotStartedError）
5. Model、Serializer、ViewSet、Service、Repository 必须拆分清晰

------

### 2.2 模块生成规范

每个业务模块均必须包含以下结构：

```
apps/<module>/
  ├─ apps.py          # Django app 配置
  ├─ admins.py        # Django admin 
  ├─ models.py        # 数据模型（不写视图逻辑）
  ├─ schemas.py       # 序列化和参数校验
  ├─ repo.py          # 数据访问层（基于模型的查询）
  ├─ service.py       # 业务逻辑（禁止写在 views）
  ├─ views.py         # 控制器（视图层）
  ├─ urls.py          # 路由配置
  └─ tests.py         # 单元测试
```

**禁止将所有逻辑写在 views.py**
视图层只做参数接收和调用 service 层

------

### 2.3 代码风格要求

- 使用 **类型注解**
- Class 名：PascalCase
  文件/变量名：snake_case
- 所有字段必须添加中文注释（业务含义说明）
- 内外逻辑隔离：
    - Model 负责“数据结构”
    - Service 负责“业务流程”
    - Repo 负责“数据访问”
    - View 负责“暴露接口”
- 统一错误处理：
    - 使用 BizError 子类，如：
        - `TeamAlreadyJoinedError`
        - `ChallengeAlreadySolvedError`
        - `FlagFormatError`

------

## 3. **基础设施层使用规范**

基础设施层组成：

```
apps/common/
  ├─ base/            # 基类（RepositoryBase / ServiceBase / SchemaBase）
  ├─ infra/           # 基础设施（docker_manager、redis_client、file_storage、logger、email_sender、jwt_provider）
  ├─ utils/           # 工具方法（crypto/helpers/redis_keys/request_context/time/validators）
  ├─ authentication.py # JWT 认证入口
  ├─ exceptions.py    # BizError 体系
  ├─ permissions.py   # 权限体系
  ├─ permission_sets.py # 权限标签/默认组
  ├─ throttles.py     # 限速体系
  ├─ pagination.py    # 统一分页器
  ├─ response.py      # 统一响应
  ├─ exception_handler.py  # 全局异常处理器
  ├─ middleware.py    # 请求上下文写入，供日志过滤使用
  └─ openapi.py       # drf-spectacular JWT 描述扩展
```

写业务模块时必须优先使用：

- **base_service.py**：业务类继承 ServiceBase
- **base_repo.py**：数据访问层基类
- **jwt_provider** / **crypto**：用于 Token、签名等
- **docker_manager**：管理靶机生命周期
- **redis_client**：缓存、排行榜、端口占用
- **permission_sets** / **permissions**：统一权限标签与默认组
- **middleware.RequestContextMiddleware + infra.logger**：写入 request_id/user/ip 到日志

禁止直接 import Django ORM 之外的系统库，例如：

❌ 在 Controller 内直接操作 Redis
❌ 在 ViewSet 内直接执行 docker 命令

必须使用 common/infra 中的封装

------

## 4. **模块级规范（按 SRS）**

Codex 在生成对应模块代码时必须遵守以下约束

------

### 4.1 【accounts 用户模块】

必须提供：

- 自定义 User 模型（邮箱唯一、昵称/头像/组织等），邮箱验证码与可配置发信账号（MailAccount）
- 注册 / 登录 / 找回密码 / 修改密码 / 修改邮箱 / 注销；登录需校验图形验证码（captcha）
- 邮箱验证码发送（注册、找回、绑定），支持指定发信账号或 settings 兜底
- 个人资料查看/更新，默认权限组分配（permission_sets 默认组标签）
- JWT 登录返回 refresh/access，所有流程使用 Schema/Repo/Service 拆分

依赖内容：

- JWTAuthentication + LoginRateThrottle + captcha 图形码
- AuthError / InvalidCredentialsError / RateLimitError 等 BizError 体系
- Schema 层严格校验用户名/邮箱/密码格式，邮箱统一 lower()
- 注销为软删除：重写用户名/邮箱、禁用账号、清空可识别信息

------

### 4.2 【contests 比赛模块】

必须包含：

- Contest 模型（slug、时间窗口、赛制、封榜时间、可见性、是否组队），ContestScoreboard 代理
- 比赛状态判定（未开始 / 已结束 / 封榜），ContestContextService 统一校验
- 比赛公告、队伍创建/加入/退出/解散/邀请码重置/队长移交，全程使用 Repo+Service
- 比赛筛选（进行中 / 已结束），比赛导出（队伍、成员、题目、提交/解题、提示解锁、记分板）
- 记分板服务：Redis 缓存，封榜区分前台/后台缓存 key

禁止逻辑写在 Serializer 或 View 中，所有接口走 services + success()

所有状态判断必须写入 ContestContextService：

- `ensure_contest_running()` / `ensure_contest_started()` / `ensure_contest_not_ended()`
- 团队成员关系统一由 TeamMemberRepo 查询

------

### 4.3 【challenges 题目模块】

必须实现：

- Challenge 模型（分类、题面、难度、slug、计分模式、动态/静态 Flag、前缀）
- 多子任务（ChallengeTask）、附件（ChallengeAttachment）、提示及解锁记录（ChallengeHint/ChallengeHintUnlock）
- 附件上传走 file_storage 封装；后台 JS 覆盖 challenge_admin.js 提升体验
- 题目 CRUD 由 ChallengeCreate/UpdateService 完成，自动同步子任务/附件/提示
- 提示服务 ChallengeHintService：列表/解锁（校验比赛状态，扣分预留）
- Flag 校验：`Challenge.check_flag()` 统一生成期望值（动态 Flag 采用 SECRET+contest/challenge/solver 哈希）
- 计分模式：固定分值或动态衰减（percentage/fixed_step），最低分 min_score 默认基于基础分

------

### 4.4 【submissions 提交计分模块】

必须包含：

- Submission 模型（提交记录）+ ChallengeSolve（解题记录）
- 计分逻辑：固定/动态衰减 + 提示扣分，支持动态 Flag 判题
- 排行榜维护：ScoreboardService + redis 缓存，提交成功后主动失效缓存
- n 血机制：blood_rank 使用 redis 计数器，失败回退数据库计数
- 错误/重复提交也会落库，便于审计；正确提交后写入 Solve 并回填 submission.solve

提交时必须调用：

- ContestContextService 确认比赛进行中
- Challenge.check_flag 校验 Flag（包含动态 Flag）
- SubmissionService 内部计算得分、提示扣分、血次序，并触发 ScoreboardService.invalidate_cache

------

### 4.5 【machines 靶机管理模块】

必须包含：

- MachineInstance 模型（容器实例记录，已移除动态 Flag 字段）
- Docker 容器启动/销毁（docker_manager，支持 mock）；端口分配使用 redis + db 占用校验
- Celery 定时任务 cleanup_expired_machines：自动销毁超时实例并释放端口
- 启停限速：MachineStartRateThrottle；防止同一题目重复实例
- 端口占用缓存 TTL 可配置，容器镜像前缀/标签通过环境变量注入

必须使用：

```
apps/common/infra/docker_manager.py
apps/common/infra/redis_client.py
```

禁止直接执行 docker shell 命令或绕过 redis 端口分配

------

## 5. **自动生成代码的具体要求**

### 5.1 每生成一个模块，必须包含：

- models.py
- schemas.py
- repo.py
- service.py
- views.py
- urls.py
- tests.py（可放空结构，但不能缺失）

------

### 5.2 视图层必须满足：

- 使用 ModelViewSet 或 ViewSet
- 必须声明权限类
- 必须记录 API 路径
- 必须使用中文文档字符串

示例：

```python
class ChallengeViewSet(ViewSet):
    """
    题目管理接口
    - 提供题目列表、详情、新增、编辑等操作
    """
    permission_classes = [IsAdmin]
```

------

### 5.3 Service 层必须使用事务

涉及：

- 计分
- Flag 校验
- 容器创建/销毁

必须使用：

```python
from django.db import transaction

with transaction.atomic():
    ...
```

------

## 6. **错误处理规范**

所有可预料的错误必须抛 BizError 子类，例如：

- `ContestNotStartedError`
- `TeamAlreadyJoinedError`
- `ChallengeNotAvailableError`
- `WrongFlagError`
- `RateLimitError`

禁止使用：

❌ `raise Exception`
❌ `raise ValidationError`（必须改成 BizValidationError）

------

## 7. **中文注释与文档规范**

所有生成的内容均必须符合：

> **代码中的注释、文档字符串、错误提示、API 文档、测试说明均必须为简体中文（专业术语英文可保留）**

------

## 8. **当用户输入新指令时的响应规范**

Codex 应当：

1. 自动识别当前需要补全的模块
2. 自动扫描现有项目结构（已给出）
3. 根据 SRS 章节顺序生成完整模块骨架或业务逻辑
4. 未出现的文件必须创建
5. 不得覆盖 common/ 目录下已有基础设施文件（除非明确要求）

------

## 9. 当前进度

- accounts：注册/登录（含图形验证码）/找回密码/修改密码/修改邮箱/资料修改/注销均已完成；邮箱验证码走 MailAccount/SMTP
  兜底；默认权限组分配、软删除注销逻辑和核心 API 测试就绪
- contests：比赛创建/筛选/公告/队伍全链路完成，支持邀请码重置、队长移交、比赛导出；记分板使用 Redis 缓存并支持封榜区分前台/后台；路由已嵌套
  challenges
- challenges：题目创建/更新/列表/详情完备，支持分类、子任务、附件上传（file_storage）、提示解锁、静态/动态 Flag（SECRET 哈希）；后台表单
  JS 覆盖；API 测试覆盖题目与提示流转
- submissions：判题服务统一使用 Challenge.check_flag，记录错误/重复提交，动态计分 + 提示扣分 + 血次序（Redis）；提交成功自动失效记分板缓存；API
  测试通过
- machines：靶机启动/停止防重复实例，端口分配使用 Redis + DB 占用缓存；Celery 定时清理超时实例；Docker manager 支持
  mock，测试覆盖核心流程
- 通用/配置：RequestContextMiddleware+logger 写入 logs/ftc.log，统一权限/限流/异常/响应封装完善；DRF Spectacular JWT
  扩展、Redis/邮箱/Docker/Celery 配置可环境化；schema.yaml 已更新
- 翻译与模板：自定义 locale（djangojs）覆盖后台提示，模板覆盖新增用户提示与批量操作布局，base_site 追加“切换账户”入口，预留
  drf_spectacular 模板目录
