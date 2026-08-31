---
tags: [pytest, testing, python, parametrize, coverage, assertion, exception, markers, xfail, data-driven]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 异常断言（pytest.raises）与异常文本匹配.md
---
# 异常断言（pytest.raises）与异常文本匹配

## 📌 一句话总结
> 异常断言是验证代码**错误处理路径**的核心手段。`pytest.raises`不仅让你精确捕获预期异常，还能通过**文本匹配**（正则表达式）和**属性检查**，确保异常携带了正确的错误信息。我将其拆解为**核心语法**、**文本匹配策略**、**深入对象属性**以及**与其他机制的对比**。

## 🎯 核心概念

### 1. 核心语法：`with` 上下文管理器

`pytest.raises` 通常以 `with` 语句形式使用，将**唯一会抛出异常的那一行代码**包裹在内。若该行未抛出指定异常，测试将直接**失败（FAILED）**。

```python
import pytest

def divide(a, b):
    if b == 0:
        raise ValueError("除数不能为零！")
    return a / b

def test_divide_by_zero():
    # 基础用法：仅检查异常类型
    with pytest.raises(ValueError):
        divide(10, 0)
```

**关键原则**：`with` 块内**只放**触发异常的那一行。若放入多行，则无法确定是哪一行抛出的异常，且可能掩盖前置条件的错误。

### 2. 异常文本匹配：`match` 参数（正则表达式）

仅匹配异常类型通常不够（例如，不同的`ValueError`可能代表不同的业务错误）。使用 `match` 参数对异常信息进行**正则表达式**匹配，确保错误信息符合预期。

```python
def test_divide_by_zero_message():
    # 使用 match 匹配错误文本（支持正则）
    with pytest.raises(ValueError, match="除数不能为零"):
        divide(10, 0)

    # 进阶：匹配部分文本或使用正则通配符
    with pytest.raises(ValueError, match=r"除数.*零"):
        divide(10, 0)
        
    # 若异常信息不匹配，测试失败并显示：
    #   ValueError: 除数不能为零！ does not match pattern '除.*数'
```

**何时必须使用 `match`？**
- 捕获 `Exception` 基类时，必须靠文本区分错误类型。
- 验证用户友好的错误提示（如API返回的`{"error":"Invalid token"}`）。
- 确保异常信息未泄露敏感堆栈信息。

### 3. 深入异常对象：`exc_info` 与属性检查

有些异常（如自定义类或网络响应错误）除了`message`外，还携带了**状态码（status_code）**、**错误码（error_code）**或**原始数据（raw_data）**。此时需要用 `as exc_info` 捕获异常实例，再进行额外断言。

```python
class APIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(message)

def fetch_user(uid):
    if uid < 0:
        raise APIError(400, "用户ID无效")

def test_api_error_attributes():
    # 1. 捕获异常实例到 exc_info
    with pytest.raises(APIError) as exc_info:
        fetch_user(-1)
    
    # 2. 获取异常对象
    error = exc_info.value
    
    # 3. 对异常属性进行精准断言
    assert error.status_code == 400
    assert "无效" in error.message
```

**`exc_info` 的其他用途**：
- `exc_info.type`：异常类（用于调试）。
- `exc_info.traceback`：回溯对象（极少需要直接操作）。

### 4. 参数化异常测试（数据驱动）

当同一函数因不同输入抛出**相同异常但不同消息**时，使用参数化可以极大减少代码重复。

```python
@pytest.mark.parametrize("invalid_input, expected_msg", [
    (0, r"除数不能为零"),
    (-5, r"除数不能为负数"),  # 假设有此逻辑
])
def test_divide_invalid_inputs(invalid_input, expected_msg):
    with pytest.raises(ValueError, match=expected_msg):
        divide(10, invalid_input)
```

### 5. 与 `xfail(raises=...)` 的关键区别

| 机制 | 使用场景 | 失败处理 |
| :--- | :--- | :--- |
| **`pytest.raises`** | **主动验证**：当前功能**必须**抛出特定异常，否则业务逻辑错误 | 若不抛出，测试 **FAILED** |
| **`@pytest.mark.xfail(raises=ZeroDivisionError)`** | **被动标记**：预知该测试会因已知缺陷而失败，但不阻塞CI | 若抛出匹配异常，记为 **XFAIL**（通过）；若不抛或抛其他，记为 **FAILED** 或 **XPASS** |

**一句话总结**：`pytest.raises` 是**验证预期行为**，`xfail(raises=...)` 是**容忍已知缺陷**。

### 6. 极易踩中的 3 个致命陷阱

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **错误消息中括号 `{}` 被误认为正则分组** | `match` 参数使用正则表达式，字符串中的括号会被解析为捕获组，导致匹配失败或报错 | 对特殊字符（如`{`、`}`、`(`、`)`）使用 `re.escape`，或使用原始字符串 `r"..."` 并转义：`match=r"Invalid token \(expired\)"` |
| **`with` 块内放置了多行代码，导致测试“虚假通过”** | 块内前置代码（如参数准备）意外抛出了同类型的异常，而真正的业务行未执行 | **严格限定**：`with` 块内仅保留**唯一**抛异常的那一行，其他代码置于块外（Arrange阶段） |
| **异常类型过于宽泛（如捕获 `Exception`）** | 使用 `raises(Exception)`，导致任何运行时错误（包括`AttributeError`）都被视为“预期” | 尽量**明确**到具体的异常子类（如`ValueError`、`KeyError`、自定义`BusinessException`）；若必须宽泛，必须搭配精准的 `match` 正则来限定 |

### 7. 高级技巧：检测异常未触发时的辅助诊断

若异常未触发，`pytest.raises` 默认只会告诉你 `DID NOT RAISE`。为了更快定位，可以在 `with` 块后添加 `else` 或使用 `pytest.fail`，但更推荐直接在块前加 `print` 或日志，或使用 `--pdb` 调试。

**检查 `match` 未匹配时的差异**：
当 `match` 正则不匹配异常文本时，PyTest会展示两者差异：
```text
E   ValueError: '除数不能为零！' does not match pattern '除.*数'
```
这类似于 `assert` 重写的增强体验。

### 8. 最佳实践速查

- **Do**：明确异常类型，尽可能使用 `match` 验证消息核心内容。
- **Do**：使用 `as exc_info` 检查异常的附加属性（状态码、错误ID）。
- **Do**：结合参数化，一次性覆盖所有错误分支。
- **Don't**：在 `with` 块内写超过1行的逻辑。
- **Don't**：用 `pytest.raises` 来标记已知缺陷，应使用 `xfail`。
- **Don't**：在 `match` 中使用易变的消息（如包含时间戳的字符串），否则测试会因文字变化而破碎。

你现在是希望**验证一个自定义业务异常**（携带`error_code`字段），还是想对**多个输入参数编写统一的异常断言模板**？告诉我具体的异常类和错误场景，我可以为你生成一段同时覆盖**类型匹配**、**文本正则**和**属性检查**的标准模板代码。

## 🔗 关联笔记
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[基于标记的条件执行与过滤筛选]]
- [[内置标记]]
- [[数据驱动测试与测试工厂（Factory）模式]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, parametrize, coverage, assertion, exception, markers, xfail, data-driven）
> - [+] 新增 H1「异常断言（pytest.raises）与异常文本匹配」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
