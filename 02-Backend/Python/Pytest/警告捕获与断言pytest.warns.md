---
tags: [pytest, testing, python, fixture, assertion, exception, scope, markers, cli, warnings]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 警告捕获与断言pytest.warns.md
---
# 警告捕获与断言pytest.warns

## 📌 一句话总结
> 警告是Python生态中用于**标记废弃（Deprecation）、使用风险（RuntimeWarning）或非致命错误**的重要机制。与异常不同，警告**不会中断程序执行**，因此验证它们更具挑战性。PyTest通过`pytest.warns`上下文管理器和内置`recwarn`固件，提供了一套完整的警告捕获与断言体系。

我将从**核心断言语法**、**`recwarn`固件深度使用**、**警告过滤器（将警告提升为错误）**以及**与`pytest.raises`的核心区别**四个维度，为你彻底讲透警告测试。

## 🎯 核心概念

### 1. 核心断言：`pytest.warns` 上下文管理器

`pytest.warns`的用法与`pytest.raises`高度相似，但有一个关键区别：**代码执行会继续**，警告被捕获后，测试继续进行。

#### 基础用法：仅匹配警告类型
```python
import warnings
import pytest

def deprecated_function():
    warnings.warn("此功能将在 v3.0 中移除", DeprecationWarning)
    return 42

def test_deprecated_warning():
    # 断言函数会触发 DeprecationWarning
    with pytest.warns(DeprecationWarning):
        result = deprecated_function()
    
    # 注意：即使警告被捕获，函数返回值依然存在，可继续断言
    assert result == 42
```

#### 进阶用法：文本匹配（正则表达式）
使用`match`参数验证警告消息内容，确保不是无关的废弃警告。

```python
def test_deprecated_with_message():
    with pytest.warns(DeprecationWarning, match=r"v3\.0 中移除"):
        deprecated_function()
```

#### 捕获多个警告（`record`参数）
当一段代码可能触发**多个警告**时，使用`record=True`将警告记录为列表，逐一断言。

```python
def multi_warning_func():
    warnings.warn("警告A", UserWarning)
    warnings.warn("警告B", RuntimeWarning)

def test_multiple_warnings():
    with pytest.warns(UserWarning) as record:
        multi_warning_func()
    
    # 验证是否只有一个 UserWarning 被触发
    assert len(record) == 1
    assert record[0].message.args[0] == "警告A"
    
    # 但注意：RuntimeWarning 没有被捕获，会正常输出到控制台
```

**注意**：`record`列表只捕获**匹配指定警告类型**（此处为`UserWarning`）的警告，其他类型（如`RuntimeWarning`）会照常打印。

### 2. `recwarn` 固件：跨测试步骤的警告收集

与`pytest.warns`的局部作用域不同，`recwarn`是一个内置固件，可以在**测试函数的不同步骤间**收集所有警告（无论类型），并允许你进行批量断言。

```python
def test_recwarn_fixture(recwarn):
    # 步骤1：执行第一段代码
    deprecated_function()
    
    # 步骤2：执行第二段代码
    warnings.warn("另一个警告", UserWarning)
    
    # 步骤3：全局检查所有收集到的警告
    assert len(recwarn) == 2
    
    # 检查特定警告
    deprecation_warnings = [w for w in recwarn if w.category == DeprecationWarning]
    assert len(deprecation_warnings) == 1
    assert "v3.0" in str(deprecation_warnings[0].message)
    
    # recwarn 会在测试结束后自动清空，无需手动清理
```

**`recwarn` 常用属性**：
- `w.category`：警告类（如`DeprecationWarning`）。
- `w.message`：警告消息对象（用`str()`获取文本）。
- `w.filename`和`w.lineno`：发出警告的文件和行号（用于调试）。

### 3. 警告过滤器：将警告升级为错误（`filterwarnings`）

这是保证代码质量的最强力手段。通过将**特定警告视为错误**，可以强制开发者在CI中修复废弃API的使用，防止警告被忽略。

#### 方式一：命令行参数
```bash
# 将所有警告视为错误（测试遇到任何警告则 FAILED）
pytest -W error

# 仅将 DeprecationWarning 视为错误
pytest -W "error::DeprecationWarning"

# 忽略特定模块的特定警告
pytest -W "ignore:deprecated:DeprecationWarning:my_legacy_module"
```

#### 方式二：`pyproject.toml` 全局配置（推荐）
```toml
[tool.pytest.ini_options]
filterwarnings = [
    "error::DeprecationWarning",                # DeprecationWarning 视为错误
    "ignore::PendingDeprecationWarning",        # 忽略尚未定案的废弃警告
    "ignore:unclosed:ResourceWarning",          # 忽略资源泄露警告（特定场景）
]
```

