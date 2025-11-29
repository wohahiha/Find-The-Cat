# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Find The Cat (FTC)** is a full-featured CTF competition platform built with Django + DRF backend and Vue.js frontend. The platform supports user management, contest creation, challenge management with dynamic Docker environments, team competitions, scoring systems, and leaderboards.

## Development Environment Setup

### Virtual Environment
```bash
# Activate virtual environment
FTCVenv\Scripts\activate       # Windows
source FTCVenv/bin/activate    # Linux/Mac
```

### Environment Variables
- Copy `.env.example` to `.env` (if exists) or configure `.env` directly
- Key variables: `SECRET_KEY`, `DEBUG`, database settings, Redis, Docker, email SMTP

### Database Operations
```bash
# Run migrations
python manage.py migrate

# Create migrations for model changes
python manage.py makemigrations

# Create superuser
python manage.py createsuperuser
```

### Running the Application
```bash
# Development server
python manage.py runserver

# Run tests (with increased throttle rates)
python manage.py test

# Run specific test module
python manage.py test apps.accounts.tests

# Celery worker (for async tasks like machine cleanup)
celery -A Config worker -l info

# Celery beat (for scheduled tasks)
celery -A Config beat -l info
```

## Architecture

### Layered Architecture Pattern

The codebase follows a strict layered architecture to maintain separation of concerns:

1. **Models Layer** (`models.py`): Django ORM models, database schema only
2. **Repository Layer** (`repo.py`): Data access abstraction, inherits from `apps.common.base.base_repo.RepositoryBase`
3. **Service Layer** (`services.py`): Business logic, inherits from `apps.common.base.base_service.ServiceBase`
4. **Schema Layer** (`schemas.py`): DRF serializers for request/response validation
5. **View Layer** (`views.py`): API controllers using ViewSet, minimal logic
6. **URL Layer** (`urls.py`): Route configuration

**Critical Rule**: Never put business logic in views or models. Always use the service layer.

### Module Structure

Each business module in `apps/` follows this structure:
```
apps/<module>/
├── models.py        # Django models
├── repo.py          # Data access layer
├── services.py      # Business logic
├── schemas.py       # DRF serializers
├── views.py         # API controllers
├── urls.py          # Route configuration
├── tests.py         # Test cases
├── admin.py         # Django admin customization
└── migrations/      # Database migrations
```

### Common Infrastructure (`apps/common/`)

All business modules **must** use the common infrastructure rather than implementing their own:

**Base Classes:**
- `base/base_repo.py` - Repository base class
- `base/base_service.py` - Service base class
- `base/base_schema.py` - Schema base class

**Infrastructure Services (`infra/`):**
- `docker_manager.py` - Docker container lifecycle management
- `redis_client.py` - Redis operations (cache, leaderboard, port allocation)
- `email_sender.py` - Email sending (SMTP)
- `file_storage.py` - File upload/download handling
- `jwt_provider.py` - JWT token generation/validation
- `logger.py` - Structured logging with request context

**Utilities (`utils/`):**
- `crypto.py` - Cryptographic operations
- `validators.py` - Custom validation functions
- `time.py` - Timezone and time utilities
- `redis_keys.py` - Redis key naming conventions
- `request_context.py` - Request context variables
- `helpers.py` - Common helper functions

**Cross-cutting Concerns:**
- `exceptions.py` - Business exception hierarchy (`BizError` and subclasses)
- `exception_handler.py` - Global exception handler
- `response.py` - Unified API response format (`success()`, `fail()`, `page_success()`)
- `permissions.py` - Custom DRF permissions (`IsAdmin`, `IsOwner`, `IsSelf`)
- `permission_sets.py` - Permission group definitions and default assignments
- `throttles.py` - Rate limiting classes
- `pagination.py` - Pagination utilities
- `authentication.py` - JWT authentication backend
- `middleware.py` - Request context middleware (adds request_id, user, IP to logs)

## Business Modules

### accounts - User & Authentication
- Custom User model with email, nickname, organization, avatar
- Registration with email verification codes (captcha required)
- Login with JWT tokens (refresh + access)
- Password reset/change, email change
- User profile management
- Account deactivation (soft delete: obfuscate username/email, set inactive)
- Default permission group assignment via `permission_sets`

### contests - Competition Management
- Contest model with time windows, contest types, freeze time, visibility
- Contest announcements (admin → participants)
- Team creation/joining/leaving with invite codes
- Team captain transfer, invite code reset
- Scoreboard service with Redis caching (separate cache for frozen/unfrozen)
- Contest state validation via `ContestContextService`
- Contest data export (teams, members, challenges, submissions, solves, hints, scoreboard)

