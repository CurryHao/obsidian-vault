---
tags: [pytest, testing, python, fixture, coverage, assertion, plugins, conftest, markers, xfail]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: pytest命令行参数详解.md
---
# pytest命令行参数详解

## 📌 一句话总结
> 命令行是`pytest`的**控制中枢**。掌握这些参数，你就能像指挥家一样，精准调度测试套件的执行范围、输出粒度和失败处理策略。

我按照**“选什么、怎么跑、看什么”**的逻辑，把最核心的参数分为四大类。记住一个黄金原则：**在CI脚本或团队文档中，永远使用 `python -m pytest` 而非裸 `pytest`**，前者能确保使用当前虚拟环境中的正确解释器。

## 🎯 核心概念

### 1. 测试选择器（跑哪些？）

| 参数/语法 | 作用 | 实战示例 |
| :--- | :--- | :--- |
| **指定路径/文件** | 运行特定文件或目录 | `python -m pytest tests/unit/` <br> `python -m pytest tests/test_login.py` |
| **`::` 节点选择器** | 精准定位到类、方法或函数（**最常用调试技巧**） | `python -m pytest tests/test_api.py::TestUserAPI` <br> `python -m pytest tests/test_api.py::TestUserAPI::test_create_user` |
| **`-k EXPRESSION`** | 按**名称模糊匹配**（支持 `and` / `not` / `or`） | `python -m pytest -k "login or logout"` <br> `python -m pytest -k "not slow"`  （排除含slow的用例） |
| **`-m MARKEXPR`** | 按**自定义标记**选择（需配合 `pytest.ini` 注册） | `python -m pytest -m "smoke"` <br> `python -m pytest -m "not regression"` <br> `python -m pytest -m "smoke and not slow"` |

### 2. 执行控制（怎么跑？）

| 参数 | 作用 | 实战场景 |
| :--- | :--- | :--- |
| **`-x` / `--maxfail=NUM`** | 遇到第一个失败立即停止 / 失败达到N个后停止 | CI快速反馈（`-x`）；本地调试时避免浪费CPU |
| **`--lf` (--last-failed)** | **仅重新运行**上次运行失败的用例（极速修复工作流） | 失败修复后，`pytest --lf` 只跑失败的那几个 |
| **`--ff` (--failed-first)** | 先跑失败的用例，再跑其余的 | 比 `--lf` 更激进，适合有信心的重构 |
| **`-n NUM`** (需 `pytest-xdist`) | 启用并行执行，指定CPU核心数 | `pytest -n 4` 将测试分摊到4个进程，大幅提速 |
| **`--maxprocesses=NUM`** | 配合 `-n auto` 限制最大进程数 | CI资源受限时的安全阀 |
| **`--durations=N`** | 显示执行最慢的N个测试（**性能分析神器**） | `pytest --durations=5` 揪出耗时最长的瓶颈用例 |

### 3. 输出与日志（看什么？）

这是最影响调试体验的一组参数。

| 参数 | 作用 | 关键细节 |
| :--- | :--- | :--- |
| **`-v` (--verbose)** | 详细模式，显示每个用例的名称和结果 | 收集时显示 `collected 5 items`，执行时每个`PASSED`/`FAILED`单独一行 |
| **`-q` (--quiet)** | 安静模式，减少输出（CI常用） | 只显示全局结果，适合大量用例的简要汇报 |
| **`-s`** | **关闭捕获**，让 `print()` 和 `logging` 输出到控制台 | **调试时必加**。注意：`-s` 会压制 `-v` 的部分效果，建议两者都用 `-sv` |
| **`--tb=STYLE`** | 控制失败回溯信息的详细程度 | `--tb=short`（精简）、`--tb=long`（详尽）、`--tb=no`（关闭回溯，只看断言结果）、`--tb=line`（每个失败只显示一行） |
| **`-r`** | 显示额外的测试结果摘要 | `-ra` 显示 `(a)ll` 额外结果（`PASSED`除外）；`-rf` 显示失败详情；`-rx` 显示 `XFAIL`/`XPASS` |
| **`--no-header`** | 隐藏Pytest版本、插件列表等头部信息 | 让CI日志更干净 |
| **`--no-summary`** | 隐藏最后的统计摘要 | 配合 `-q` 实现极简输出 |