#### 方式三：单测试/单类级别的标记控制（最精细）
```python
import pytest

# 此测试函数将忽略 DeprecationWarning
@pytest.mark.filterwarnings("ignore:deprecated:DeprecationWarning")
def test_legacy_code():
    deprecated_function()  # 不会失败，也不会打印警告
    assert True

# 此测试类中的所有方法都将 DeprecationWarning 视为错误
@pytest.mark.filterwarnings("error::DeprecationWarning")
class TestStrictDeprecation:
    def test_new_code(self):
        # 若此处触发 DeprecationWarning，测试将 FAILED
        pass
```

### 4. `pytest.warns` vs `pytest.raises` 的核心区别

| 维度 | **`pytest.raises`（异常）** | **`pytest.warns`（警告）** |
| :--- | :--- | :--- |
| **程序执行流** | **中断**：抛出异常后，`with`块内后续代码不执行 | **继续**：警告发出后，代码继续执行下一行 |
| **默认行为** | 若未抛出异常，测试**FAILED** | 若未发出警告，测试**FAILED**（类似） |
| **捕获后断言** | 使用`exc_info.value`访问异常对象属性 | 使用`record`列表或`recwarn`固件访问`Warning`对象 |
| **典型用途** | 验证错误处理路径（如参数非法） | 验证迁移计划（如API废弃）、资源回收（ResourceWarning） |

### 5. 极易踩中的 3 个致命陷阱

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **`pytest.warns` 捕获不到第三方库内部的 `PendingDeprecationWarning`** | PyTest默认**忽略** `PendingDeprecationWarning`（因其不影响当前运行），需显式开启。 | 在 `pyproject.toml` 中添加：`filterwarnings = ["always::PendingDeprecationWarning"]`，或使用 `pytest -W always`。 |
| **`recwarn` 中检查 `len(recwarn)` 为0，但肉眼能看到警告打印** | 警告在 `recwarn` 收集**之前**已经被 `sys.stderr` 输出，但未被收集。可能因为警告未被触发，或代码在 `with` 块外部。 | 确保所有可能触发警告的代码均在 `recwarn` 固件生效后的执行路径内（即测试函数主体内）。检查是否错误地在 `recwarn` 声明前执行了代码。 |
| **`filterwarnings = "error"` 导致测试因第三方库的无害警告而全部变红** | 升级过于激进，将整个测试套件阻塞。 | 使用**精准过滤**：只对特定模块或特定警告类型设置为 `error`，并为旧代码库保留 `ignore` 白名单。 |

### 6. 实战组合：测试“废弃警告 + 返回值逻辑”

最实用的场景是：函数在返回正确值的同时，会发出一个废弃警告。

```python
import warnings

def old_api_call():
    warnings.warn("old_api_call is deprecated, use new_api_call", DeprecationWarning)
    return {"status": "success", "data": "legacy"}

def test_old_api_with_deprecation():
    with pytest.warns(DeprecationWarning, match="use new_api_call") as record:
        result = old_api_call()
    
    # 验证1：只发出了一个警告
    assert len(record) == 1
    # 验证2：返回值逻辑正确
    assert result["status"] == "success"
    # 验证3：警告消息精确匹配
    assert "old_api_call" in str(record[0].message)
```

### 7. 高级技巧：测试“没有发出警告”

有时你需要确保特定代码路径**不会**意外触发警告。虽然 `pytest.warns` 要求必须有警告，但结合 `recwarn` 可以反向断言：

```python
def test_no_warning_emitted(recwarn):
    # 执行一个不应该有警告的操作
    result = safe_function()
    
    # 断言：没有收集到任何警告
    assert len(recwarn) == 0
    # 或断言特定类型未出现
    assert not any(w.category == DeprecationWarning for w in recwarn)
```

### 8. 决策矩阵：何时用哪种方式？

| 场景 | 推荐方案 | 理由 |
| :--- | :--- | :--- |
| **单行代码触发单个警告** | `pytest.warns(Warning, match=...)` | 最简洁，上下文明确 |
| **多行代码触发多个不同警告** | `recwarn` 固件 + 批量断言 | 灵活收集，可按类型筛选 |
| **全局规范（CI强制）** | `pyproject.toml` 中的 `filterwarnings = ["error::DeprecationWarning"]` | 强制团队清理废弃API |
| **仅为某个特定测试放宽限制** | `@pytest.mark.filterwarnings("ignore::...")` | 保持全局严格，局部例外 |

你现在是想**验证某个第三方库的废弃警告**（确保升级时收到通知），还是想**在CI中强制将所有`DeprecationWarning`视为错误**来提升代码质量？告诉我具体场景，我可以为你生成一段包含`filterwarnings`配置和`pytest.warns`组合使用的完整代码模板。你选哪个？

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[assert语句的增强输出与重写原理]]
- [[内置作用域层级]]
- [[内置标记]]
- [[pytest命令行参数详解]]
- [[异常断言（pytest.raises）与异常文本匹配]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, assertion, exception, scope, markers, cli, warnings）
> - [+] 新增 H1「警告捕获与断言pytest.warns」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