### challenges - Challenge Management
- Challenge model with categories, difficulty, scoring mode (static/dynamic)
- Multi-flag support via ChallengeTask sub-challenges
- Static vs Dynamic flags (dynamic flags use SECRET + contest/challenge/solver hash)
- Attachment upload/download via `file_storage`
- Hint system with unlock tracking and optional score penalties
- Challenge CRUD via `ChallengeCreate/UpdateService`
- Dynamic scoring with decay (percentage/fixed_step modes)

### submissions - Flag Submission & Scoring
- Submission tracking (correct + incorrect attempts)
- Flag validation via `Challenge.check_flag()` (supports dynamic flags)
- Scoring: static or dynamic decay + hint penalties
- Blood ranking (first n solvers) using Redis counters
- Scoreboard cache invalidation on successful submission
- ChallengeSolve records for correct submissions

### machines - Docker Machine Management
- MachineInstance model tracks container lifecycle
- Docker container start/stop via `docker_manager`
- Port allocation using Redis + DB (prevents conflicts)
- Celery periodic task for cleanup of expired instances
- Rate limiting on machine starts
- Prevents duplicate instances per user/challenge

### problem_bank - Challenge Bank
- Challenge templates for reuse across contests
- Import/export functionality
- Separation from active contest challenges

### system - System Administration
- System-wide settings and maintenance
- Monitoring and status checks

## Error Handling

### BizError Exception Hierarchy

**Never use Django/DRF exceptions directly.** Always throw `BizError` subclasses for predictable business errors:

```python
from apps.common.exceptions import (
    BizError,              # Base: 40000
    AuthError,             # 40100-40199
    PermissionDeniedError, # 40300-40399
    NotFoundError,         # 40400-40499
    ConflictError,         # 40900-40999
    RateLimitError,        # 42900-42999
    ContestNotStartedError,# 46000-46099
    # ... etc
)

# In service layer:
if not contest.is_running():
    raise ContestNotStartedError("比赛尚未开始")
```

The global exception handler (`apps.common.exception_handler.py`) catches all BizError subclasses and returns a unified JSON response with `code`, `message`, and optional `extra` data.

**Error Code Ranges:**
- `40000-40099`: Validation/parameter errors
- `40100-40199`: Authentication errors
- `40300-40399`: Permission errors
- `40400-40499`: Resource not found
- `40900-40999`: Conflicts (duplicate operations)
- `42900-42999`: Rate limiting
- `46000-46099`: Contest state errors
- `47000-47099`: Team/member errors
- `48000-48099`: Challenge/flag errors

## API Response Format

All API endpoints must use the unified response helpers from `apps.common.response`:

```python
from apps.common.response import success, fail, created, page_success

# Success response
return success(data={"user": user_data}, message="操作成功")

# Created response (201)
return created(data={"id": 123}, message="创建成功")

# Paginated response
return page_success(queryset, request, serializer_class=MySerializer)

# Error response (usually via exception, not direct call)
# raise BizError instead of: return fail(code=40001, message="...")
```

**Never return raw DRF `Response()` objects directly in views.**

## Testing

### Test Structure
- Inherits from `rest_framework.test.APITestCase`
- Use `apps.common.tests_utils.AuthenticatedAPIMixin` for authenticated requests
- Override throttle settings to avoid rate limiting in tests:
  ```python
  @override_settings(
      REST_FRAMEWORK={
          **settings.REST_FRAMEWORK,
          "DEFAULT_THROTTLE_RATES": {
              **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
              "login": "1000/min",
              "user_post": "1000/min",
          },
      }
  )
  class MyTestCase(AuthenticatedAPIMixin, APITestCase):
      pass
  ```

### Running Tests
```bash
# All tests
python manage.py test

# Specific module
python manage.py test apps.accounts

# With verbosity
python manage.py test --verbosity=2
```

## Code Style & Conventions

### Language
- **All comments, docstrings, error messages, and documentation must be in Simplified Chinese (简体中文)**
- Technical terms (e.g., "JWT", "Docker", "Redis") remain in English

### Naming Conventions
- Classes: `PascalCase`
- Functions/variables/files: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Type Annotations
Always use type hints for function signatures:
```python
def get_user_by_id(user_id: int) -> User:
    """通过 ID 获取用户"""
    return User.objects.get(id=user_id)
```

