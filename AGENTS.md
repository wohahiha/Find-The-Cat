# **AGENTS.md**

> **本文件用于统一整个代码生成代理（Codex）的行为规范，确保在本项目中自动生成的所有代码均满足：可维护、高内聚、低耦合、可扩展，并严格遵守
FTC 项目的技术架构与 SRS 定义。**

------

## 0. 总则

1. 本仓库为 **Find The Cat（FTC）CTF 竞赛平台后端**，基于 **Django + DRF** 实现，采用分层和模块化设计。
2. **一切业务行为必须严格对齐 SRS 与需求文档**，不得凭空臆造需求。
3. 所有新增代码必须：
    - 使用 **简体中文注释**（必要技术术语保留英文）；
    - 遵守统一的 **错误处理、权限、限流、响应格式**；
    - 保持 **高内聚，低耦合**。
4. 不确定的地方，宁可 **保守、留 TODO 注释**，也不要拍脑袋造协议或字段。

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
│
├─ Config/                    # Django 项目配置包
│   ├─ __init__.py
│   ├─ settings.py            # 全局配置（数据库/DRF/JWT/异常处理/限流、本地化）
│   ├─ urls.py                # 全局路由入口
│   ├─ asgi.py                # ASGI 网关（未来接入 WebSocket）
│   └─ wsgi.py                # WSGI 网关（部署时使用）
│
├─ apps/                      # 所有业务模块（分 app）
│   ├─ __init__.py
│   ├─ accounts/              # 用户与认证模块
│   │   ├─ __init__.py
│   │   ├─ admin.py           # Django admin 注册与展示
│   │   ├─ apps.py            # Django app 配置
│   │   ├─ backends.py        # 认证后端（用户名/邮箱登录）
│   │   ├─ models.py          # 用户、发信账号等模型
│   │   ├─ repo.py            # 账号数据访问层
│   │   ├─ schemas.py         # Serializer（注册、登录、资料、邮箱验证码）
│   │   ├─ services.py        # 账号业务逻辑（注册、登录、资料修改、邮件）
│   │   ├─ signals.py         # 信号（创建默认权限组等）
│   │   ├─ tests.py           # 账号 API/流程测试
│   │   ├─ urls.py            # 账号路由配置
│   │   ├─ utils.py           # 账号辅助函数（验证码等）
│   │   ├─ views.py           # 账号接口层
│   │   └─ migrations/        # 数据库迁移记录
│   │       ├─ __init__.py
│   │       ├─ 0001_initial.py
│   │       ├─ 0002_alter_user_options_user_avatar_user_bio_user_country_and_more.py
│   │       ├─ 0003_mailaccount.py
│   │       ├─ 0004_playeruser_staffuser_alter_user_avatar_and_more.py
│   │       ├─ 0005_alter_user_managers_user_account_type.py
│   │       ├─ 0006_create_default_groups.py
│   │       └─ 0007_ensure_default_groups_permissions.py
│   │
│   ├─ contests/              # 比赛管理（比赛、公告、队伍、记分板）
│   │   ├─ __init__.py
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py          # Contest、Team 等模型
│   │   ├─ repo.py            # 比赛、公告、队伍仓储
│   │   ├─ schemas.py         # 比赛/公告/队伍序列化与校验
│   │   ├─ services.py        # 比赛状态、公告发布、队伍生命周期
│   │   ├─ tests.py           # 比赛与队伍 API 测试
│   │   ├─ urls.py            # 比赛路由
│   │   ├─ views.py           # 比赛与队伍接口
│   │   └─ migrations/
│   │       ├─ __init__.py
│   │       ├─ 0001_initial.py
│   │       ├─ 0002_alter_contest_created_at_alter_contest_description_and_more.py
│   │       └─ 0003_contestannouncement.py
│   │
│   ├─ challenges/            # 题目与题库
│   │   ├─ __init__.py
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py          # Challenge、ChallengeTask、ChallengeAttachment
│   │   ├─ repo.py            # 题目与附件/子任务仓储
│   │   ├─ schemas.py         # 题目/Flag 校验与序列化
│   │   ├─ services.py        # 题目 CRUD、Flag 校验、提交记录
│   │   ├─ tests.py           # 题目 API 测试
│   │   ├─ urls.py            # 题目路由
│   │   ├─ views.py           # 题目接口
│   │   └─ migrations/
│   │       ├─ __init__.py
│   │       ├─ 0001_initial.py
│   │       ├─ 0002_alter_challenge_author_alter_challenge_base_points_and_more.py
│   │       └─ 0003_challengetask_challengeattachment_flagtype.py
│   │
│   ├─ common/                # 通用基础设施层（全局复用）
│   │   ├─ __init__.py
│   │   ├─ base/              # 三大基类：仓储、服务、Schema
│   │   │   ├─ __init__.py
│   │   │   ├─ base_repo.py
│   │   │   ├─ base_schema.py
│   │   │   └─ base_service.py
│   │   ├─ infra/             # 底层工具 & 基础设施封装
│   │   │   ├─ __init__.py
│   │   │   ├─ docker_manager.py
│   │   │   ├─ email_sender.py
│   │   │   ├─ file_storage.py
│   │   │   ├─ jwt_provider.py
│   │   │   ├─ logger.py       # 日志封装（级别/格式/文件输出）
│   │   │   └─ redis_client.py
│   │   ├─ utils/             # 通用工具函数（严格无业务逻辑）
│   │   │   ├─ __init__.py
│   │   │   ├─ crypto.py
│   │   │   ├─ helpers.py
│   │   │   ├─ time.py
│   │   │   └─ validators.py
│   │   ├─ authentication.py  # JWT 认证入口
│   │   ├─ exception_handler.py # 全局异常处理器
│   │   ├─ exceptions.py      # 业务异常体系
│   │   ├─ pagination.py      # 统一分页器
│   │   ├─ permission_sets.py # 默认权限集声明
│   │   ├─ permissions.py     # 自定义权限
│   │   ├─ response.py        # 统一 API 响应格式
│   │   └─ throttles.py       # 自定义限速
│   │
│   ├─ submissions/           # Flag 提交（记录、判题日志、排行榜失效）
│   │   ├─ __init__.py
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py
│   │   ├─ repo.py
│   │   ├─ schemas.py
│   │   ├─ services.py        # 判题、血次序、记分板缓存失效
│   │   ├─ tests.py
│   │   ├─ urls.py
│   │   └─ views.py
│   │
│   ├─ machines/              # 靶机实例管理（Docker 容器）
│   │   ├─ __init__.py
│   │   ├─ admin.py
│   │   ├─ apps.py
│   │   ├─ models.py          # MachineInstance（已移除动态 Flag 字段）
│   │   ├─ repo.py
│   │   ├─ schemas.py
│   │   ├─ services.py        # 启停靶机、端口分配
│   │   ├─ tests.py
│   │   ├─ urls.py
│   │   └─ views.py
│   │
│   └─ ...                    # 未来按 SRS 拓展
│
├─ locale/                    # 自定义翻译目录（覆盖后台 JS 文本）
│   └─ zh_Hans/
│       └─ LC_MESSAGES/
│           ├─ djangojs.po
│           └─ djangojs.mo
│
├─ templates/                 # 模板覆盖（Django Admin）
│   └─ admin/
│       ├─ actions.html       # 批量操作区域布局覆盖
│       ├─ base_site.html     # 后台首页标题/切换账户入口
│       └─ auth/
│           └─ user/
│               └─ add_form.html  # 新增用户页提示文案覆盖
│
├─ docs/                      # 项目文档（SRS、设计文档等）
│   ├─ Find The Cat 需求分析与设计.md
│   └─ FTC 软件需求规格说明书.docx
│
└─ FTCVenv/                   # Python 虚拟环境（可忽略）

