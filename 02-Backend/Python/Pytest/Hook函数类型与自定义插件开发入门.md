---
tags: [pytest, testing, python, fixture, plugins, conftest, markers, skip, cli, reporting]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: Hook函数类型与自定义插件开发入门.md
---
# Hook函数类型与自定义插件开发入门

## 📌 一句话总结
> 这是PyTest架构中最具深度的领域——**插件开发**。如果说Fixture和标记是PyTest的“招式”，那么Hook函数就是它的“经脉”。通过Hook，你可以拦截PyTest的执行生命周期，实现从**测试收集**到**结果报告**的全链路定制。

我将按照**Hook类型（生命周期分层）**、**本地插件（conftest.py） vs 安装包插件**、**实战开发一个插件**以及**调试技巧**四个维度，带你入门自定义插件开发。

## 🎯 核心概念

### 1. Hook函数的类型（生命周期分层）

PyTest定义了**数百个**Hook函数，按执行阶段可以分为六大类。理解它们出现的顺序，是开发插件的核心基础。

| 阶段 | 核心Hook | 触发时机 | 典型用途 |
| :--- | :--- | :--- | :--- |
| **启动初始化** | `pytest_addoption`<br>`pytest_configure` | PyTest启动时，收集测试之前 | 添加自定义命令行参数、注册标记、修改配置 |
| **测试收集** | `pytest_collect_file`<br>`pytest_generate_tests`<br>`pytest_collection_modifyitems` | 扫描测试文件和函数时 | 动态生成参数、修改测试顺序、添加/删除测试用例 |
| **测试运行（Setup）** | `pytest_runtest_setup` | 每个测试执行**前** | 根据标记动态跳过测试、注入环境变量 |
| **测试运行（Call）** | `pytest_runtest_call` | 执行测试函数本体时 | 拦截测试执行，添加超时或重试逻辑 |
| **测试运行（Teardown）** | `pytest_runtest_teardown` | 每个测试执行**后**（无论成败） | 清理资源、统计失败信息 |
| **结果报告** | `pytest_runtest_makereport`<br>`pytest_terminal_summary` | 测试执行完毕后，生成报告时 | 自定义输出格式、发送通知、生成HTML报告 |

### 2. 开发模式：本地插件（conftest.py）vs 安装包插件

入门阶段，**99%的自定义需求**只需在项目根目录的 `conftest.py` 中实现Hook即可（本地插件），无需打包。

| 维度 | **本地插件（conftest.py）** | **安装包插件（可复用）** |
| :--- | :--- | :--- |
| **存放位置** | 项目根目录或测试子目录下 | 独立的Python包，通过`pip`安装 |
| **加载方式** | PyTest自动发现（根据目录层级） | 通过`setuptools`的`pytest11`入口点注册 |
| **适用场景** | 项目特定的定制（如业务标记校验） | 跨项目通用（如公司内部测试基建） |
| **开发复杂度** | 低（即写即用） | 中（需配置`pyproject.toml`和打包） |

**入门建议**：先在 `conftest.py` 中开发，验证逻辑正确后，再考虑打包为通用插件。

### 3. 实战入门：开发一个“标记校验”插件

**需求**：强制要求所有 `integration` 标记的测试必须同时带上 `slow` 或 `smoke` 标记，否则在收集阶段直接报错阻止执行。

#### 步骤一：在 `conftest.py` 中实现 `pytest_collection_modifyitems`

```python
# conftest.py
import pytest

def pytest_collection_modifyitems(config, items):
    """
    在测试收集完成后、执行前调用。
    遍历所有收集到的测试项，检查标记规则。
    """
    for item in items:
        # 1. 检查测试是否带有 'integration' 标记
        if item.get_closest_marker("integration"):
            # 2. 检查是否同时携带了 'slow' 或 'smoke'
            has_slow = item.get_closest_marker("slow") is not None
            has_smoke = item.get_closest_marker("smoke") is not None
            
            if not (has_slow or has_smoke):
                # 3. 如果不符合规则，构造错误信息并抛出
                error_msg = (
                    f"测试 '{item.name}' 标记了 'integration'，"
                    f"但未同时标记 'slow' 或 'smoke'。"
                    f"位置: {item.fspath}:{item. lineno if hasattr(item, 'lineno') else '?'}"
                )
                # 在收集阶段失败，PyTest将不会执行任何测试
                raise pytest.CollectError(error_msg)
```

**效果**：若有人写了 `@pytest.mark.integration` 但忘了加 `slow`/`smoke`，执行 `pytest` 会立即报错并停止，而非等到测试失败时才发现。

### 4. 进阶实战：添加自定义命令行参数（`pytest_addoption`）