### Transactions
Use `@transaction.atomic()` or `with transaction.atomic():` for operations that modify multiple records:
```python
from django.db import transaction

@transaction.atomic()
def submit_flag(user, challenge, flag):
    # Create submission, update score, invalidate cache
    pass
```

## Critical Architectural Rules

1. **Use Common Infrastructure**: Never reimplement Redis, Docker, email, file storage, or crypto operations. Always use `apps.common.infra/` services.

2. **Layered Separation**:
   - Models = data structure only
   - Repo = database queries
   - Service = business logic (transactions, validation, orchestration)
   - View = HTTP request/response handling only

3. **Exception Handling**: Throw `BizError` subclasses for business errors. Let the global handler format responses.

4. **Response Format**: Use `success()`, `created()`, `page_success()` helpers. Never return raw `Response()`.

5. **Authentication**: Use `JWTAuthentication` from `apps.common.authentication`. Check permissions via `permission_classes`.

6. **Permissions**: Use pre-defined permission classes (`IsAuthenticated`, `IsAdmin`, `IsOwner`, `IsSelf`) from `apps.common.permissions`.

7. **Chinese Comments**: All code must have Chinese comments explaining business logic and purpose.

8. **Dynamic Flags**: Generated using `crypto.py` with `SECRET + contest_id + challenge_id + solver_id` hash. Validated in `Challenge.check_flag()`.

9. **Redis Usage**: Use `apps.common.infra.redis_client` and follow key naming conventions in `apps.common.utils.redis_keys`.

10. **Logging**: Use `apps.common.infra.logger` which includes request context (request_id, user, IP) via middleware.

## Docker Machine Management

The machine module manages Docker containers for challenge environments:

- **Port Allocation**: Redis-based with TTL, DB fallback for verification
- **Lifecycle**: Start → Running → Auto-cleanup after timeout
- **Prevention**: No duplicate instances per user/challenge
- **Cleanup**: Celery periodic task (`cleanup_expired_machines`) runs every 5 minutes
- **Mock Mode**: Set `DOCKER_ENABLED=False` in settings for testing without Docker

## Celery Tasks

Celery is used for async/scheduled tasks:

**Configuration**: `Config/celery.py` and `Config/settings.py` (CELERY_* settings)

**Scheduled Tasks**:
- `apps.machines.tasks.cleanup_expired_machines` - Clean up expired Docker containers (every 5 min)

**Running Workers**:
```bash
celery -A Config worker -l info        # Task worker
celery -A Config beat -l info          # Scheduler
celery -A Config worker --pool=solo    # Windows compatibility
```

## Admin Customization

Django admin is heavily customized for FTC:

- **Templates**: Overridden in `templates/admin/` for Chinese UI
- **Localization**: Custom translations in `locale/zh_Hans/LC_MESSAGES/`
- **Challenge Admin**: Enhanced with custom JS (`apps/challenges/static/challenges/js/challenge_admin.js`)
- **Permission Groups**: Default groups defined in `apps.common.permission_sets`

## Schema & API Documentation

- **DRF Spectacular**: Auto-generated OpenAPI schema at `/api/schema/`
- **Swagger UI**: Available at `/api/schema/swagger-ui/`
- **ReDoc**: Available at `/api/schema/redoc/`
- **Custom JWT Docs**: Extension in `apps.common.openapi.py`

## Key Configuration Files

- `Config/settings.py` - Django settings, DRF config, installed apps
- `Config/urls.py` - Root URL configuration
- `Config/celery.py` - Celery app initialization
- `.env` - Environment variables (SECRET_KEY, DB, Redis, Docker, Email)
- `manage.py` - Django management script

## Security Considerations

- Passwords hashed with Django's default hasher
- JWT tokens for authentication (refresh + access)
- CSRF protection enabled
- CORS configured via `django-cors-headers`
- Captcha on registration/login (configurable via `ALLOW_LOGIN_WITHOUT_CAPTCHA`)
- Rate limiting via DRF throttles
- Input validation via DRF serializers
- Dynamic flags use cryptographic hashing
- Container isolation via Docker
- Request context logging for audit trails

## Future Extensions

The architecture is designed for extensibility:

- **Attack-Defense Mode**: Scoreboard and submission systems support custom scoring
- **Kubernetes**: Docker manager can be swapped for K8s orchestration
- **Distributed Machines**: Machine service is decoupled, can run on separate nodes
- **Additional Auth**: OAuth2 interfaces pre-defined
- **WebSocket**: Django Channels for real-time updates (currently polling)
