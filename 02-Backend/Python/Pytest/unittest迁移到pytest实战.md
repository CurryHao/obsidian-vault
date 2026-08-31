---
tags: [pytest, testing, python, fixture, parametrize, assertion, exception, plugins, conftest, scope]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: unittest迁移到pytest实战.md
---
# unittest迁移到pytest实战

## 📌 一句话总结
> 这是一个极具实战价值的议题。许多大型代码库都沉淀了海量的`unittest`用例，完全重写不现实，但固守旧制又无法享受`pytest`的现代生产力。

我的核心观点是：**兼容是过渡手段，迁移是最终目标**。`pytest`对`unittest`的兼容性非常优秀，但**“能跑”不等于“用得好”**。我们需要分阶段、有策略地完成蜕变。

## 🎯 核心概念

### 1. 兼容机制：`pytest` 如何“托管” `unittest` 用例？

当你执行`pytest`时，它内部有一个专门的 **`unittest.TestCase` 执行器（`pytest_unittest` 插件）**。它的处理逻辑是：

- **收集阶段**：正常识别所有继承`unittest.TestCase`的类和方法。
- **执行阶段**：`pytest`并**不重写**这些类内部的`assert`语句（退化回原生断言），但会**接管**其生命周期管理。
- **生命周期映射**（关键点）：
  - `setUp()` → 映射为 `pytest` 的 **function** 级别 setup
  - `tearDown()` → 映射为 function 级别 teardown
  - `setUpClass()` → 映射为 **class** 级别 setup
  - `tearDownClass()` → 映射为 class 级别 teardown
  - `setUpModule()` / `tearDownModule()` → 映射为 **module** 级别

这意味着，只要你执行`pytest`，这些旧用例**完全零修改**就能跑起来，且执行顺序和生命周期得到正确保障。

### 2. 兼容期的致命伤：为什么“能跑”并不够？

在兼容模式下运行，你会损失`pytest`最精华的三大优势，这直接导致**迁移的必要性**：

| 丢失的能力 | 具体表现 | 带来的痛苦 |
| :--- | :--- | :--- |
| **断言自省（Introspection）** | 失败时只能看到 `AssertionError`，看不到变量具体值 | 调试大型旧用例时，必须手动加`print`或断点，效率骤降 |
| **Fixture 依赖注入** | 无法在测试方法参数中直接声明 `db_conn` 并使用 | 只能继续写臃肿的 `self.db = get_db()`，无法实现固件复用 |
| **参数化（Parametrize）** | `@pytest.mark.parametrize` **无法直接**作用于 `unittest.TestCase` 的方法上 | 若要测试多组数据，只能写多个方法或用`subTest`，代码冗余 |

> **特别注意**：如果你在 `unittest.TestCase` 内部尝试给方法加 `@pytest.mark.parametrize`，`pytest` 会收集到参数，但执行时会因为`self`传递混乱而报错或行为异常。**强烈建议不要在兼容模式下强行混合装饰器。**

### 3. 四步渐进式迁移策略（实战推荐）

不要一次性大面积重构，应采用“**新代码用新风格，旧代码分模块替换**”的绞杀者模式。

#### 阶段一：替换运行器（零风险，立即生效）
- **操作**：不再使用 `python -m unittest`，直接改用 `pytest` 运行所有旧用例。
- **目的**：验证兼容性，同时享受 `pytest` 的彩色输出、`-x`（失败即停）和 `--lf`（只跑上次失败）等快捷选项。

#### 阶段二：将 `setUp`/`tearDown` 拆解为独立 Fixture（核心重构）
这是**工作量最大但收益最高**的步骤。将类中的属性和资源抽取到 `conftest.py` 中。

- **旧代码（unittest）**：
```python
import unittest

class TestUserAPI(unittest.TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = self.client.create_user("test")
    
    def tearDown(self):
        self.client.delete_user(self.user.id)
    
    def test_update(self):
        self.user.name = "new"
        res = self.client.update(self.user)
        self.assertEqual(res.status, 200)
```

