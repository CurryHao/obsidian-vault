---
tags: [pytest, testing, python, fixture, parametrize, mock, monkeypatch, coverage, assertion, plugins]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 内置实用Fixture.md
---
# 内置实用Fixture

## 📌 一句话总结
> 这四个Fixture是PyTest官方提供的“瑞士军刀”，覆盖了测试中最常遇到的**临时文件、标准输出、环境模拟和上下文自省**四大场景。它们开箱即用，无需安装任何插件。

我将逐个拆解它们的**核心用法**、**典型场景**和**极易踩中的陷阱**，并给出组合使用的实战案例。

## 🎯 核心概念

### 1. `tmp_path`：临时文件与目录管理（现代版）

- **作用**：为每个测试创建一个独立的临时目录，测试结束后自动清理。
- **类型**：返回 `pathlib.Path` 对象（Python 3.5+ 标准），比旧版的 `tmpdir`（返回 `py.path.local`）更现代、更类型友好。
- **作用域**：默认 `function`（每个测试独立）。

```python
def test_write_and_read(tmp_path):
    # Arrange：在临时目录下创建子目录和文件
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    file_path = data_dir / "config.json"
    
    # Act：写入文件
    file_path.write_text('{"key": "value"}')
    
    # Assert：读取并验证
    content = file_path.read_text()
    assert content == '{"key": "value"}'
    assert file_path.exists() is True
    # 测试结束后，tmp_path 及其所有内容被自动删除
```

**陷阱与进阶**：
- **与 `tmp_path_factory` 的区别**：`tmp_path` 是函数级（每个测试独立）；`tmp_path_factory` 是 `session` 级，用于在 `session` 级 Fixture 中创建跨测试共享的临时目录。
- **切勿手动删除**：`pytest` 会自动清理，手动 `rmtree` 不仅多余，还可能因权限问题导致清理失败。

### 2. `capsys`：捕获标准输出与错误输出

- **作用**：捕获 `sys.stdout` 和 `sys.stderr` 的输出，用于断言打印内容或日志（非 `logging` 模块）。
- **方法**：`capsys.readouterr()` 返回 `(out, err)` 元组。

```python
def greet(name):
    print(f"Hello, {name}!")
    return True

def test_greet_output(capsys):
    # Act
    result = greet("Alice")
    
    # Assert：验证返回值
    assert result is True
    
    # Assert：验证打印内容（极其精准）
    captured = capsys.readouterr()
    assert captured.out == "Hello, Alice!\n"  # 注意 print 自带换行
    assert captured.err == ""
```

**极易踩中的陷阱**：
- **与 `-s` 参数冲突**：当你使用 `pytest -s`（关闭捕获）运行时，`capsys` 会失效，`readouterr()` 返回空字符串。**解决方法**：调试时不要用 `-s` 测试 `capsys` 逻辑，或者在配置文件中禁止同时使用。
- **多次调用会清空缓冲区**：`capsys.readouterr()` 是**消费型**的，第二次调用会返回空。务必在捕获完输出后立即断言。

### 3. `monkeypatch`：动态修改环境（Mock 的轻量级替代）

- **作用**：在运行时安全地修改对象、环境变量、字典项和属性，测试结束后**自动复原**，无需手动恢复。
- **它是 `unittest.mock` 的完美补充**：适合修改全局配置、环境变量、第三方库的不可控属性。

| 方法 | 用途 | 示例 |
| :--- | :--- | :--- |
| `monkeypatch.setattr(obj, name, value)` | 修改对象属性/方法 | `monkeypatch.setattr(os, "getcwd", lambda: "/fake")` |
| `monkeypatch.setenv(name, value)` | 设置环境变量 | `monkeypatch.setenv("API_KEY", "test-123")` |
| `monkeypatch.setitem(dict, key, value)` | 修改字典项 | `monkeypatch.setitem(os.environ, "PATH", "/new/path")` |
| `monkeypatch.delattr(obj, name)` | 删除属性 | 模拟属性不存在的情况 |

**实战：Mock 外部 API 调用**：
```python
import requests

def fetch_user_data(user_id):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

def test_fetch_user_data(monkeypatch):
    # 定义一个假的 get 函数，替换 requests.get
    def mock_get(*args, **kwargs):
        class MockResponse:
            def json(self):
                return {"id": 1, "name": "Mocked User"}
        return MockResponse()
    
    monkeypatch.setattr(requests, "get", mock_get)
    
    # Act
    result = fetch_user_data(999)
    
    # Assert
    assert result["name"] == "Mocked User"
```

