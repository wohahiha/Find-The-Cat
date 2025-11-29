# LOG_OUTPUT_LEVEL 配置优化说明

## 需求

1. LOG_OUTPUT_LEVEL 字段设置默认值为 "Medium"（第一次启动后台时就有）
2. 配置值时改为下拉框选择（不要输入字符串），从三种日志级别中选择一个

---

## 实现方案

### 1. 设置默认值（Config/settings.py:397-399）

**修改内容**：添加日志系统默认值

```python
# 日志系统默认值（用于首次启动时初始化SystemConfig）
LOG_OUTPUT_LEVEL = "Medium"  # 日志输出级别：Low/Medium/High
LOG_PATH = "logs/"  # 日志文件路径
```

**工作原理**：
- 系统启动时，`ConfigService.ensure_supported_configs()` 会检查数据库
- 如果 LOG_OUTPUT_LEVEL 配置不存在，会调用 `get_supported_default()` 从 settings.py 读取默认值
- 自动创建配置项，值为 "Medium"

---

### 2. 配置下拉框选择（apps/system/admin.py:270-290）

**修改内容**：在 `SystemConfigAdminForm.__init__()` 中添加特殊处理

```python
# 特殊处理：LOG_OUTPUT_LEVEL 使用下拉框选择
if cfg.key == "LOG_OUTPUT_LEVEL":
    # 确定当前值
    if cfg.value and cfg.value.strip():
        initial_value = cfg.value
    else:
        # 数据库无值，从 settings.py 读取默认值
        from django.conf import settings
        initial_value = getattr(settings, "LOG_OUTPUT_LEVEL", "Medium")

    self.fields["value"] = forms.ChoiceField(
        label="配置值",
        required=True,
        choices=[
            ("Low", "Low - 仅错误（ERROR、CRITICAL）"),
            ("Medium", "Medium - 包含警告（WARNING、ERROR、CRITICAL）"),
            ("High", "High - 全部日志（INFO、WARNING、ERROR、CRITICAL）"),
        ],
        initial=initial_value,
        help_text="控制哪些级别的日志会被输出到文件",
    )
```

**下拉框选项**：
- **Low**：仅错误（ERROR、CRITICAL）
- **Medium**：包含警告（WARNING、ERROR、CRITICAL）
- **High**：全部日志（INFO、WARNING、ERROR、CRITICAL）

---

### 3. 添加值验证（apps/system/admin.py:354-358）

**修改内容**：在 `clean_value()` 中添加验证

```python
# 特殊校验：LOG_OUTPUT_LEVEL
if cfg.key == "LOG_OUTPUT_LEVEL":
    if val not in ("Low", "Medium", "High"):
        raise forms.ValidationError("日志级别必须是 Low、Medium 或 High 之一")
    return val
```

**验证规则**：
- 值必须是 "Low"、"Medium" 或 "High"（严格匹配大小写）
- 不接受 "INFO"、"DEBUG"、"low"、"medium" 等其他值

---

## 使用说明

### 第一次启动（全新安装）

1. 运行数据库迁移：
   ```bash
   python manage.py migrate
   ```

2. 启动服务器：
   ```bash
   python manage.py runserver
   ```

3. 系统自动初始化：
   - `apps.system.apps.ConfigsConfig.ready()` 自动执行
   - 调用 `ConfigService.ensure_supported_configs()`
   - 创建 LOG_OUTPUT_LEVEL 配置，默认值为 "Medium"

4. 访问后台查看：
   ```
   http://localhost:8000/admin/configs/systemconfig/
   ```

### 修改日志级别

1. 访问系统配置页面：
   ```
   http://localhost:8000/admin/configs/systemconfig/
   ```

2. 找到 "LOG_OUTPUT_LEVEL" 配置项，点击编辑

3. 看到一个下拉框，包含三个选项：
   - Low - 仅错误（ERROR、CRITICAL）
   - Medium - 包含警告（WARNING、ERROR、CRITICAL）
   - High - 全部日志（INFO、WARNING、ERROR、CRITICAL）

4. 选择需要的级别，点击保存

5. 修改后立即生效（下次写入日志时使用新级别）

---

## 测试验证

### 测试1：验证默认值

```bash
python test_log_output_level.py
```

**预期结果**：
```
1. 检查 settings.py 默认值:
  LOG_OUTPUT_LEVEL = 'Medium'
  ✅ LOG_OUTPUT_LEVEL 默认值正确设置为 'Medium'

2. 检查数据库中的配置:
  键: LOG_OUTPUT_LEVEL
  值: 'Medium'（或其他已设置的值）
  ✅ 配置存在
```

### 测试2：兼容旧值

如果数据库中有旧的小写值（如 "high"、"medium"、"low"），运行：

```bash
python update_log_output_level.py
```

**功能**：
- 自动将小写值转换为首字母大写（high → High）
- 空值设为默认值 "Medium"
- 未知值设为默认值 "Medium"

