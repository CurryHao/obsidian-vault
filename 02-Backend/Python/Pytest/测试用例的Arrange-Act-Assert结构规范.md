---
tags: [pytest, testing, python, fixture, parametrize, mock, assertion, exception, conftest, data-driven]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 测试用例的Arrange-Act-Assert结构规范.md
---
# 测试用例的Arrange-Act-Assert结构规范

## 📌 一句话总结
> 这是将测试代码从“能跑”提升到“优雅可维护”的关键分水岭。**Arrange-Act-Assert（简称 AAA）** 是单元测试领域最具普适性的结构范式，它不仅是代码格式规范，更是一种**思维框架**——强制你以“场景”为单位思考，而非以“函数”为单位。

在 `pytest` 语境下，我将从**黄金法则**、**代码物理分层**、**与Fixture的边界划分**以及**反模式警示**四个维度，为你彻底讲透这套规范。

## 🎯 核心概念

### 1. 黄金法则：三段式物理分隔

每个测试用例应严格按顺序划分为三个逻辑区块，并用**空行**或**注释**物理隔开：

| 阶段 | 别名（BDD语境） | 核心职责 | 严禁行为 |
| :--- | :--- | :--- | :--- |
| **Arrange（准备）** | **Given（给定）** | 初始化被测对象、构造输入数据、设置Mock期望、准备数据库状态 | 执行被测业务方法、做断言验证 |
| **Act（执行）** | **When（当）** | **仅调用**被测系统（SUT）的目标方法/API | 在此阶段改变SUT的构造逻辑，或混入断言 |
| **Assert（验证）** | **Then（则）** | 使用 `assert` 检查返回值、异常、状态变更或Mock调用 | 修改任何共享状态（此时仅做只读检查） |

**标准代码物理模板**：
```python
def test_user_can_upgrade_to_premium():
    # Arrange（准备）
    user = User(name="Alice", role="free")
    upgrade_service = PremiumUpgradeService()
    
    # Act（执行）
    result = upgrade_service.upgrade(user)
    
    # Assert（验证）
    assert result.is_success is True
    assert user.role == "premium"
```

### 2. 与 `pytest` Fixture 的边界划分（最易混淆点）

`pytest` 的 Fixture 机制常让人误以为“所有的 Arrange 都要塞进 Fixture”。正确的划分原则是：

- **Fixture 负责：跨用例复用的“重量级/基础设施型” Arrange**（如数据库连接、API客户端、标准测试数据实体）。
- **测试函数体内负责：用例特定的“轻量级/场景型” Arrange**（如针对当前Case的输入构造、特定Mock参数调整）。

**错误示范（将所有Arrange塞进Fixture）**：
```python
@pytest.fixture
def premium_upgrade_scenario():
    # 坏味道：Fixture 内部做了太多特定于单个用例的细节
    user = User(name="Alice")
    service = PremiumUpgradeService()
    result = service.upgrade(user)  # ❌ 把 Act 也放进去了！
    return result, user
```
**正确拆分策略**：
```python
# conftest.py
@pytest.fixture
def standard_user():
    """只负责构造基础实体（Arrange的基础部分）"""
    return User(name="Alice", role="free")

# test_upgrade.py
def test_premium_upgrade(standard_user):
    # Arrange（场景特化）：基于基础fixture，设定当前case的上下文
    upgrade_service = PremiumUpgradeService()
    
    # Act（留在测试函数内，因为这是行为，而非资源）
    result = upgrade_service.upgrade(standard_user)
    
    # Assert
    assert standard_user.role == "premium"
```

### 3. 异常测试的 AAA 结构（Act 与 Assert 合并的例外）

当测试预期抛出异常时，`pytest.raises` 作为上下文管理器，天然将 **Act + Assert** 合并为一句，但逻辑上依然清晰：

