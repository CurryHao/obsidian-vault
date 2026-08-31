---
tags: [pytest, testing, python, fixture, assertion, plugins, unittest, discovery, inheritance, readability]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: Python测试框架谱系对比.md
---
# Python测试框架谱系对比

## 📌 一句话总结
> 当我们谈论Python的测试框架谱系时，`unittest`、`doctest`和`nose`（以及它的继任者`nose2`）代表了从**内置标准工具**到**社区增强**再到**现代范式**的演进过程。

我把它们的核心区别整理成了下面这个表格，方便你快速把握全貌：

| 特性 | **unittest** | **doctest** | **nose / nose2** |
| :--- | :--- | :--- | :--- |
| **类型** | 内置标准库 | 内置标准库 | 第三方扩展库 |
| **设计风格** | xUnit风格，基于类继承 | 文档驱动，基于交互式示例 | unittest的“增强版” |
| **写法与断言** | 需继承`unittest.TestCase`，使用`self.assertEqual()`等方法 | 在文档字符串中编写`>>>`交互式示例 | 兼容unittest写法，也支持更自由的函数式测试 |
| **主要优势** | 零依赖，稳定可靠，是其他框架的基础 | 测试即文档，确保文档示例始终正确 | 自动发现测试，比unittest更方便 |
| **主要局限** | 样板代码较多，不够灵活 | 不适合复杂测试，会污染文档 | nose已停止维护；nose2相对小众 |
| **当前状态** | **仍在使用**，是Python的基石 | **仍在使用**，作为文档验证的补充 | **逐渐被pytest取代**，成为现代标准 |

## 🎯 核心概念

### 1. unittest：Python官方钦定的“标准答案”

`unittest`是Python官方自带的单元测试框架，灵感来源于Java的JUnit。它最大的优点就是**无需安装**，开箱即用，因此成为了许多大型项目和旧有代码库的基石。它的核心是**xUnit风格**，要求你通过继承`unittest.TestCase`类来创建测试用例。

### 2. doctest：藏在文档里的“活例子”

`doctest`是另一个内置模块，它的理念很巧妙：**将写在文档字符串（docstring）里的交互式示例直接作为测试用例**。它非常适合用来验证文档中的示例代码是否仍然有效，起到了“**测试即文档，文档即测试**”的作用。但它不适合作为主要的测试框架，因为全面的测试用例会严重拖累文档的可读性。

### 3. nose：让unittest“更好用”的尝试

`nose`是一个**第三方扩展库**，旨在让基于`unittest`的测试**编写、发现和运行变得更简单**。它最大的贡献是**自动发现测试**，你不再需要手动创建测试套件（TestSuite），`nose`能自动找到并运行测试。然而，`nose`项目已经进入维护模式，官方推荐新项目使用其他替代方案。它的继任者`nose2`继承了这一理念，但在`pytest`的强势崛起下，影响力有限。

### 深入对比：从“写一个测试”看差异

为了让你更直观地感受差异，我们用一个简单的加法函数测试来对比这三种框架：

*   **unittest**：需要编写一个类，继承`TestCase`，并使用特定的`assert`方法。
*   **doctest**：测试代码直接写在函数的文档字符串里，看起来像在Python交互式终端里操作。
*   **nose**：写法更自由，可以直接写一个以`test`开头的普通函数，使用Python原生的`assert`语句。这也是`pytest`所推崇的更简洁的风格。

```python
# ---------- 待测试的函数 ----------
def add(x, y):
    """A simple add function."""
    return x + y

# ========== 1. unittest 风格 ==========
import unittest

class TestAddFunction(unittest.TestCase):
    def test_add_positive(self):
        self.assertEqual(add(2, 3), 5)  # 使用特殊的assert方法

    def test_add_negative(self):
        self.assertEqual(add(-1, -1), -2)

# ========== 2. doctest 风格 ==========
def add(x, y):
    """
    A simple add function.

    >>> add(2, 3)
    5
    >>> add(-1, -1)
    -2
    """
    return x + y

# ========== 3. nose 风格 ==========
# nose 完全兼容上面的 unittest 风格
# 同时也支持更简洁的函数风格
def test_add_positive():
    assert add(2, 3) == 5  # 使用Python原生assert

def test_add_negative():
    assert add(-1, -1) == -2
```

### 总结：如何选择？

*   如果你的项目**极其简单**，或者你**不想引入任何外部依赖**，`unittest`依然是一个可靠的选择。
*   如果你希望**确保文档中的示例代码永远正确**，那么`doctest`是一个极佳的辅助工具。
*   但对于**大多数现代Python项目**，社区的主流选择已经转向了**`pytest`**。`pytest`不仅兼容`unittest`和`doctest`的测试用例，还提供了更简洁的语法、强大的固件（Fixture）系统和丰富的插件生态。

了解这些框架的谱系，能帮你更好地理解`pytest`为何成为今日的首选。你目前是在维护一个使用`unittest`的旧项目，还是打算为新项目选择测试框架呢？告诉我你的具体情况，我可以为你提供更针对性的建议。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[assert语句的增强输出与重写原理]]
- [[unittest迁移到pytest实战]]
- [[pytest自动发现机制]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, assertion, plugins, unittest, discovery, inheritance, readability）
> - [+] 新增 H1「Python测试框架谱系对比」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
