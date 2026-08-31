---
tags: [pytest, testing, python, fixture, parametrize, coverage, assertion, conftest, markers, registration]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: Fixture相互依赖与工厂模式实现.md
---
# Fixture相互依赖与工厂模式实现

## 📌 一句话总结
> 这是PyTest Fixture机制从**“入门”迈向“精通”**的必经之路。如果说`conftest.py`解决了“资源在哪共享”，那么**Fixture依赖与工厂模式**则解决了“资源如何灵活组装”。

我将分两个层级为你拆解：**基础层（直接依赖注入）** 和 **高级层（工厂模式动态生成）**，并揭示`pytest`内部的**依赖图解析（DAG）**机制。

## 🎯 核心概念

### 1. 层级一：Fixture 相互依赖（直接注入）

这是最直观的用法：**一个Fixture可以像测试函数一样，在参数中声明另一个Fixture**。`pytest` 会自动解析依赖关系，构建一个有向无环图（DAG），并保证**被依赖的Fixture先执行（深度优先）**。

```python
import pytest

# 1. 底层资源：数据库连接
@pytest.fixture(scope="session")
def db_engine():
    print("\n[Setup] 创建数据库引擎")
    yield "postgresql://localhost:5432/test"
    print("[Teardown] 关闭数据库引擎")

# 2. 中层资源：会话层事务（依赖 db_engine）
@pytest.fixture(scope="function")
def db_session(db_engine):  # ← 显式依赖
    print(f"   [Setup] 基于 {db_engine} 开启事务")
    yield {"conn": db_engine, "txn_id": 123}
    print("   [Teardown] 回滚事务")

# 3. 业务层资源：当前登录用户（依赖 db_session）
@pytest.fixture
def auth_user(db_session):  # ← 多层依赖
    print(f"      [Setup] 在事务 {db_session['txn_id']} 中创建用户")
    user = {"id": 1, "name": "Alice"}
    yield user
    print("      [Teardown] 删除测试用户")

# 测试函数：只需声明最顶层的 Fixture
def test_user_profile(auth_user):
    print(f"         [Test] 验证用户: {auth_user['name']}")
    assert auth_user["id"] == 1
```

**执行顺序（深度优先输出）：**
```text
[Setup] 创建数据库引擎          ← session级
   [Setup] 基于 ... 开启事务     ← function级（依赖引擎）
      [Setup] 在事务 123 中创建用户 ← function级（依赖事务）
         [Test] 验证用户: Alice
      [Teardown] 删除测试用户
   [Teardown] 回滚事务
[Teardown] 关闭数据库引擎
```
> **核心规则**：无论你声明了多少层，`pytest` 永远**先跑最底层（无依赖的），再跑上层**。Teardown 严格逆序执行。

### 2. 层级二：工厂模式（Factory as Fixture）

直接注入的Fixture返回的是**固定对象**。但在真实测试中，我们需要**动态构造不同属性的对象**（比如每个测试要创建不同名字的用户）。此时，让Fixture返回一个**“工厂函数（可调用对象）”**，而非数据本身。

#### 基础工厂模式（无状态）
```python
@pytest.fixture
def user_factory(db_session):  # 依赖数据库会话
    """返回一个用于动态创建用户的工厂函数"""
    def _create_user(name, age=18, role="free"):
        # 内部使用 db_session 执行插入
        user_id = db_session["conn"].insert(f"INSERT INTO users (name,age,role) VALUES ({name},{age},{role})")
        return {"id": user_id, "name": name, "age": age, "role": role}
    return _create_user

# 测试用例：灵活构造不同的输入
def test_premium_feature(user_factory):
    # Arrange - 动态创建特定用户
    adult_user = user_factory(name="Bob", age=30, role="premium")
    child_user = user_factory(name="Charlie", age=12)  # 使用默认 role="free"
    
    # Act & Assert
    assert adult_user["role"] == "premium"
    assert child_user["age"] == 12
```

#### 高级工厂模式（带自动清理的终结器）
工厂每调用一次就生成一个新资源（如插入一条数据库记录）。如果不清理，会污染数据库。这时需要**在工厂内部注册终结器（Finalizer）**，让每个动态生成的对象在测试结束后自动销毁。

