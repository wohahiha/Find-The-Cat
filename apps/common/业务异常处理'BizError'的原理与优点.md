# BizError 设计原理与优点总结

## 一、BizError 的设计原理

### 1. 使用类属性作为“声明式默认值”

- `default_code`
- `default_message`
- `http_status`

这些是 **类属性（class attribute）** ，而非实例属性
当实例访问 `self.default_code` 时：

1. Python 优先查实例属性 → 找不到
2. 再查子类类属性（如 AuthError.default_code）
3. 再查父类类属性（BizError.default_code）

因此：

- 子类只需“声明”默认值，不需要写 `__init__`
- 父类的 `__init__` 在运行时会自动读取子类的 class attribute

这实现了 **“声明式异常体系”**

---

### 2. 父类 __init__ 实现统一初始化逻辑

```python
def __init__(self, message=None, code=None, *, extra=None):
    self.code = code if code is not None else self.default_code
    self.message = message if message is not None else self.default_message
    self.extra = extra or {}
    super().__init__(self.message)
```

业务逻辑：

- 若调用方未传 `message/code` → 使用子类声明的默认值
- 若调用方传入参数 → 临时覆盖默认值

所有实例属性：

- `self.code`
- `self.message`
- `self.extra`

均在基类统一设置，**子类无需写重复代码**

---

### 3. 利用 Python 的属性查找链（MRO）

访问 `self.default_code` 实际运行流程：

```
instance → AuthError → BizError → Exception → BaseException → object
```

因此默认值总是能被解析到

这让子类可以“声明”，父类负责“使用”，实现逻辑与数据分离

---

## 二、BizError 的优点

### ✔ 1. 子类无需写 __init__、无需 super()

只需：

```python
class AuthError(BizError):
    default_code = 40100
    default_message = "认证失败"
```

即可拥有完整初始化行为：

- code
- message
- extra
- http_status
- Exception 基类初始化

极大减少重复代码（避免 N 个子类重复写 super()).

---

### ✔ 2. 默认行为与覆盖行为并存

默认：

```python
raise AuthError()
```

使用声明式默认值

可选覆盖：

```python
raise AuthError("账号被封禁", code=40110)
```

保持语义一致（还是 AuthError），但允许更具体描述

这是实际工程中非常有用的能力

---

### ✔ 3. 统一异常处理机制

异常处理器只需要判断：

```python
isinstance(exc, BizError)
```

然后读取：

- exc.code（业务码）
- exc.message（前端提示）
- exc.http_status（HTTP 状态）
- exc.extra（附加数据）

即可生成统一格式响应：

```json
{ "code": 40100, "message": "认证失败", "data": {...} }
```

---

### ✔ 4. 避免类属性与实例属性冲突

因为：

- 默认值放类属性
- 实例属性只在初始化时拷贝一次

确保：

- 默认值可被子类覆盖
- 实例属性不会误遮挡类属性

设计简洁、安全

---

### ✔ 5. 高扩展性（声明式 + 最小重复）

未来新增异常：

```python
class ContestNotStartedError(ContestError):
    default_code = 46001
    default_message = "比赛未开始"
```

不需要多写一行逻辑

几十个异常类 → 都非常优雅、清晰

---

## 三、总结

BizError 的核心思想：
> **“用类属性声明语义，用父类 __init__ 统一赋值，用实例属性输出运行状态”**

这是 Python 中管理大量业务异常最优雅、最可维护的方式

