---
tags: [pytest, testing, python, fixture, parametrize, coverage, assertion, conftest, markers, xfail]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 数据驱动测试与测试工厂（Factory）模式.md
---
# 数据驱动测试与测试工厂（Factory）模式

## 📌 一句话总结
> 这是PyTest进阶实践中**数据处理的核心模式组合**。**数据驱动测试（Data-Driven Testing）** 关注的是“**用什么数据**”，而**测试工厂（Factory）模式**关注的是“**如何构造数据**”。两者结合，能让你用极少的代码覆盖大量的业务场景。

我将其拆解为**概念分层**、**工厂模式实现**、**数据驱动高级技巧**以及**与Fixture的融合**四个维度。

## 🎯 核心概念

### 1. 概念界定：数据驱动 vs 测试工厂

| 维度 | **数据驱动测试 (DDT)** | **测试工厂 (Factory)** |
| :--- | :--- | :--- |
| **核心目标** | 分离**测试逻辑**与**测试数据**，用同一套逻辑验证多组输入/输出 | 封装**复杂对象的构造过程**，简化Arrange阶段 |
| **实现载体** | `@pytest.mark.parametrize` | 返回可调用对象的Fixture，或独立的Factory类 |
| **解决痛点** | 避免复制粘贴测试代码，提升覆盖率 | 避免每个测试重复写对象构造代码（如创建用户、订单） |
| **是否互补** | ✅ **高度互补**：工厂为数据驱动提供“数据原料”，数据驱动为工厂提供“参数化入口” |

### 2. 测试工厂（Factory）的三种实现形态

#### 形态一：简单工厂——Fixture 返回工厂函数（最常用，前面已涉及）
```python
# conftest.py
@pytest.fixture
def user_factory(db_session):
    """返回一个创建用户的工厂函数"""
    def _create_user(name="default", age=18, role="free"):
        user = User(name=name, age=age, role=role)
        db_session.add(user)
        db_session.commit()
        return user
    return _create_user

# test_user.py
def test_user_upgrade(user_factory):
    # Arrange: 工厂快速创建特定用户
    user = user_factory(name="Alice", role="free")
    # Act
    user.upgrade_to_premium()
    # Assert
    assert user.role == "premium"
```

#### 形态二：专用工厂类——适合复杂业务对象（如订单、多层次嵌套）
```python
# factories.py
from dataclasses import dataclass
from typing import List

@dataclass
class OrderFactory:
    """工厂类：封装订单构造逻辑，支持链式调用"""
    user_id: int = 1
    items: List[dict] = None
    discount_code: str = None
    
    def with_items(self, items):
        self.items = items
        return self
    
    def with_discount(self, code):
        self.discount_code = code
        return self
    
    def create(self):
        # 这里可以调用真实的业务层创建方法
        return OrderService.create(self.user_id, self.items, self.discount_code)

# test_order.py
def test_order_calculation():
    # 使用链式工厂
    order = OrderFactory() \
        .with_items([{"id": 1, "qty": 2}, {"id": 2, "qty": 1}]) \
        .with_discount("SAVE10") \
        .create()
    
    assert order.total == 100.0  # 按业务规则计算
```

#### 形态三：与 `factory_boy` 库集成（大型项目首选）
`factory_boy` 是专门用于测试的ORM工厂库，支持Django、SQLAlchemy等。

```python
# factories.py
import factory
from myapp.models import User

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    name = factory.Sequence(lambda n: f"user_{n}")
    age = factory.Faker("random_int", min=18, max=60)
    role = "free"

# test.py
def test_user_model(user_factory):
    user = UserFactory(name="Alice", age=25)  # 覆盖默认值
    # 或批量创建
    users = UserFactory.create_batch(5, role="premium")
```

### 3. 数据驱动测试的高级技巧

#### 技巧一：从外部文件加载测试数据
```python
import json
import pytest

def load_test_cases(file_path):
    with open(file_path) as f:
        return json.load(f)  # 返回列表，每个元素是一组参数

@pytest.mark.parametrize(
    "input_val, expected",
    load_test_cases("test_data/login_cases.json")
)
def test_login_scenarios(input_val, expected):
    assert login_api(input_val) == expected
```

#### 技巧二：使用 `pytest.param` 为每条数据附加标记
```python
@pytest.mark.parametrize("user_data, expected", [
    pytest.param({"name": "admin", "pwd": "123"}, 200, id="valid_user"),
    pytest.param({"name": "admin", "pwd": "wrong"}, 401, id="invalid_pwd", marks=pytest.mark.xfail),
    pytest.param({"name": "", "pwd": ""}, 400, id="empty_fields", marks=pytest.mark.smoke),
])
def test_login(user_data, expected):
    assert login(user_data["name"], user_data["pwd"]) == expected
```