```python
import pytest

@pytest.fixture
def user_factory_with_cleanup(db_session):
    """工厂模式 + 自动清理动态创建的资源"""
    created_ids = []  # 闭包变量，记录本次测试中工厂创建的所有ID
    
    def _create_user(name, age):
        user_id = db_session["conn"].insert(f"INSERT INTO users (name,age) VALUES ({name},{age})")
        created_ids.append(user_id)
        return {"id": user_id, "name": name}
    
    yield _create_user  # 先交出工厂函数
    
    # --- 此处是 Fixture 的 Teardown 阶段 ---
    # 批量清理所有动态创建的用户（逆序删除）
    for uid in reversed(created_ids):
        db_session["conn"].delete(f"DELETE FROM users WHERE id={uid}")
        print(f"   [Cleanup] 删除动态用户 ID: {uid}")
```
**使用效果**：无论测试用例用工厂创建了1个还是10个用户，测试结束后都会被自动清理，无需手动操心。

### 3. 进阶技巧：利用 `request` 对象实现“可配置工厂”

有时工厂需要根据测试的**标记（Marker）**或**参数化**调整行为。可以通过注入 `request` 对象来读取上下文：

```python
@pytest.fixture
def configurable_factory(request):
    default_age = request.node.get_closest_marker("default_age")
    default_age_value = default_age.args[0] if default_age else 18
    
    def _create_user(name, age=default_age_value):
        return {"name": name, "age": age}
    return _create_user

@pytest.mark.default_age(25)  # 自定义标记
def test_with_custom_default(configurable_factory):
    user = configurable_factory("Eve")
    assert user["age"] == 25  # 覆盖了默认的18
```

### 4. 极易踩中的 3 个陷阱（务必留心）

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **工厂内使用 `session` 级 Fixture，导致状态累积** | 工厂函数引用了一个 `session` 级的可变对象（如列表），多次调用工厂追加数据，影响后续测试 | 工厂函数内部**每次调用时创建新容器**（如 `data = []`），而非引用外部闭包变量 |
| **直接依赖工厂函数而非工厂结果** | 测试参数写 `def test(user_factory):`，但忘记调用 `user_factory()`，直接把函数对象当数据用 | 记得加括号调用；或在工厂命名时加动词前缀（`make_user`）来提醒自己 |
| **嵌套工厂依赖死循环** | Fixture A 依赖 B，B 依赖 A（循环依赖），Pytest 抛出 `RecursionError` | 检查依赖图，提取公共底层资源（如数据库连接），让 A 和 B 都依赖底层 C，而非互相依赖 |

### 5. 决策指南：何时用直接依赖，何时用工厂模式？

| 判断维度 | 直接依赖注入 | 工厂模式（返回函数） |
| :--- | :--- | :--- |
| **对象是否固定** | ✅ 固定值（如配置字典、单例连接） | ❌ 需在测试中动态定制（不同名字、年龄） |
| **构造逻辑复杂度** | 简单（`return` 字面量） | 复杂（需调用API、计算、入库） |
| **清理策略** | 单个对象，直接用 Fixture 的 `yield` 清理 | 多个对象（批量创建），需在工厂闭包内收集ID并批量清理 |
| **使用频率** | 每次测试只用一次 | 一个测试中可能创建多个不同的对象 |

### 6. 终极架构参考（集成 `conftest.py`）

在实际工程中，我会这样组织（三层结构）：

- **`conftest.py`（根）**：定义 `db_engine`（session级）、`db_session`（function级）。
- **`conftest.py`（unit/）**：定义 `user_factory`（依赖根部的 `db_session`），并封装好清理逻辑。
- **`test_api.py`**：直接使用 `user_factory` 动态构造参数，聚焦业务断言。

这种分层让**基础资源（DB）**、**制造器（Factory）**和**测试逻辑（Assert）**三者分离，代码极其整洁。

您现在是想为一个**依赖真实数据库**的项目编写工厂固件，还是想**对现有的复杂对象构造逻辑**（比如多层嵌套的订单数据）进行封装？告诉我您正在测试的业务对象类型，我可以为您专门设计一个“工厂 + 依赖注入”的完整代码模板，直接放入您的 `conftest.py` 即可运行。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[内置标记]]
- [[自定义标记注册与业务语义映射]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, coverage, assertion, conftest, markers, registration）
> - [+] 新增 H1「Fixture相互依赖与工厂模式实现」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
