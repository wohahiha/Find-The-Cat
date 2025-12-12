# Find The Cat（FTC）

**A Comprehensive CTF Center**

------

## 📖 项目简介 / Project Overview
FTC 是一款现代化的 CTF 竞赛与练习平台，支持比赛发布、题库管理、战队/榜单、通知与验证码登录，以及靶机容器的调度。

FTC is a modern CTF platform for contests and practice, covering contest/scoreboard/team management, problem bank, notifications with captcha login, and dynamic machine orchestration.

### ✨ 核心特性 / Key Features
- 🖥️ 现代化界面：Vite 构建的前端，Nginx 提供静态与反代。
- ⚡ 高性能后端：Django + DRF + Channels (ASGI) 搭配 Celery，支撑 WebSocket 实时榜单与异步任务。
- 🚀 一键部署：Docker Compose 集成前后端、Postgres、Redis、Nginx，无需手改 nginx/uvicorn/celery/redis 配置。
- 🔐 安全与可配置：后台 SystemConfig 可设置密钥、HTTPS/CORS/CSRF、邮件、DB/Redis 等；默认收紧安全。
- 🧩 RBAC 与验证码：内置权限字典/角色管理、图形验证码登录、邮件验证码；WebSocket 推送榜单。

------

## 🚀 快速开始 / Quick Start
### 📋 前置要求 / Prerequisites
- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- Git

> - PostgreSQL 15+（已在 Compose 中内置，外部自备可替换）
> - Redis 7+（已在 Compose 中内置，外部自备可替换）

### 🔧 一键部署 / One-Click Deployment
1. 启动容器（**仓库根目录**）：  

   - 生产环境（默认）：  
     `docker compose up --build -d`  
   - 本地调试（暴露 8000）：  
     `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d`

2. 创建后台超级管理员（在后端容器内执行）：  
   `docker compose exec backend python manage.py createsuperuser`

3. 打开浏览器访问后台：

   `http://localhost:8080/admin/`

4. 在 “系统配置” 里完善配置，保存后重启容器：  
   `docker compose restart`

### 🌐 访问地址 / Access URLs

- 前台：`http://localhost:8080/`
- 后台：`http://localhost:8080/admin/`
- API 调试：`http://localhost:8000/api/`

> [!CAUTION]
>
> 生产环境下务必关闭 8000 端口，使用 `docker compose up --build -d`  启动容器，并修改 “系统配置” 令 `DEBUG = False`

------

## 📁 项目结构 / Project Structure
```
FTC/
├── backend/                         # Django 项目与业务代码
│   ├── Config/                      # 全局配置
│   │   ├── settings.py              # Django 设置（安全/DB/Redis/CORS/WS/Celery 等）
│   │   ├── urls.py                  # 路由入口（admin/api/schema/health 等）
│   │   ├── asgi.py / wsgi.py        # ASGI/WSGI 入口
│   │   └── __init__.py
│   ├── apps/
│   │   ├── accounts/                # 账户/登录/注册/头像/邮箱验证码
│   │   ├── auth/                    # 轻量 RBAC 权限/角色
│   │   ├── contests/                # 比赛、公告、榜单
│   │   ├── challenges/              # 题目管理与提示
│   │   ├── submissions/             # 提交与判题记录
│   │   ├── machines/                # 靶机调度/Docker 端口管理/任务
│   │   ├── problem_bank/            # 题库导入导出
│   │   ├── system/                  # 动态配置 SystemConfig、安全覆盖、日志解析
│   │   ├── notifications/           # 通知/定时扫描
│   │   ├── common/                  # 通用：认证/权限/响应/日志/中间件/工具
│   │   └── ...                      # 其他业务模块
│   ├── requirements.txt             # 后端依赖
│   └── manage.py                    # Django 管理命令入口
│
├── frontend/                        # 前端源码（Vite）
│   ├── src/
│   │   ├── assets/                  # 静态资源
│   │   ├── components/              # 通用组件
│   │   ├── pages/                   # 页面
│   │   ├── router/                  # 路由定义
│   │   ├── store/                   # 状态管理
│   │   ├── services/                # API 封装
│   │   └── utils/                   # 工具函数
│   ├── index.html                   # 前端入口
│   ├── package.json / lockfile      # 前端依赖
│   └── vite.config.js               # Vite 配置
│
├── deploy/
│   ├── nginx.Dockerfile             # Nginx 镜像（含前端打包阶段）
│   └── nginx.conf                   # 反代 /api /ws /captcha /admin，托管静态
│
├── docker-compose.yml               # 一键部署（backend/worker/beat/nginx/postgres/redis）
├── docker-compose.dev.yml           # 开发调试叠加（暴露 8000 端口）
├── .env.example                     # Compose 环境变量示例
├── .dockerignore / .gitignore       # 构建与版本控制忽略
├── .dockerignore                    # Docker 构建忽略
├── .gitignore                       # Git 忽略列表
├── LICENSE                          # MIT 许可证
└── README.md                        # 本文件
```

------

## 🤝 贡献指南 / Contributing

我们欢迎所有形式的贡献！

We welcome all forms of contributions!

### 🐛 问题反馈 / Bug Reports

如果您发现了 bug，请在 [Issues](https://github.com/carbofish/A1CTF/issues) 页面提交问题报告。

### 💡 功能建议 / Feature Requests

有好的想法？欢迎在 [Discussions](https://github.com/carbofish/A1CTF/discussions) 中分享！

------

## 📄 许可证 / License

MIT License. Refer to `LICENSE`.