#### 技巧三：动态参数组合（笛卡尔积 + 过滤）
```python
roles = ["admin", "guest", "vip"]
actions = ["read", "write", "delete"]

# 生成所有组合，但过滤掉“guest 不能 delete”
valid_combos = [
    (role, action) for role in roles for action in actions
    if not (role == "guest" and action == "delete")
]

@pytest.mark.parametrize("role, action", valid_combos)
def test_permission(role, action):
    assert check_permission(role, action) is True
```

### 4. 工厂 + 数据驱动的深度融合（最强大模式）

将工厂与数据驱动结合，实现“**参数化数据 → 工厂构造 → 业务断言**”的流水线。

```python
# conftest.py
@pytest.fixture
def order_factory():
    return OrderFactory

# test_orders.py
@pytest.mark.parametrize("items, discount, expected_total", [
    ([{"id": 1, "price": 10}], None, 10),
    ([{"id": 1, "price": 10}, {"id": 2, "price": 20}], "SAVE20", 24),
    ([{"id": 3, "price": 5}], "SAVE10", 4.5),
])
def test_order_total(order_factory, items, discount, expected_total):
    # 工厂 + 数据驱动：一行搞定构造
    order = order_factory().with_items(items).with_discount(discount).create()
    assert order.total == expected_total
```

### 5. 数据清理策略（工厂的“后顾之忧”）

工厂每次创建数据（如插入数据库）都可能留下痕迹。必须确保测试结束后清理干净。

**方案一：工厂内部使用事务回滚（最干净）**
```python
@pytest.fixture
def order_factory(db_session):
    def _create(**kwargs):
        order = Order(**kwargs)
        db_session.add(order)
        db_session.flush()  # 分配ID但不提交
        return order
    yield _create
    db_session.rollback()  # 测试结束后回滚所有数据
```

**方案二：利用 `factory_boy` 的自动清理机制**
`factory_boy` 结合 SQLAlchemy 时，可使用 `factory.Factory` 的 `create()` 方法配合 Session 回滚。

**方案三：事后显式删除（适用于 E2E 测试，不能回滚）**
```python
@pytest.fixture
def user_factory():
    created_ids = []
    def _create(**kwargs):
        user = User.create(**kwargs)
        created_ids.append(user.id)
        return user
    yield _create
    # 所有测试结束后，批量删除
    for uid in created_ids:
        User.delete(uid)
```

### 6. 极易踩中的 3 个陷阱

| 陷阱 | 表现 | 解决方案 |
| :--- | :--- | :--- |
| **工厂与数据驱动参数同名冲突** | 数据驱动参数名为 `name`，工厂内也有 `name`，导致 `user_factory(name="Alice")` 误传 | 工厂方法的参数命名使用更具体的名称（如 `user_name`），或使用 `**kwargs` 并严格校验 |
| **外部数据文件变更导致测试难以追踪** | JSON/CSV 文件被同事修改后，本地测试失败，难以定位原因 | 将数据文件纳入版本控制，并在测试失败时打印文件内容或行号；推荐使用 **`pytest.param` 内联数据**，而非外部文件，除非数据量极大 |
| **Factory Boy 过度使用导致测试不透明** | 复杂工厂隐藏了太多默认值，导致测试失败时难以判断是哪个默认值出错 | **显式优于隐式**：在测试中明确指定关键参数（如 `role="premium"`），而非依赖工厂默认值；仅在非关键字段（如创建时间、随机ID）使用默认值 |

### 7. 终极模板：完整的三层数据体系

```text
project/
├── tests/
│   ├── factories/              # 工厂层
│   │   ├── user_factory.py
│   │   └── order_factory.py
│   ├── data/                   # 数据层（静态测试数据集）
│   │   ├── login_cases.json
│   │   └── product_cases.csv
│   └── test_api.py             # 测试层（使用工厂 + 数据驱动）
```

**测试层示例（直接调用工厂 + 外部数据）**：
```python
import json
import pytest
from tests.factories.user_factory import UserFactory

def load_login_data():
    with open("tests/data/login_cases.json") as f:
        return json.load(f)

@pytest.mark.parametrize("case", load_login_data())
def test_login_api(case, api_client):
    # 使用工厂构造用户（若数据中包含用户属性）
    user = UserFactory(**case.get("user", {}))
    resp = api_client.login(user.email, case["password"])
    assert resp.status_code == case["expected_status"]
```

你现在是想**为复杂的业务对象（如订单、支付记录）实现工厂类**，还是想**搭建一套基于CSV/Excel的数据驱动测试框架**？告诉我你的项目业务特征（如ORM类型、数据结构复杂度），我可以为你定制一套工厂 + 数据驱动的完整代码模板，包含清理策略和性能优化建议。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[基于标记的条件执行与过滤筛选]]
- [[内置标记]]
- [[pytest-cov配置与多模式报告生成]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, coverage, assertion, conftest, markers, xfail）
> - [+] 新增 H1「数据驱动测试与测试工厂（Factory）模式」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
