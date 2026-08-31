---
tags: [pytest, testing, python, fixture, parametrize, plugins, hooks, conftest, markers, unittest]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: Fixture定义语法与自动使用.md
---
# Fixture定义语法与自动使用

## 📌 一句话总结
> 测试执行顺序是`pytest`中一个常被误解但至关重要的细节。官方明确宣称：**默认顺序是确定的（Deterministic），但不是依赖性的（Dependency-free）**。

具体而言，`pytest` 默认按 **"文件系统顺序 + 定义顺序"** 执行，且**故意打乱了类内方法按名称排序的常规做法**。更重要的是，`pytest` 提供了强大的 **收集钩子（Collection Hooks）**，允许你完全掌控排序逻辑。

我将从**默认算法**、**自定义收集钩子**、以及**踩坑指南**三个维度为你拆解。

## 🎯 核心概念

### 1. 默认执行顺序算法（源码级规则）

当你执行 `pytest` 时，收集到的所有测试项（Item）会被放入一个列表，排序规则如下（按优先级从高到低）：

1. **文件级别**：按 `os.listdir()` 返回的顺序执行（通常是**ASCII/Unicode 字符串升序**，即 `test_a.py` 先于 `test_z.py`）。
2. **类级别**：按类在文件中出现的**定义顺序**执行。
3. **函数/方法级别**：按在类中或文件中**定义的上下文字面顺序**执行。
4. **参数化（Parametrize）**：按参数列表的**传入顺序**执行。

> **极其重要的特殊规则**：`pytest` **不会**像 `unittest` 那样按方法名（`test_a`、`test_b`）的字母序排序。如果你依赖类内方法的字母序，默认情况下你的假设会落空。

**验证脚本示例**（新建 `test_order.py`）：
```python
import pytest

class TestA:
    def test_b(self): print("B")
    def test_a(self): print("A")  # 定义在 test_b 之后，所以后执行

class TestZ:  # 这个类在 TestA 之后定义，所以后执行
    def test_c(self): print("C")

def test_d(): print("D")  # 在类之后定义，最后执行
```
执行 `pytest -sv`，输出顺序将是：`B` → `A` → `C` → `D`。顺序完全由代码行号决定。

### 2. 核心钩子：`pytest_collection_modifyitems`（排序控制中枢）

这是`pytest`提供给开发者修改测试执行顺序的**官方入口**。你在 `conftest.py` 中实现这个钩子函数，就能在测试收集完成后、执行开始前，任意调整 `items` 列表。

#### 实战案例 1：按标记（Marker）排序（慢速测试移到最后）
```python
# conftest.py
import pytest

def pytest_collection_modifyitems(config, items):
    """将标记为 'slow' 的测试全部移动到执行队列的末尾"""
    # 构建两个队列：慢速和非慢速
    slow_items = []
    other_items = []
    
    for item in items:
        if item.get_closest_marker("slow"):
            slow_items.append(item)
        else:
            other_items.append(item)
    
    # 清空原列表，先执行非慢速，最后执行慢速
    items[:] = other_items + slow_items
```
*执行效果*：本地开发时，快速用例先跑完给你即时反馈，耗时的数据库迁移用例最后再跑。

#### 实战案例 2：按模块路径逆序执行（模拟压力测试）
```python
def pytest_collection_modifyitems(config, items):
    # 按文件路径的字符串逆序排列（简单的反转）
    items.sort(key=lambda x: x.module.__name__, reverse=True)
```

#### 实战案例 3：将特定类或函数的测试强制提前
```python
def pytest_collection_modifyitems(config, items):
    # 将 "TestSmoke" 类中的所有用例提到列表最前面
    items.sort(
        key=lambda x: 0 if "TestSmoke" in x.parent.name else 1
    )
```

### 3. 更细粒度的钩子：`pytest_runtest_protocol` 与 `pytest_runtest_setup`

如果你不仅想改顺序，还想**在运行每个测试前后插入自定义逻辑**，可以结合使用：
- **`pytest_runtest_setup(item)`**：在每个测试的 `setup` 阶段触发，可用来动态跳过或报错。
- **`pytest_runtest_teardown(item)`**：清理阶段触发。

**注意**：直接修改顺序通常用 `pytest_collection_modifyitems` 就足够了，后者更适合干预固件（Fixture）的初始化行为，而非顺序。

### 4. 第三方插件：放弃手动，拥抱懒人方案

如果不想手写钩子，社区提供了开箱即用的插件：

| 插件 | 用法 | 典型场景 |
| :--- | :--- | :--- |
| **`pytest-order`** | 在测试函数上使用 `@pytest.mark.order(1)`、`@pytest.mark.order(2)` | 定义严格的线性依赖（如“先注册后登录”） |
| **`pytest-random-order`** | 执行 `pytest --random-order` | **种子随机化（Seed Randomization）**，用于检测测试间的隐性依赖（这是最高级别的测试隔离质量检验） |

> **业界共识**：如果你的测试依赖于执行顺序（比如 `TestA` 必须先于 `TestB` 跑），这通常意味着**测试没有实现隔离**。正确的做法是使用 Fixture 共享状态，而非依赖排序。

### 5. 极易踩中的 3 个致命陷阱

| 陷阱 | 错误表现 | 解决方案 |
| :--- | :--- | :--- |
| **在 `unittest.TestCase` 中按字母序的惯性思维** | 认为 `test_a` 一定比 `test_b` 先跑，结果发现顺序混乱 | 要么接受 `pytest` 的定义顺序，要么用 `pytest-order` 显式标注 |
| **`pytest_collection_modifyitems` 修改了 `items` 但没截断** | 直接使用 `items = new_list`，导致原列表未被修改，排序无效 | 必须使用切片赋值：`items[:] = sorted_items` |
| **参数化测试的排序混乱** | 认为参数化生成的多条用例会按顺序聚在一起，实际上它们可能被其他用例穿插 | 参数化用例的节点 ID 包含参数索引，钩子中可通过 `item.callspec.id` 获取并排序 |

### 6. 黄金法则与推荐实践

1. **默认情况下，不要依赖顺序**。这是 TDD 的第一原则。
2. **若必须手动排序（如为了 CI 日志美观）**，优先使用 `conftest.py` 中的 `pytest_collection_modifyitems` + 标记（Marker）组合，而非硬编码文件名。
3. **定期使用随机顺序插件**：在 CI 的某个夜间构建任务中启用 `--random-order`，可以及早暴露那些“隐式依赖”的坏味道测试。

您是想**强制将某种标记（如冒烟测试）提前执行**，还是想**处理现有代码中因依赖顺序导致偶尔变红（Flaky Tests）的顽疾**？告诉我您的痛点，我可以为您写一段可直接放入 `conftest.py` 的钩子代码，配合您的项目结构即插即用。

## 🔗 关联笔记
- [[conftest.py的共享机制与作用域隔离]]
- [[单参数与多参数笛卡尔积组合]]
- [[Hook函数类型与自定义插件开发入门]]
- [[内置标记]]
- [[unittest迁移到pytest实战]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, parametrize, plugins, hooks, conftest, markers, unittest）
> - [+] 新增 H1「Fixture定义语法与自动使用」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
