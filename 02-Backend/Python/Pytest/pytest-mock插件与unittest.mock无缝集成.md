---
tags: [pytest, testing, python, fixture, parametrize, mock, monkeypatch, assertion, exception, unittest]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: pytest-mock插件与unittest.mock无缝集成.md
---
# pytest-mock插件与unittest.mock无缝集成

## 📌 一句话总结
> `pytest-mock` 并非要替代 `unittest.mock`，而是为它在 `pytest` 生态中提供了一个更自然、更“Pythonic”的接口。它是一个围绕 `unittest.mock` 的**轻量级包装器（thin-wrapper）**。

它的核心是提供一个 `mocker` fixture，让 Mock 的创建和管理与 `pytest` 的风格无缝融合。

## 🎯 核心概念

### 为什么是 `pytest-mock`？它解决了什么痛点？

直接使用 `unittest.mock` 时，常见的两种方式都有其不便之处：

*   **`with` 上下文管理器**：当需要模拟多个对象时，会导致代码陷入多层嵌套，破坏测试的流畅性。
*   **`@patch` 装饰器**：虽然避免了嵌套，但会导致测试函数参数增多且顺序与装饰器相反，容易出错。同时，它与 `pytest` 的 fixture 和参数化功能配合不佳。

`pytest-mock` 通过 `mocker` fixture 解决了这些问题，带来以下核心价值：

1.  **自动清理，确保隔离**：`mocker.patch()` 创建的补丁在测试结束后会被**自动撤销（automatically undone）**，无需手动 `stop()`，从根本上避免了 Mock 污染。
2.  **更简洁的语法**：`mocker.patch()` 直接返回 Mock 对象，减少了样板代码。
3.  **增强的断言错误报告**：当 `mock.assert_called_with()` 等断言失败时，`pytest-mock` 会利用 `pytest` 的先进断言机制，生成更清晰、更具可读性的差异报告。
4.  **额外的实用工具**：提供了 `mocker.spy` 和 `mocker.stub` 等便捷功能。
5.  **完整的类型注解**：`pytest-mock` 提供了完整的类型注解，便于静态类型检查。

### `mocker` Fixture：核心 API 使用指南

`mocker` fixture 的 API 设计与 `unittest.mock` 高度一致，学习成本极低。

#### 1. 基础补丁 (`mocker.patch`)

这是最常用的方法，用于替换指定路径的对象。

```python
# myapp/services.py
import requests

def get_cat_facts():
    response = requests.get("https://catfact.ninja/fact")
    return response.json()['fact']
```

```python
# test_services.py
import pytest
from myapp.services import get_cat_facts

def test_get_cat_facts(mocker):
    # 1. 创建补丁，替换 'myapp.services.requests.get'
    #    注意：要 patch 的是对象被**使用**的地方，而非定义的地方
    mock_get = mocker.patch('myapp.services.requests.get')
    
    # 2. 配置 Mock 对象的行为
    mock_response = mocker.Mock()
    mock_response.json.return_value = {'fact': 'Cats sleep a lot.'}
    mock_get.return_value = mock_response
    
    # 3. 执行测试
    result = get_cat_facts()
    
    # 4. 断言
    assert result == 'Cats sleep a lot.'
    mock_get.assert_called_once_with("https://catfact.ninja/fact")
```

#### 2. 补丁对象方法 (`mocker.patch.object`)

当需要替换一个对象的特定方法时，使用此方法更安全、更精确。

```python
class UserRepository:
    def save(self, user):
        # ... 保存用户到数据库
        pass

def create_user(repo, name):
    repo.save({"name": name})
```

```python
def test_create_user(mocker):
    mock_repo = mocker.Mock(spec=UserRepository)
    # 使用 patch.object 替换 UserRepository.save 方法
    mock_save = mocker.patch.object(UserRepository, 'save')
    
    create_user(mock_repo, 'Alice')
    
    mock_save.assert_called_once_with({"name": "Alice"})
```

#### 3. 配置返回值 (`return_value`) 和副作用 (`side_effect`)

*   **`return_value`**: 指定 Mock 对象被调用时返回的值。
*   **`side_effect`**: 可以指定一个异常、一个可迭代对象（每次调用返回下一个值）或一个函数。

