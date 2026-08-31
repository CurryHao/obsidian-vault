---
tags: [pytest, testing, python, coverage, plugins, skip, cli, reporting, exclusion, pipeline]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: pytest-cov配置与多模式报告生成.md
---
# pytest-cov配置与多模式报告生成

## 📌 一句话总结
> `pytest-cov` 是 `pytest` 最核心的官方插件之一，用于统计测试覆盖率。它非常灵活，支持多种报告格式和输出，可以满足从本地开发到 CI/CD 集成的各种场景。

## 🎯 核心概念

### ⚙️ 核心配置：从测量到报告

`pytest-cov` 的配置主要通过命令行选项和配置文件两种方式进行。

#### 1. 命令行选项：最直接的控制方式

最基础的用法是 `--cov` 指定要测量的代码，`--cov-report` 指定报告格式。

**常用选项速查表：**

| 选项 | 说明 | 示例 |
| :--- | :--- | :--- |
| `--cov=SOURCE` | 指定要测量的源码路径或包名（可重复使用） | `--cov=src` 或 `--cov=mypackage` |
| `--cov` | 启用覆盖率测量，但不指定源码（将使用 `.coveragerc` 等配置文件中的设置） | `--cov` |
| `--cov-report=TYPE` | **指定报告格式**（可重复使用以生成多种报告） | `--cov-report=html` |
| `--cov-branch` | **启用分支覆盖率**（测量 if/else 等分支的覆盖情况） | `--cov-branch` |
| `--cov-fail-under=MIN` | 设定**覆盖率门禁**，低于设定百分比则测试失败 | `--cov-fail-under=90` |
| `--cov-append` | **追加**本次覆盖率数据到已有数据，而非覆盖 | `--cov-append` |
| `--cov-config=PATH` | 指定覆盖率配置文件路径 | `--cov-config=.coveragerc` |
| `--no-cov` | **禁用**覆盖率测量（调试时有用） | `--no-cov` |
| `--no-cov-on-fail` | 如果测试失败，**不生成**覆盖率报告 | `--no-cov-on-fail` |

> **注意**：当使用 `--cov=something` 指定了源码路径时，会覆盖配置文件中的 `source` 设置。

#### 2. 配置文件：精细控制的推荐方式

对于更精细的控制（如忽略特定文件、调整输出目录），推荐使用 `coverage.py` 的配置文件。`pytest-cov` 默认会读取 `.coveragerc` 文件，也支持 `pyproject.toml`、`setup.cfg` 或 `tox.ini`。

**`.coveragerc` 示例：**

```ini
[run]
# 指定要测量的源码目录
source = src
# 启用分支覆盖率
branch = True
# 忽略的目录或文件
omit =
    */tests/*
    */migrations/*
    */__pycache__/*

[report]
# 设置覆盖率门禁
fail_under = 90
# 设置覆盖率百分比精度
precision = 2
# 在报告中排除的文件
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:

[html]
# HTML 报告的输出目录
directory = htmlcov

[xml]
# XML 报告的输出文件
output = coverage.xml
```

### 📊 多模式报告生成

`pytest-cov` 真正的强大之处在于支持**在一次测试运行中生成多种格式的报告**。

#### 报告类型一览

| 报告格式 (`--cov-report`) | 说明 | 典型用途 | 默认输出位置 |
| :--- | :--- | :--- | :--- |
| `term` | 终端输出简洁的覆盖率表格 | 本地开发快速查看 | `stdout` |
| `term-missing` | 终端输出表格，并**列出未覆盖的行号** | **本地开发调试，快速定位未测试代码** | `stdout` |
| `term:skip-covered` | 终端输出时，**隐藏**100%覆盖的文件 | 精简终端输出，聚焦薄弱环节 | `stdout` |
| `html` | 生成带行号高亮的**交互式 HTML 报告** | **本地深度分析**，逐行查看覆盖情况 | `htmlcov/` 目录 |
| `xml` | 生成 Cobertura 兼容的 XML 报告 | **CI/CD 集成**（如 Jenkins, GitLab） | `coverage.xml` 文件 |
| `json` | 生成结构化的 JSON 报告 | 程序化处理或前端展示 | `coverage.json` 文件 |
| `lcov` | 生成 LCOV 格式报告 | 与 `genhtml` 等工具集成 | `coverage.lcov` 文件 |
| `annotate` | 为每个源文件生成带注释（`> ` 未覆盖，`! ` 已覆盖）的副本 | 简单的文本化分析 | 源文件同目录下生成 `.cover` 后缀文件 |
| `markdown` | 生成 Markdown 格式报告 | 在 GitHub 等平台的 PR 评论中展示 | 指定 `.md` 文件 |
| `markdown-append` | 以**追加**模式写入 Markdown 报告 | 在 CI 中合并多次运行的报告 | 指定 `.md` 文件 |