---

## 技术细节

### 初始化流程

```
1. Django 启动
   ↓
2. apps.system.apps.ConfigsConfig.ready()
   ↓
3. ConfigService.ensure_supported_configs()
   ↓
4. 检查数据库中是否存在 LOG_OUTPUT_LEVEL
   ↓
5a. 存在 → 同步元数据（类型、描述等），不覆盖值
5b. 不存在 → 创建配置，值从 settings.LOG_OUTPUT_LEVEL 读取
```

### Form 渲染流程

```
1. 访问配置编辑页面
   ↓
2. SystemConfigAdminForm.__init__()
   ↓
3. 检查 cfg.key == "LOG_OUTPUT_LEVEL"
   ↓
4. 创建 ChoiceField 替换默认的 CharField
   ↓
5. 设置 choices=[("Low", ...), ("Medium", ...), ("High", ...)]
   ↓
6. 设置 initial=当前值或默认值
   ↓
7. 渲染下拉框
```

### 值保存流程

```
1. 用户选择下拉框选项并提交
   ↓
2. SystemConfigAdminForm.clean_value()
   ↓
3. 检查 cfg.key == "LOG_OUTPUT_LEVEL"
   ↓
4. 验证 val in ("Low", "Medium", "High")
   ↓
5. 返回值（字符串格式）
   ↓
6. 保存到数据库 value 字段
```

---

## 日志级别说明

### Low - 仅错误

**包含级别**：ERROR、CRITICAL

**适用场景**：
- 生产环境，需要最小化日志量
- 只关注严重错误
- 磁盘空间有限

**示例日志**：
```
2025-11-29 12:00:00 ERROR django.request Internal Server Error: /api/users/
2025-11-29 12:01:00 CRITICAL apps.system 数据库连接失败
```

---

### Medium - 包含警告（推荐）

**包含级别**：WARNING、ERROR、CRITICAL

**适用场景**：
- 生产环境默认级别
- 需要关注潜在问题
- 平衡日志量和信息量

**示例日志**：
```
2025-11-29 12:00:00 WARNING apps.accounts 用户登录失败：密码错误
2025-11-29 12:00:01 ERROR django.request Internal Server Error: /api/users/
2025-11-29 12:01:00 CRITICAL apps.system 数据库连接失败
```

---

### High - 全部日志

**包含级别**：INFO、WARNING、ERROR、CRITICAL

**适用场景**：
- 开发环境
- 问题排查
- 审计追踪

**示例日志**：
```
2025-11-29 12:00:00 INFO apps.accounts 用户登录成功 [admin|1|127.0.0.1|/api/auth/login/]
2025-11-29 12:00:00 WARNING apps.accounts 用户登录失败：密码错误
2025-11-29 12:00:01 ERROR django.request Internal Server Error: /api/users/
2025-11-29 12:01:00 CRITICAL apps.system 数据库连接失败
```

---

## 文件变更清单

### 修改的文件

1. **Config/settings.py**
   - 添加 `LOG_OUTPUT_LEVEL = "Medium"`（第398行）
   - 添加 `LOG_PATH = "logs/"`（第399行）

2. **apps/system/admin.py**
   - 添加 LOG_OUTPUT_LEVEL 下拉框处理（第270-290行）
   - 添加 LOG_OUTPUT_LEVEL 值验证（第354-358行）

### 新增的测试文件

1. **test_log_output_level.py** - 验证配置和下拉框
2. **update_log_output_level.py** - 更新旧值到新格式

---

## 常见问题

### Q1: 修改日志级别后需要重启服务吗？

**A:** 不需要。日志级别在每次写入日志时动态读取，修改后立即生效。

### Q2: 如何恢复默认值？

**A:** 在后台编辑页面选择 "Medium"，或者删除该配置项（系统会在下次启动时自动创建并设为 Medium）。

### Q3: 能否自定义日志级别？

**A:** 不建议。系统设计了三个标准级别（Low/Medium/High），已经覆盖常见场景。如需自定义，需要修改：
1. settings.py 的默认值
2. admin.py 的 choices 选项
3. clean_value() 的验证逻辑
4. logger.py 的级别映射逻辑

### Q4: 旧的小写值（如 "high"）还能用吗？

**A:** 不能。运行 `update_log_output_level.py` 将旧值转换为新格式（High）。

---

## 总结

✅ **默认值**：settings.py 设置 LOG_OUTPUT_LEVEL = "Medium"
✅ **下拉框**：三个选项（Low/Medium/High），带说明
✅ **值验证**：严格校验，只接受标准值
✅ **自动初始化**：首次启动自动创建，默认值 "Medium"
✅ **向后兼容**：提供更新脚本转换旧值

---

**修改完成时间**: 2025-11-29
**测试状态**: ✅ 全部通过
**可部署状态**: ✅ 生产就绪
