---
tags: [pytest, testing, python, fixture, parametrize, mock, coverage, plugins, conftest, scope]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: conftest.py的共享机制与作用域隔离.md
---
# conftest.py的共享机制与作用域隔离

## 📌 一句话总结
> 这是`pytest`架构中最精妙的“隐藏引擎”——`conftest.py`。理解了它，你就掌握了跨模块共享资源与隔离环境的核心钥匙。

`conftest.py` 的本质是一个**本地插件（Local Plugin）**。它的共享机制基于**目录树（Directory Tree）**，而隔离机制则依赖**作用域（Scope）叠加**和**名称覆盖（Override）**。我将其拆解为“可见性”与“生命周期”两个维度，帮你彻底理清。

## 🎯 核心概念

### 1. 共享机制：基于目录血缘的“可见性”规则

`pytest` 遵循 **“向上可见，向下隔离”** 的原则。具体来说：

- **向上继承**：当前目录下的测试文件，**可以自动发现**并注入当前目录及其**所有父级目录**（直到项目根目录）中的 `conftest.py` 定义的固件。
- **向下隔离**：父级 `conftest.py` **无法使用** 子级 `conftest.py` 中定义的固件。

**目录结构实战图解：**
```text
project/
├── conftest.py                # 全局固件（所有测试可见）
├── tests/
│   ├── conftest.py            # 测试根级固件（仅 tests/ 下可见）
│   ├── unit/
│   │   ├── conftest.py        # 单元测试专用固件（仅 unit/ 下可见）
│   │   └── test_math.py      # ✅ 可见：本目录 + tests/ + project/ 的 conftest
│   ├── integration/
│   │   └── test_db.py        # ✅ 可见：tests/ + project/ 的 conftest（不可见 unit/ 内的）
│   └── e2e/
│       └── test_flow.py      # ✅ 可见：tests/ + project/ 的 conftest
```

> **关键结论**：共享范围由 `conftest.py` 所在的**最近公共父目录**决定。越贴近根目录，共享范围越大；越贴近具体测试文件夹，隔离性越强。

### 2. 隔离机制：物理覆盖（Override）与逻辑作用域（Scope）的交织

`conftest.py` 提供了**两种隔离武器**，一种针对“定义”，一种针对“状态”：

#### 隔离武器一：同名覆盖（定义级隔离）
如果子目录中的 `conftest.py` 定义了一个**与父级同名**的固件（Fixture），子目录内的测试会**强制使用子级版本**，父级固件对该子目录“不可见”（被遮蔽）。

```python
# project/conftest.py
@pytest.fixture
def db_url():
    return "postgresql://prod:pass@global-db"   # 全局配置

# project/tests/unit/conftest.py
@pytest.fixture
def db_url():  # 同名！
    return "sqlite:///:memory:"                # 单元测试用轻量级SQLite

# project/tests/unit/test_model.py
def test_model(db_url):  
    # 此处拿到的永远是 "sqlite:///:memory:"，父级被完美隔离
    assert "sqlite" in db_url
```
这是实现**环境隔离（生产配置 vs 测试配置）**的标准手段。

#### 隔离武器二：作用域叠加（状态级隔离）
即使固件定义在顶层的 `conftest.py` 中，作用域（Scope）依然控制着状态的共享边界。

| 父级作用域 | 子级测试行为 | 隔离效果 |
| :--- | :--- | :--- |
| `scope="session"` | 所有子目录中的测试共享同一个对象实例 | **无隔离**（状态完全共享，容易污染） |
| `scope="function"` | 每个测试函数都获得一个新的独立对象 | **完全隔离**（即使定义在全局，也不影响） |

**一句话总结**：`conftest.py` 的位置决定“能否拿到”，`scope` 决定“拿到的对象是新的还是旧的”。若想实现物理隔离，优先用“同名覆盖”；若想实现运行态隔离，优先用 `scope="function"`。

### 3. 极易踩中的 3 个“隐性共享”陷阱

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **修改 session 级固件导致子测试失败** | 根 `conftest.py` 定义 `list` 或 `dict` 返回，子测试A执行 `append`，子测试B读到了脏数据 | 若必须 `session`，返回**不可变类型**（`tuple`）或**深拷贝副本**：`return data.copy()` |
| **`conftest.py` 中的导入 `ModuleNotFoundError`** | 在 `conftest.py` 顶部写 `from src import app`，但 `src` 未安装到虚拟环境 | 在 `conftest.py` 中**延迟导入**（在函数内部 `import`），或确保 `pip install -e .` |
| **子目录 `conftest` 未生效** | 该文件命名为 `conftest.pyc` 或 `conf_test.py`（拼写错误），或不在测试文件执行的起始目录下 | 名称必须**全小写**、**精确**为 `conftest.py`，并确保 `__init__.py` 不是必须的（`conftest` 不依赖包结构） |

### 4. 高级策略：`pytest_plugins` 与插件共享

如果你想跨多个根 `conftest.py` 共享一套通用固件（如公司内部测试工具集），可以利用 `pytest_plugins` 变量：

```python
# common_test_lib/conftest_helpers.py （外部文件，非标准 conftest）
# 不能直接放入 conftest.py，但可作为“可导入插件”

# 在项目根目录的 conftest.py 中注册：
pytest_plugins = ["common_test_lib.conftest_helpers"]
```
这个用法适合大型企业级测试基建，但日常项目极少用到，知道即可。

### 5. 决策速查：该把 Fixture 放哪里？

| 判定条件 | 存放位置 | 示例 |
| :--- | :--- | :--- |
| 所有测试都需要（环境变量、全局DB Schema） | **项目根目录** `conftest.py` | `os.environ["TEST_MODE"] = "True"` |
| 某个子模块（如 `unit`）专用，不愿污染其他模块 | 子目录下的 **`unit/conftest.py`** | `@pytest.fixture` 制造本地Mock数据 |
| 仅在单个 `.py` 文件中使用 | 直接写在该**测试文件顶部**，不放入 `conftest` | 特定参数化构造器 |
| 需要覆盖父级配置（如单元测试改用内存DB） | 子目录 `conftest.py` + **同名函数** | 参见上文“隔离武器一” |

### 6. 终极验证命令

当你怀疑 `conftest.py` 的隔离逻辑时，请执行以下诊断命令：
```bash
# 1. 查看当前目录下所有可用的固件及其来源
pytest --fixtures -v

# 2. 查看特定测试文件会加载哪些 conftest
pytest --trace-config
```

现在，您的项目根目录下是否已经存在 `conftest.py`？如果还没有，我可以为您设计一个**三层结构**（根、单元、集成各放一个），并写出具体代码，让您直观感受“同名覆盖”带来的环境隔离魔法。您想试试看吗？

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[pytest-mock插件与unittest.mock无缝集成]]
- [[内置作用域层级]]
- [[pytest自动发现机制]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, mock, coverage, plugins, conftest, scope）
> - [+] 新增 H1「conftest.py的共享机制与作用域隔离」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