**核心优势**：与 `unittest.mock.patch` 装饰器不同，`monkeypatch` 是**命令式**的，可以在 Fixture 或测试函数中间动态决策，灵活性极高。

### 4. `request`：测试上下文自省（Fixtures 的“上帝视角”）

- **作用**：提供当前测试函数/类/模块的**元信息**，是构建高级 Fixture 的关键依赖。
- **常用属性**：

| 属性 | 描述 | 实战场景 |
| :--- | :--- | :--- |
| `request.param` | 获取参数化传入的当前参数值 | 实现 **`indirect=True`** 的参数化 Fixture |
| `request.node` | 当前测试节点对象 | 获取测试名称、标记、命令行参数 |
| `request.fixturename` | 当前 Fixture 的名称（自省） | 在 Fixture 内部打印日志时标识来源 |
| `request.config` | Pytest 配置对象 | 读取 `pyproject.toml` 中的自定义配置 |
| `request.cls` | 当前测试所属的类（若有） | 类级别 Fixture 中获取类属性 |
| `request.module` | 当前测试所属的模块 | 模块级 Fixture 中获取模块名 |

**经典用法：参数化 Fixture（`indirect=True`）**：
```python
import pytest

# 定义一个 Fixture，其行为依赖参数化传入的值
@pytest.fixture
def user_role(request):
    role = request.param  # 从参数化中取值
    if role == "admin":
        return {"permissions": ["read", "write", "delete"]}
    elif role == "guest":
        return {"permissions": ["read"]}
    else:
        return {"permissions": []}

# indirect=True 表示参数 'user_role' 的值会传给 Fixture，而非测试函数
@pytest.mark.parametrize("user_role", ["admin", "guest", "anonymous"], indirect=True)
def test_permissions(user_role):
    if user_role["permissions"]:
        assert "read" in user_role["permissions"]
    # 这个测试会分别用 admin/guest/anonymous 三种角色运行三次
```

### 5. 组合实战：四剑合璧

假设你在测试一个**读取环境变量并写入临时文件、同时打印日志**的函数：

```python
import os

def generate_report():
    env = os.getenv("APP_MODE", "prod")
    print(f"Generating report for {env} mode...")
    with open("report.txt", "w") as f:
        f.write(f"Mode: {env}")
    return "success"

def test_report_generation(tmp_path, capsys, monkeypatch, request):
    # 1. monkeypatch：将 APP_MODE 强制设为 test
    monkeypatch.setenv("APP_MODE", "test")
    
    # 2. 结合 tmp_path：修改当前工作目录到临时目录，防止污染项目根目录
    monkeypatch.chdir(tmp_path)  # 这也是 monkeypatch 的常用技巧！
    
    # 3. Act：执行被测函数（现在它会在临时目录下创建 report.txt）
    result = generate_report()
    
    # 4. 使用 capsys 验证打印日志
    captured = capsys.readouterr()
    assert captured.out == "Generating report for test mode...\n"
    
    # 5. 使用 tmp_path 验证文件内容
    report_file = tmp_path / "report.txt"
    assert report_file.read_text() == "Mode: test"
    
    # 6. 可选：使用 request.node 打印调试信息
    print(f"\n[Debug] Test {request.node.name} completed in {tmp_path}")
```

### 6. 终极总结与选型建议

| 内置 Fixture | 一句话场景 | 替代方案（何时不用） |
| :--- | :--- | :--- |
| **`tmp_path`** | 测试文件读写、生成图片/报告 | 若只是构造内存对象（字典/列表），无需它 |
| **`capsys`** | 测试 `print()` 或命令行输出 | 测试 `logging` 模块时，使用 `caplog`（另一个内置 Fixture）更专业 |
| **`monkeypatch`** | 修改环境变量、Mock 单个函数属性 | 需要复杂行为验证（如断言调用次数）时，配合 `unittest.mock` 使用 |
| **`request`** | 高级 Fixture 编写、参数化注入、访问配置 | 普通测试函数无需使用，仅用于 Fixture 定义层 |

这些 Fixture 覆盖了 80% 的日常测试场景。您现在的测试中遇到最多的是**文件操作**、**环境配置**还是**日志输出**？如果某个场景特别棘手，告诉我，我可以为您写一段“诊断型”测试代码，专门验证该 Fixture 在您项目中的行为是否符合预期。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[pytest-mock插件与unittest.mock无缝集成]]
- [[内置作用域层级]]
- [[内置标记]]
- [[pytest命令行参数详解]]
- [[monkeypatch动态替换运行时对象与属性]]
- [[unittest迁移到pytest实战]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, mock, monkeypatch, coverage, assertion, plugins）
> - [+] 新增 H1「内置实用Fixture」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