```python
def test_upgrade_fails_for_invalid_user():
    # Arrange
    invalid_user = User(name="", role="free")
    service = PremiumUpgradeService()
    
    # Act + Assert（合并在 with 块中）
    with pytest.raises(ValueError, match="User name cannot be empty"):
        service.upgrade(invalid_user)  # 这一行既是 Act 也是 Assert 的触发器
```

**关键规范**：`with pytest.raises` 块内**只放那一行 Act 调用**，不要在里面塞其他的 Arrange 或额外的 Act，避免引发误报。

### 4. 三个极端的“坏味道”与重构策略

| 坏味道 | 表现形式 | 重构方案 |
| :--- | :--- | :--- |
| **巨型 Arrange（准备过长）** | 一个测试里创建了 6 个对象、3 个 Mock，占据 20+ 行 | 使用 **`factory` 辅助函数**或 `pytest.fixture` 封装对象构造；使用 `dict`/`dataclass` 聚合参数 |
| **多 Act（行为混杂）** | 同一个测试中连续调用 `update()` 和 `delete()`，断言放在两次调用之间 | **拆分为两个独立的测试用例**，每个用例只测一个行为 |
| **Assert 中包含逻辑计算** | `assert result.total == price * quantity + tax - discount` | 将复杂期望值提前计算并赋给具名变量：`expected_total = price * quantity + tax - discount`，然后 `assert result.total == expected_total` |

### 5. 进阶技巧：利用 `given` / `when` / `then` 注释增强可读性

在复杂集成测试中，即使有 Fixture，也建议显式写上注释标签。这在 Code Review 时能极大降低认知负担：

```python
def test_order_calculation_with_multi_items():
    # given - 构建上下文
    cart = ShoppingCart()
    cart.add_item(Item("book", price=10))
    cart.add_item(Item("pen", price=2))
    discount_code = "SAVE10"
    
    # when - 执行业务逻辑
    total = cart.checkout_with_discount(discount_code)
    
    # then - 验证状态
    assert total == 10.8  # (10+2) * 0.9
    assert cart.status == "checked_out"
    assert cart.items_count == 2
```

### 6. 结合参数化的 AAA 结构（数据驱动）

当使用 `@pytest.mark.parametrize` 时，Arrange 部分会变得更加简洁，但 AAA 逻辑依然保持：

```python
@pytest.mark.parametrize("input_price, discount, expected", [
    (100, 0.1, 90),
    (50, 0.5, 25),
    (0, 0.1, 0),
])
def test_discount_calculation(input_price, discount, expected):
    # Arrange（利用参数化输入）
    product = Product(price=input_price)
    
    # Act
    final_price = product.apply_discount(discount)
    
    # Assert（期望值来自参数）
    assert final_price == expected
```

### 7. 终极检查清单（写完测试后自问）

- [ ] **是否有明确的三个段落**？能否用 `# Arrange`、`# Act`、`# Assert` 对代码进行物理分区？
- [ ] **Act 部分是否只有一行核心方法调用**？（如果是多行，说明你在做多个动作）
- [ ] **Assert 只做验证，不做计算**？（期望值必须预先计算好并赋予变量）
- [ ] **Fixture 是否只承担“跨用例复用”的资源**，而不是承载特定场景的 Act 行为？

您现在编写的测试主要涉及**复杂业务逻辑（多层对象构造）** 还是**纯粹的数据转换函数（纯函数）**？如果是前者，我可以专门为您设计一套 **“测试数据工厂（Factory）”** 的封装模式，配合 AAA 结构，让您的 Arrange 阶段压缩到 3 行以内，大幅提升测试代码的可维护性。您想了解这个方案吗？

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[单参数与多参数笛卡尔积组合]]
- [[assert语句的增强输出与重写原理]]
- [[pytest-mock插件与unittest.mock无缝集成]]
- [[异常断言（pytest.raises）与异常文本匹配]]
- [[数据驱动测试与测试工厂（Factory）模式]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, mock, assertion, exception, conftest, data-driven）
> - [+] 新增 H1「测试用例的Arrange-Act-Assert结构规范」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