```python
def test_api_retry(mocker):
    # 模拟前两次调用失败，第三次成功
    mock_fetch = mocker.patch(
        'myapp.api.fetch',
        side_effect=[ConnectionError(), ConnectionError(), {'data': 'ok'}]
    )
    
    result = fetch_with_retry()  # 假设这个函数会重试
    assert result == {'data': 'ok'}
    assert mock_fetch.call_count == 3
```

#### 4. 间谍 (`mocker.spy`)

与 `mocker.patch` 完全替换原方法不同，`mocker.spy` 会**保留原方法的原始逻辑**，同时允许你追踪它的调用信息。

```python
# myapp/tax.py
def calculate_tax(amount):
    return amount * 0.1
```

```python
def test_tax_calculation(mocker):
    # 在 calculate_tax 上创建一个 spy
    spy = mocker.spy(myapp.tax, 'calculate_tax')
    
    result = process_order(amount=1000)  # 假设这个函数内部调用了 calculate_tax
    
    # 验证 calculate_tax 被正确调用，且原始逻辑被执行
    spy.assert_called_once_with(1000)
    assert spy.spy_return == 100.0  # 原始函数的返回值
    assert result == 1100.0
```

#### 5. 桩 (`mocker.stub`)

`mocker.stub` 创建一个可以接受任何参数的 Mock 对象，主要用于测试回调函数等场景。

```python
def test_callback(mocker):
    callback = mocker.stub(name="my_callback")
    # 将这个 stub 传递给某个函数，该函数会调用它
    some_function(callback)
    callback.assert_called_once_with(1, 2, 3)
```

### `pytest-mock` 与 `unittest.mock` 的对比

| 特性 | `unittest.mock` (直接使用) | `pytest-mock` (通过 `mocker`) |
| :--- | :--- | :--- |
| **清理机制** | 需手动管理（`patch.stop`）或依赖上下文/装饰器 | **自动清理**，随测试结束而结束 |
| **语法简洁性** | 多层装饰器或 `with` 嵌套，较繁琐 | 扁平化，所有补丁在函数内顺序执行 |
| **与 Pytest 集成** | 需处理装饰器顺序与 fixture 参数的冲突 | 原生支持，`mocker` 就是一个 fixture |
| **错误报告** | 标准输出，信息有限 | **增强输出**，提供参数差异的详细比较 |
| **额外工具** | 无 | 提供 `spy`, `stub` 等便捷工具 |
| **类型注解** | 有限 | **完全类型注解**，支持 `mypy` |

### 高级配置与集成

*   **使用独立的 `mock` 包**：若需要使用比 Python 内置版本更新的 `mock` 包，可在 `pytest.ini` 中配置：
    ```ini
    [pytest]
    mock_use_standalone_module = true
    ```
*   **禁用增强的错误报告**：如果增强的报告导致问题，可以关闭：
    ```ini
    [pytest]
    mock_traceback_monkeypatch = false
    ```

### 常见陷阱与最佳实践

1.  **补丁的位置 ("Where to patch")**：这是最常见的错误。应该 patch 对象**被使用的地方**，而不是它**被定义的地方**。
2.  **`mocker` 与 `monkeypatch` 的抉择**：
    *   **`monkeypatch`**：适合替换简单的属性、环境变量等。
    *   **`mocker` (`pytest-mock`)**：适合创建功能完整的 Mock 对象，特别是需要模拟行为、验证调用时。
3.  **为 Mock 指定 `spec`**：使用 `mocker.Mock(spec=SomeClass)` 或 `autospec=True`，可以让 Mock 拥有与真实对象相同的接口，避免因拼写错误导致的测试通过但生产失败的问题。

### 总结

`pytest-mock` 通过提供 `mocker` fixture，将 `unittest.mock` 的强大功能以更优雅、更安全的方式融入 `pytest` 工作流。

*   **如果你在使用 `pytest`**：强烈推荐安装 `pytest-mock`。它能让 Mock 代码更简洁、更健壮。
*   **核心价值**：自动清理 + 简洁语法 + 增强报错。

安装只需一行命令：
```bash
pip install pytest-mock
```

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[monkeypatch动态替换运行时对象与属性]]
- [[异常断言（pytest.raises）与异常文本匹配]]
- [[unittest迁移到pytest实战]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, mock, monkeypatch, assertion, exception, unittest）
> - [+] 新增 H1「pytest-mock插件与unittest.mock无缝集成」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
