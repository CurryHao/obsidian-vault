---
tags: [pytest, testing, python, assertion, exception, hooks, conftest, unittest, registration]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: conftest黑魔法核心.md
---
# conftest黑魔法核心

## 📌 一句话总结
> 这无疑是`pytest`最令人拍案叫绝的“黑魔法”核心。如果说“约定优于配置”是`pytest`的骨架，那么**断言重写（Assertion Rewriting）** 就是它的灵魂。

在原生Python中，当你执行`assert a == b`失败时，你只会得到一句赤裸裸的`AssertionError`，完全不知道`a`和`b`到底是什么。而`pytest`通过**AST（抽象语法树）重写**，在运行时将你的断言语句“偷梁换柱”，注入了强大的自省代码，把冷冰冰的失败变成了**即时的调试会话（Instant Debugging Session）**。

## 🎯 核心概念

### 1. 机制揭秘：Python 的“编译时魔法”

`pytest` 并没有修改Python解释器的底层`assert`指令，而是在**测试收集阶段**，将测试模块的源码解析成AST，然后将`assert`节点替换为自定义的`pytest`断言自省节点。

**关键区别：**

- **原生Python**：`assert a == b` → 虚拟机判断布尔值 → `False`则抛出异常（不保存任何现场变量）。
- **Pytest重写后**：`assert a == b` → 拆解为 `assert 比较( a, b )`，同时记录了`a`和`b`的具体值、`repr()`展示，甚至递归进入容器内部。

这一特性由 `pytest` 的 `AssertionRewritingHook` 钩子实现，它会在模块导入时生效。**唯一要求**：你的测试文件必须被`pytest`收集（即以`test_`开头），而非直接作为普通脚本被Python解释器执行。

### 2. 深入实战：它能“自省”到什么程度？

让我们通过几个实际场景，感受下它如何将你的调试时间从分钟级缩短到秒级。

#### 场景一：基础数据类型（直观展示）
```python
def test_basic_values():
    expected = 100
    actual = 50 + 30   # 等于80
    assert actual == expected
```
**原生断言输出**：`AssertionError`
**Pytest 重写后输出**：
```python
E       assert 80 == 100
```
你一眼就能看出计算少了20，无需打印变量。

#### 场景二：深度容器比较（递归揭示差异）
这是最惊艳的部分。当比较列表、字典或自定义对象时，它会**精准定位到差异发生的下标或键**。

```python
def test_deep_list():
    expected = [1, 2, {"name": "Alice", "age": 25}]
    actual   = [1, 2, {"name": "Bob",   "age": 25}]
    assert actual == expected
```
**Pytest 输出（结构化展示）**：
```python
E       assert [1, 2, {'age': 25, 'name': 'Bob'}] == [1, 2, {'age': 25, 'name': 'Alice'}]
E         
E         At index 2: dict items differ
E           Common keys: {'age', 'name'}
E           Differing values:
E             'name' : 'Bob' != 'Alice'
```
它自动识别出只有`name`字段不同，而且精准指向了`index 2`，这在调试复杂的API JSON响应时简直是神技。

#### 场景三：复杂逻辑表达式（拆解中间值）
当你用`and`或`or`连接多个条件时，`pytest`会通过**括号展开（Bracket Unrolling）** 告诉你哪个子句出了问题。

```python
def test_complex_logic():
    a, b, c = 1, 2, 0
    assert a > 0 and b < 5 and c > 10  # c > 10 失败
```
**Pytest 输出**：
```python
E       assert (1 > 0 and 2 < 5 and 0 > 10)
E         -> False
E         where 0 > 10 is False
```
它明确提示`c > 10`为`False`，而不是笼统地说“整个逻辑为假”。

#### 场景四：异常匹配的自省（`pytest.raises`）
配合异常测试时，如果抛出的异常消息不符，它也会展示差异：

```python
def test_exception_msg():
    with pytest.raises(ValueError, match="Invalid ID"):
        raise ValueError("Invalid id")  # 大小写不一致
```
**输出**：
```python
E       Pattern 'Invalid ID' not found in 'Invalid id'
```

### 3. 必须绕开的 3 个“失效陷阱”

尽管重写很强，但它**不是万能的**。以下几种情况重写机制不会生效，你会退化成原生`AssertionError`，失去自省能力：

1.  **脱离 `pytest` 运行**：直接使用 `python test_xxx.py` 执行，而非 `pytest test_xxx.py`。重写只在pytest的导入钩子下发生。
2.  **在 `unittest.TestCase` 子类中使用 `assert`**：如果你为了兼容旧代码写了 `class MyTest(unittest.TestCase):`，里面的 `assert` 会退化为原生断言（因为pytest为了兼容该框架的异常处理机制，不会重写其内部的断言）。**解决方案**：要么完全改用普通函数，要么继续使用`self.assertEqual`。
3.  **在 `conftest.py` 或非测试辅助模块中未显式注册**：如果你的工具函数写在 `utils.py` 中，并被测试函数导入，`pytest` 默认不会重写 `utils.py` 里的断言。若需要，必须在 `conftest.py` 中调用 `pytest.register_assert_rewrite('utils')` 提前注册。

### 4. 进阶技巧：利用 `--assert=plain` 关掉魔法

虽然几乎用不到，但如果你怀疑重写机制干扰了调试（比如重写导致复杂的 `__eq__` 方法被无限递归调用），你可以临时关闭重写：
```bash
pytest --assert=plain
```
此时所有断言退化为原生Python，以验证是否是重写引发的问题。

### 5. 思维导图速查

- **核心机制**：收集期 AST 替换 → 注入自省变量
- **输出特征**：显示 `左值` vs `右值`，递归展示容器差异
- **适用场景**：数值计算、API接口校验、数据结构比对、正则匹配
- **失效场景**：原生`python`启动、`unittest`类内部、未注册的第三方模块

现在，你是否想亲手验证一下这个“黑魔法”？你可以随手写一个包含**嵌套字典**的测试，故意把某个值写错，然后运行`pytest -v`。观察那个报错信息——你会爱上这种**所见即所得**的调试体验。如果遇到某个特殊的数据结构（比如`dataclass`或`numpy`数组）断言信息不够清晰，可以告诉我，我们还可以探讨如何利用 `pytest_assertrepr_compare` 钩子进行**自定义输出美化**。你想试试吗？

## 🔗 关联笔记
- [[conftest.py的共享机制与作用域隔离]]
- [[assert语句的增强输出与重写原理]]
- [[Hook函数类型与自定义插件开发入门]]
- [[异常断言（pytest.raises）与异常文本匹配]]
- [[unittest迁移到pytest实战]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, assertion, exception, hooks, conftest, unittest, registration）
> - [+] 新增 H1「conftest黑魔法核心」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