通过自定义命令行参数，可以让插件的执行行为受外部控制。

**需求**：新增一个 `--demo-mode` 参数，当开启时，跳过所有 `slow` 标记的测试。

```python
# conftest.py
import pytest

def pytest_addoption(parser):
    # 添加自定义命令行选项
    parser.addoption(
        "--demo-mode", 
        action="store_true", 
        default=False, 
        help="快速演示模式：跳过所有 slow 标记的测试"
    )

def pytest_collection_modifyitems(config, items):
    # 获取命令行参数值
    if config.getoption("--demo-mode"):
        skip_slow = pytest.mark.skip(reason="演示模式下跳过慢速测试")
        for item in items:
            if item.get_closest_marker("slow"):
                item.add_marker(skip_slow)
```

**用法**：`pytest --demo-mode tests/`，所有 `slow` 测试被自动标记为跳过。

### 5. 第三个实战：自定义测试报告摘要（`pytest_terminal_summary`）

**需求**：在测试结束后，额外输出一句“测试完成！总耗时 X 秒”。

```python
# conftest.py
import time

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    # terminalreporter 可以控制终端输出
    total_seconds = time.time() - terminalreporter._sessionstarttime
    terminalreporter.write_sep("=", f"🏁 测试完成！总耗时 {total_seconds:.2f} 秒", yellow=True)
```

### 6. 如何打包为可安装的插件（进阶参考）

当你的Hook逻辑需要跨项目复用时，可打包为外部插件：

1.  **目录结构**：
```python
    pytest_myplugin/
    ├── src/
    │   └── pytest_myplugin.py      # 包含Hook实现
    ├── pyproject.toml
    └── README.md
    ```

2.  **`pyproject.toml` 中注册入口点**：
    ```toml
    [project.entry-points.pytest11]
    myplugin = "pytest_myplugin"  # 命名空间，PyTest会通过它加载
    ```

3.  **用户安装**：`pip install -e .` 即可生效。

### 7. 极易踩中的 3 个开发陷阱

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **Hook 函数签名错误（`TypeError`）** | PyTest调用时传入的参数数量或名称与Hook定义不匹配。例如 `pytest_collection_modifyitems(config, items)` 少写了 `config`。 | 查阅官方文档，**严格复制**签名。可以使用 `*args, **kwargs` 作为通配，但不推荐（会失去自省）。 |
| **在 `conftest.py` 中使用 `pytest_plugins` 变量报错** | 在非根目录的 `conftest.py` 中使用 `pytest_plugins` 已被废弃。 | 若需加载其他插件模块，请在**根目录的 `conftest.py`** 中定义该变量，或直接在测试文件中 `import`。 |
| **Hook 中修改 `items` 列表导致收集计数错乱** | 直接 `items.append` 或 `items.pop` 未正确处理迭代器。 | 若需删除，**反向迭代**或使用 `items[:] = new_list` 整体替换；若需添加，确保新项具有正确的父节点信息（较复杂，不建议入门阶段做）。 |

### 8. 诊断技巧：查看哪些Hook被触发了

```bash
# 开启调试模式，打印详细的Hook执行日志
pytest --trace-config

# 查看当前环境中所有可用的Hook函数（包括插件的）
pytest --help | grep "pytest_"
```

### 9. 核心Hook速查表（入门必备）

| Hook | 最常用参数 | 核心用途 |
| :--- | :--- | :--- |
| `pytest_addoption` | `parser` | 添加自定义命令行参数 |
| `pytest_configure` | `config` | 注册自定义标记、添加动态配置 |
| `pytest_collection_modifyitems` | `config, items` | **最常用**：修改/过滤/排序测试用例 |
| `pytest_runtest_setup` | `item` | 测试执行前的准备工作，可调用 `pytest.skip()` |
| `pytest_runtest_makereport` | `item, call` | 获取测试执行结果（Pass/Fail/Skip），用于自定义报告 |
| `pytest_terminal_summary` | `terminalreporter` | 在终端输出额外信息（统计、通知） |

你现在是想**在CI中强制校验标记规范**（如上述的 integration + slow 校验），还是想**自定义测试报告格式**（如输出JSON供前端展示）？告诉我具体场景，我可以直接给你一段可直接放入 `conftest.py` 的完整Hook代码，并说明其执行时机。你选哪个？

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[基于标记的条件执行与过滤筛选]]
- [[内置标记]]
- [[pytest命令行参数详解]]
- [[pytest自动发现机制]]
- [[自定义标记注册与业务语义映射]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, plugins, conftest, markers, skip, cli, reporting）
> - [+] 新增 H1「Hook函数类型与自定义插件开发入门」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
