---
tags: [pytest, testing, python, fixture, parametrize, coverage, hooks, conftest, unittest, discovery]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: pytest自动发现机制.md
---
# pytest自动发现机制

## 📌 一句话总结
> 这是 `pytest` 自动发现机制的第一道关卡。命名约定遵循**极简主义**原则：你只需遵守几个固定的通配符模式，`pytest` 就能零配置地找到所有测试。

我把这套规则分为 **物理层（文件/目录）** 和 **逻辑层（类/函数）**，并给出工程化的命名最佳实践。

## 🎯 核心概念

### 1. 核心默认约定速查表

| 层级 | 对象 | 必须匹配的模式 | 错误示例（不会被收集） |
| :--- | :--- | :--- | :--- |
| **物理层** | 测试文件 | `test_*.py` 或 `*_test.py` | `case_login.py`、`login_tests.py`（注意：`_test` 必须在**末尾**） |
| **逻辑层** | 测试函数（顶级） | `test_*` | `login_test()`、`check_login()` |
| **逻辑层** | 测试类 | `Test*`（且 **无** `__init__` 方法） | `LoginTest`（缺少 `Test` 前缀）、`TestLogin` 但写了 `__init__` |
| **逻辑层** | 测试方法（类内部） | `test_*` | `test_login` 是标准，`login_test` 不行 |

> **关键原则**：`pytest` 默认递归扫描目录，但**只会执行**文件名、类名、函数名同时匹配上述模式的对象。

### 2. 目录命名推荐（物理隔离）

虽然 `pytest` 不强制规定测试目录名称，但社区标准实践是：

```python
my_project/
├── src/                    # 业务代码
│   └── myapp/
├── tests/                  # 所有测试的根目录（推荐）
│   ├── conftest.py         # 共享固件
│   ├── unit/               # 单元测试（按模块拆分）
│   │   ├── test_models.py
│   │   └── test_services.py
│   ├── integration/        # 集成测试（依赖外部服务）
│   │   └── test_database.py
│   └── e2e/                # 端到端测试
│       └── test_user_flow.py
└── pyproject.toml
```

**为什么推荐 `tests/` 而非 `test/`**：`tests` 是复数形式，是 Python 官方文档和大多数开源项目（如 Django、Flask）的惯例。在 `pyproject.toml` 中配置：
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]  # 只扫描该目录，避免误扫 venv 或 node_modules
```

### 3. 测试类命名：为什么不能有 `__init__`？

这是一个**极其特殊且致命的约定**：

- **允许**：`class TestUserAPI:`（无 `__init__`）
- **禁止**：`class TestUserAPI:` 且内部定义了 `def __init__(self):` 或 `def __init__(self, arg):`

如果类包含 `__init__` 方法，`pytest` 在收集阶段会抛出 **`TypeError: 'TestUserAPI' is not a class`** 或直接忽略该类。这是因为 `pytest` 不会实例化测试类来执行方法（它利用 Python 的反射机制直接绑定函数），`__init__` 的存在会破坏这一机制。

**若需要初始化逻辑，请使用 `setup_method` 或 `pytest.fixture`**，而非 `__init__`。

### 4. 进阶：自定义命名模式（放宽或收紧）

如果你的项目历史原因导致文件命名不是 `test_` 开头，你可以在 `pyproject.toml` 中覆盖默认模式：

```toml
[tool.pytest.ini_options]
# 让 pytest 也收集以 "check_" 或 "verify_" 开头的文件
python_files = ["test_*.py", "*_test.py", "check_*.py"]

# 让 pytest 收集以 "should_" 开头的函数（行为驱动风格）
python_functions = ["test_*", "should_*"]

# 让 pytest 收集以 "Spec" 结尾的类
python_classes = ["Test*", "*Spec"]
```

**注意**：过度放宽命名规则会降低代码可读性，且增加新人理解成本。非必要不修改。

### 5. 命名最佳实践（写给人看，而非机器）

约定保证“能被发现”，但**好的命名**保证“能被理解”。遵循 **“Given-When-Then”** 或 **“行为描述”** 范式：

- ✅ **优秀**：`test_withdraw_more_than_balance_raises_error()`（一眼看出测什么、预期什么）
- ❌ **差劲**：`test_case_1()`、`test_fail()`（无意义）
- ✅ **类级分组**：`class TestAccountWithdraw:` 将相关场景聚合
- ✅ **参数化 ids**：为 `@pytest.mark.parametrize` 添加可读的 `ids`，生成的测试节点名会变成 `test_process_order[valid_user]` 而非 `test_process_order[0]`

```python
@pytest.mark.parametrize(
    "role,expected_code",
    [("admin", 200), ("guest", 403)],
    ids=["admin_should_succeed", "guest_should_fail"]  # 命名提升可读性
)
def test_access_control(role, expected_code):
    ...
```

### 6. 混合 `unittest` 兼容模式下的命名陷阱

如果你处于 `unittest` 向 `pytest` 的迁移期，请注意：

- `unittest.TestCase` 子类会被 `pytest` 收集，但**其内部方法必须仍以 `test_` 开头**（遵循 `unittest` 自己的规则）。
- 类名**无需**严格以 `Test` 开头也能被 `pytest` 收集（因为 `unittest` 的发现机制不同），但**强烈建议统一**改为 `Test` 前缀，以保持风格一致。

### 7. 快速自查清单（遇到测试未执行时）

如果 `pytest` 显示 `collected 0 items`，按此顺序排查：

1.  [ ] 文件名是否以 `test_` 开头或以 `_test` 结尾？
2.  [ ] 函数名是否以 `test_` 开头？（注意全是小写）
3.  [ ] 类名是否以 `Test` 开头？（注意大写 T）
4.  [ ] 该类是否不小心写了 `__init__` 方法？（删掉或用 `fixture`）
5.  [ ] 文件是否在 `testpaths` 配置的目录下？（检查 `pyproject.toml`）
6.  [ ] 文件是否为空或存在语法错误？（`pytest --collect-only` 可查看详细收集日志）

现在，您项目中现有的测试文件命名是更偏向 `test_*.py` 还是 `*_test.py`？如果您的项目有历史遗留的“非标准”命名（比如以 `tc_` 开头的文件），我可以教您如何通过 `conftest.py` 中的 `pytest_collect_file` 钩子进行**精准定制化收集**，而不必大面积重命名文件。您想了解这个进阶技巧吗？

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[单参数与多参数笛卡尔积组合]]
- [[Hook函数类型与自定义插件开发入门]]
- [[unittest迁移到pytest实战]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, coverage, hooks, conftest, unittest, discovery）
> - [+] 新增 H1「pytest自动发现机制」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