#### 实战示例：一次运行，多种报告

```bash
# 一次运行，同时生成 terminal, HTML, XML, JSON 和 Markdown 报告
pytest \
  --cov=src \
  --cov-branch \
  --cov-report=term-missing:skip-covered \
  --cov-report=html:reports/html \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=json:reports/coverage.json \
  --cov-report=markdown:reports/coverage.md \
  tests/
```

这条命令会：
*   **终端** (`term-missing:skip-covered`)：显示包含缺失行号、并隐藏100%覆盖文件的表格。
*   **HTML** (`html:reports/html`)：将详细的 HTML 报告输出到 `reports/html` 目录。
*   **XML** (`xml:reports/coverage.xml`)、**JSON** (`json:reports/coverage.json`)、**Markdown** (`markdown:reports/coverage.md`)：分别生成用于 CI/CD、程序化处理和 PR 评论的报告。

> **关键点**：一旦使用了任何 `--cov-report` 选项，默认的 `term` 报告就不会自动生成。

### 🔧 高级配置：与其他插件协同

#### 1. 与 `pytest-xdist` 并行测试

`pytest-cov` 与 `pytest-xdist` 协同良好，支持并行测试和跨环境覆盖率合并。

*   **`load` 模式**：测试任务被分发到多个 worker，最终汇总所有 worker 的覆盖率。
    ```bash
    pytest --cov=src -n auto tests/
    ```
*   **`each` 模式**：每个 worker 都运行全部测试，适用于在不同 Python 环境或平台上运行，并合并覆盖率。
    ```bash
    pytest --cov=src --dist each --tx popen//python=python3.8 --tx popen//python=python3.9 tests/
    ```

#### 2. 与 `tox` 多环境测试

在 `tox` 中，默认每个环境都会擦除之前的覆盖率数据。为了合并多个 `tox` 环境的覆盖率，需要：

1.  **每个环境追加数据**：在 `tox.ini` 的每个测试环境命令中添加 `--cov-append`。
2.  **单独生成报告**：创建一个专门的 `report` 环境，不运行测试，只用来合并并生成最终报告。

**`tox.ini` 简化示例：**
```ini
[testenv]
# 在 py3.8 和 py3.9 环境中，都追加覆盖率数据
commands =
    pytest --cov=src --cov-append {posargs}

[testenv:report]
# 这个环境不运行测试，只生成最终报告
skip_install = true
deps = pytest-cov
commands =
    pytest --cov=src --cov-report=html --cov-report=xml
```

### 💎 最佳实践总结

1.  **本地开发**：使用 `pytest --cov=src --cov-report=term-missing` 快速查看未覆盖行号。
2.  **CI/CD 门禁**：设置覆盖率门禁，如 `pytest --cov=src --cov-fail-under=80 --cov-report=xml`。当覆盖率不足时，测试失败，阻止合并。
3.  **深度分析**：在 CI 中生成 `html` 报告，作为构建产物存档，供团队详细查看。
4.  **配置优先**：对于复杂的忽略规则或输出路径，优先使用 `.coveragerc` 或 `pyproject.toml` 进行配置，保持命令行简洁。
5.  **分支覆盖**：使用 `--cov-branch` 或配置 `branch = True` 来获取更严格的分支覆盖率。

以上是 `pytest-cov` 配置与多模式报告生成的核心内容。你的测试项目主要是在本地开发使用，还是需要配置复杂的 CI/CD 流水线？如果有特定的集成需求（比如和 Jenkins 或 GitHub Actions 配合），可以告诉我，我帮你看看具体的配置方案。

## 🔗 关联笔记
- [[基于标记的条件执行与过滤筛选]]
- [[pytest命令行参数详解]]
- [[排除代码（exclude）与覆盖率阈值设定]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, coverage, plugins, skip, cli, reporting, exclusion, pipeline）
> - [+] 新增 H1「pytest-cov配置与多模式报告生成」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