```

生成顺序必须严格遵守 SRS 模块顺序：

> **accounts → contests → challenges → submissions → machines**

如当前模块不存在（如 contests/），Codex 必须自动创建目录和基础文件。

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
2. **所有代码文件均需使用中文注释。**
3. 业务接口统一使用：
    - 权限：`IsAuthenticated`、`IsAdmin`、`IsOwner`、`IsSelf` 等
    - 统一响应：`success/created/fail/page_success`
    - 异常：必须抛 `BizError` 子类，而不是 Django/DRF 默认异常。
4. 控制器(ViewSet) 必须遵守：
    - RESTful 风格
    - 不直接返回 DRF Response，统一调用 `success()`
    - 业务错误使用异常体系（如 WrongFlagError、ContestNotStartedError）
5. Model、Serializer、ViewSet、Service、Repository 必须拆分清晰。

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

**禁止将所有逻辑写在 views.py**。
视图层只做参数接收和调用 service 层。

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
  ├─ infra/           # 基础设施（redis、file_storage、logger、docker_manager）
  ├─ utils/           # 工具方法（crypto、validators…）
  ├─ exceptions.py    # BizError 体系
  ├─ permissions.py   # 权限体系
  ├─ pagination.py    # 统一分页器
  ├─ response.py      # 统一响应
  └─ exception_handler.py  # 全局异常处理器
```