### 4. 诊断与调试（出问题怎么办？）

| 参数 | 作用 | 示例 |
| :--- | :--- | :--- |
| **`--collect-only`** | **只收集测试，不执行**。列出所有将被运行的用例节点ID | 检查命名是否正确，或确认 `conftest.py` 是否被正确加载 |
| **`--setup-show`** | 显示每个测试执行前后的 `Setup`/`Teardown` 固件链条 | 排查Fixture依赖泄漏或执行顺序混乱 |
| **`--pdb`** | 测试**失败时**自动进入 `pdb` 调试器 | `python -m pytest --pdb -x` （失败即停，并进入断点） |
| **`--trace`** | 在执行**每个测试之前**进入调试器 | 极其精细的单步调试，用于追踪诡异的并发问题 |
| **`-l` (--showlocals)** | 在回溯信息中显示失败处的**局部变量值** | 免去手动加 `print`，快速定位脏数据 |

### 5. 组合技：三个高频实战命令

我将三个最常用的命令场景固化下来，你可以直接复制到终端执行：

| 场景 | 终极命令 | 解释 |
| :--- | :--- | :--- |
| **日常开发（快速验证）** | `python -m pytest -xvs` | 失败即停(`-x`) + 详细(`-v`) + 显示print(`-s`)，即时反馈 |
| **修复历史失败的用例** | `python -m pytest --lf -v --tb=short` | 只跑上次失败的(`--lf`)，回溯精简，集中火力修复 |
| **提交前全量回归（含覆盖率）** | `python -m pytest tests/ -n auto --cov=src --cov-report=term --durations=3` | 全量并行 + 覆盖率报告 + 分析最慢的3个用例 |

### 6. 极易踩中的 3 个命令行陷阱

| 陷阱表现 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **加了 `-s` 还是看不到 `print`** | 你同时加了 `--capture=fd` 或日志级别被 `log_cli` 覆盖 | 使用 `-s` 足以，若不行，检查 `pyproject.toml` 中是否有 `log_cli = false` |
| **`-k "test login"` 匹配不到任何测试** | Shell解析引号出错，或在 Windows CMD 中语法不同 | 在 Unix 下用双引号包裹表达式：`-k "login or logout"`；**在 Windows PowerShell 中，建议使用单引号** `-k 'login or logout'`，或使用 `--` 分隔：`pytest -- -k "login"` |
| **`--lf` 运行后显示 `no tests ran`** | 上一次运行的 `.pytest_cache/v/cache/lastfailed` 文件被删除或损坏 | 先跑一次全量 `pytest` 生成缓存，或手动删除 `.pytest_cache` 目录重置 |

### 7. 参考速查：`pytest --help` 的定制化

如果你想看当前配置下所有可用的参数（包括插件注入的自定义参数），直接在终端执行：
```bash
python -m pytest --help
```
你会看到最后列出的 `custom options`，那是你安装的 `pytest-cov`、`pytest-xdist` 等插件注入的专属参数。

您目前手头是要跑一个**单模块的快速验证**，还是要在CI上配置**全量并发执行**？告诉我具体场景，我可以直接帮您拼好一条最终命令，并解释每个碎片的作用，让您即拿即用。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[conftest.py的共享机制与作用域隔离]]
- [[基于标记的条件执行与过滤筛选]]
- [[内置标记]]
- [[pytest-cov配置与多模式报告生成]]
- [[排除代码（exclude）与覆盖率阈值设定]]
- [[自定义标记注册与业务语义映射]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, coverage, assertion, plugins, conftest, markers, xfail）
> - [+] 新增 H1「pytest命令行参数详解」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