- **新代码（重构为纯函数 + Fixture）**：
```python
import pytest

# 放在 conftest.py 或当前文件中
@pytest.fixture
def api_client():
    client = APIClient()
    yield client  # 替代 tearDown，资源清理放在 yield 之后
    # 如果无需整体清理，可忽略

@pytest.fixture
def test_user(api_client):
    user = api_client.create_user("test")
    yield user
    api_client.delete_user(user.id)  # 自动清理

# 测试函数极简且干净
def test_update(api_client, test_user):  # 依赖注入
    test_user.name = "new"
    res = api_client.update(test_user)
    assert res.status == 200  # 享受原生断言与自省！
```

#### 阶段三：拆解 `setUpClass` 为 Session/Module 级 Fixture
对于耗时的类级初始化（如数据库连接池），映射为作用域更大的固件：
```python
@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    engine.init_tables()
    yield engine
    engine.drop_tables()
```

#### 阶段四：拥抱参数化，废弃 `subTest`
- **旧写法**：`for data in test_cases: with self.subTest(data): ...`
- **新写法**：`@pytest.mark.parametrize("input,expected", [...])`
此时测试报告会为**每一组数据**生成独立的 `PASSED/FAILED` 条目，定位问题精准百倍。

### 4. 特殊兼容技巧：让 Fixture 临时注入 `unittest` 类

如果短期内无法拆掉类结构，但你又想让旧类使用`pytest`的强大固件，可以用 `@pytest.mark.usefixtures` 配合 `autouse`，但**不推荐**作为长期方案（因为无法直接传递给方法参数，需通过 `self` 属性访问，侵入性强）。

```python
import pytest

@pytest.fixture(autouse=True)
def inject_global_state(request):
    # 将固件挂载到 unittest.TestCase 实例上
    request.instance.db = create_db()
    yield
    request.instance.db.close()

# 旧类依然能通过 self.db 访问到
class TestOldStyle(unittest.TestCase):
    def test_query(self):
        self.assertIsNotNone(self.db)  # 可运行，但丧失了注入的显式性
```

### 5. 迁移路线图决策矩阵

| 项目规模 | 推荐策略 | 预期耗时 |
| :--- | :--- | :--- |
| **小型项目（< 50 个用例）** | 一次性全量迁移，直接重写为纯函数 | 1天 |
| **中型项目（50 - 500 个用例）** | 新需求用新风格，修改到的旧文件顺带重构（**童子军军规**） | 迭代2-3周 |
| **大型遗留系统（> 500 个用例）** | 仅在 `conftest.py` 抽离全局固件，**保持旧类不变**，仅享受 `pytest` 运行器的便利；待模块重构时再彻底改造 | 长期演进 |

### 6. 最后一张迁移清单（Cheatsheet）

- [ ] 将运行命令从 `unittest` 改为 `pytest`，检查通过率是否一致。
- [ ] 找一个简单的 `setUp` 方法，尝试将其替换为一个 `yield` 固件，并修改对应的测试函数（去掉类）。
- [ ] 确认 `pytest.ini` 中配置了 `testpaths = tests`，并遵守命名规范。
- [ ] 删除旧代码中的 `import unittest` 和 `(unittest.TestCase)`，使代码净重下降。
- [ ] 运行 `pytest --assert=plain` 对比一下重写前后的错误信息差异，亲自体验“自省”的爽感。

您的项目中目前大概有多少个 `unittest.TestCase` 类？它们主要依赖 `setUp` 还是 `setUpClass` 进行准备？告诉我具体状况，我可以为您设计一条**最小的可行迁移路径（MVP Path）**，让您花最少的时间获得最大的测试体验提升。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[内置作用域层级]]
- [[异常断言（pytest.raises）与异常文本匹配]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, assertion, exception, plugins, conftest, scope）
> - [+] 新增 H1「unittest迁移到pytest实战」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