写业务模块时必须优先使用：

- **base_service.py**：业务类继承 ServiceBase
- **base_repo.py**：数据访问层基类
- **jwt_provider** / **crypto**：用于 Token、签名等
- **docker_manager**：管理靶机生命周期
- **redis_client**：缓存、排行榜

禁止直接 import Django ORM 之外的系统库，例如：

❌ 在 Controller 内直接操作 Redis
❌ 在 ViewSet 内直接执行 docker 命令

必须使用 common/infra 中的封装。

------

## 4. **模块级规范（按 SRS）**

Codex 在生成对应模块代码时必须遵守以下约束。

------

### 4.1 【accounts 用户模块】

必须提供：

- User 模型拓展
- 注册 / 登录 / 找回密码
- 邮箱验证码
- 角色与权限
- 用户资料接口
- 队长权限 IsLeader（Team 模型后续才出现，但 accounts 必须预留字段）

依赖内容：

- JWTAuthentication
- LoginRateThrottle
- AuthError / InvalidCredentialsError
- Schema 层必须严格校验邮件、密码格式

------

### 4.2 【contests 比赛模块】

必须包含：

- Contest 模型（名称、时间、赛制、封榜时间…）
- 比赛状态判定（未开始 / 已结束 / 封榜）
- 比赛公告
- 比赛-题目多对多关联
- 比赛筛选（进行中 / 已结束）

禁止逻辑写在 Serializer 或 View 中。

所有状态判断必须写入 ContestService：

- `ensure_contest_available()`
- `ensure_contest_not_ended()`
- `ensure_contest_started()`

------

### 4.3 【challenges 题目模块】

必须实现：

- Challenge 模型（标题、描述、类型、难度、标签）
- 多子任务题（ChallengeTask）
- 静态 Flag + 动态 Flag（注入靶机环境）
- 附件上传
- Checker 脚本可选

Flag 校验逻辑必须写在：

```
services/challenge_service.py
```

并且抛出：

- WrongFlagError
- FlagFormatError
- ChallengeAlreadySolvedError

------

### 4.4 【submissions 提交计分模块】

必须包含：

- Submission 模型（提交记录）
- Solve 模型（正确解题记录）
- 计分逻辑：静态/动态
- 排行榜维护（可使用 redis_client）
- n 血机制（First Blood / Second Blood…）

提交时必须调用：

- ContestService（检查状态）
- ChallengeService（检查 Flag）
- ScoreService（负责计算分值）

------

### 4.5 【machines 靶机管理模块】

必须包含：

- MachineInstance 模型（容器实例记录）
- Docker 容器启动/销毁
- 端口分配
- 动态 Flag 注入
- 启停限速：MachineStartRateThrottle

必须使用：

```
apps/common/infra/docker_manager.py
apps/common/infra/redis_client.py
```

禁止直接执行 docker shell 命令。

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

> **代码中的注释、文档字符串、错误提示、API 文档、测试说明均必须为简体中文（专业术语英文可保留）。**

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

- accounts：注册/登录/验证码/资料修改/密码邮箱修改/注销接口已就绪，APITestCase 覆盖核心流程。
- contests：比赛创建/状态筛选/公告/队伍全链路完成；记分板支持 Redis 缓存并在解题/提交后自动失效；API 测试通过。
- challenges：题目创建/更新/列表/详情/提交 Flag 完成，支持子任务、附件、静态/动态 Flag（哈希生成）、附件上传接口；后台表单优化；API 与附件上传测试通过。
- submissions：提交记录/判题/血次序/排行榜缓存失效逻辑完成，支持动态 Flag 判题，API 测试通过。
- machines：靶机实例管理完成，端口分配与 Docker 启停占位，动态 Flag 字段已移除，测试使用 Docker mock。
- 通用：存储支持本地/OSS，日志支持级别/格式/文件输出，JWT 封装与工具库（crypto/helpers/time/validators）完善；schema.yaml 已更新。
- 翻译与模板：自定义 locale（djangojs）覆盖后台提示，模板覆盖新增用户提示与批量操作布局，base_site 追加“切换账户”入口。
