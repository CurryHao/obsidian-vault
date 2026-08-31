---
tags: [pytest, testing, python, coverage, markers, cli, reporting, warnings, exclusion, threshold]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 排除代码（exclude）与覆盖率阈值设定.md
---
# 排除代码（exclude）与覆盖率阈值设定

## 📌 一句话总结
> 这是`pytest-cov`在落地企业级质量门禁时的核心配置项。**排除（Exclude）决定“测什么”，阈值（Threshold）决定“必须测到多少”**。两者配合，才能生成可信且可执行的覆盖率报告。

我将从**排除策略（静态过滤 vs 动态标记）**、**阈值设定与CI门禁**、**阈值衰减策略（防止一次性强制导致的抵触）**以及**常见陷阱**四个维度展开。

## 🎯 核心概念

### 1. 排除代码：让报告聚焦于“真正需要测试的代码”

覆盖率报告的价值在于**揭露风险**，而非惩罚框架代码或迁移脚本。排除策略分为**静态配置（基于文件/行号）**和**动态标记（基于代码注释）**两种。

#### 策略一：`.coveragerc` / `pyproject.toml` 静态排除（推荐）

在配置文件中通过`omit`和`exclude_lines`精准剔除无需测量的部分。

```toml
# pyproject.toml (推荐)
[tool.coverage.run]
# 1. 排除整个目录或文件（omit）
omit = [
    "*/tests/*",               # 排除测试文件自身
    "*/migrations/*",          # Django/ORM迁移脚本
    "*/__pycache__/*",         # 缓存
    "*/setup.py",              # 安装脚本
    "src/legacy/deprecated.py",# 废弃模块（计划删除）
]

# 2. 排除特定代码行（不计算在覆盖率内）
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",        # 手动标记
    "if __name__ == .__main__.:", # 命令行入口
    "raise NotImplementedError", # 占位符
    "if TYPE_CHECKING:",        # 类型检查（运行时无影响）
    "@abstractmethod",          # 抽象方法（由子类实现）
]
```

**`pragma: no cover` 的精准用法**：
在代码中显式标记不需要测试的行，适合“防御性代码”或“极难触发的错误分支”。

```python
def safe_divide(a, b):
    if b == 0:
        return None  # pragma: no cover  # 明确标记不可达或无需测试
    return a / b
```

> **关键原则**：`pragma: no cover` 应视为“特殊情况”，而非逃避测试的捷径。在Code Review中应审查其必要性。

#### 策略二：`pytest-cov` 命令行临时排除

适合在调试或特定场景下快速调整，不修改配置文件。

```bash
# 忽略整个目录
pytest --cov=src --cov-omit="src/legacy/*"

# 忽略多个路径
pytest --cov=src --cov-omit="src/migrations/*,src/deprecated/*"
```

### 2. 覆盖率阈值设定：CI门禁的核心指标

阈值是质量门禁的数值化体现。`pytest-cov` 支持**总体阈值**和**单文件阈值**，并可在CI中强制阻断合并。

#### 基础用法：全局阈值（`--cov-fail-under`）

```bash
# 总体覆盖率低于 85% 则测试失败（CI阻断）
pytest --cov=src --cov-fail-under=85
```

#### 进阶用法：`.coveragerc` 中设定细粒度阈值

```toml
# pyproject.toml
[tool.coverage.report]
# 全局门禁
fail_under = 85

# 按文件/模块设定不同阈值（覆盖全局）
[tool.coverage.report.optional_headers]
"src/core/*" = 95   # 核心模块要求更高
"src/ui/*" = 70     # UI层可适当放宽
```

#### 组合策略：`--cov-fail-under` + `--cov-report=term-missing`

在CI中，既要有门禁，又要提供可操作的缺失行列表，帮助开发者快速定位未覆盖代码。

```bash
# 设置80%门禁，并显示缺失行号（便于修复）
pytest --cov=src --cov-fail-under=80 --cov-report=term-missing
```

### 3. 阈值衰减策略（给遗留项目的缓刑期）

对于缺乏测试的遗留项目，**一次性要求90%覆盖率**会直接导致CI全线飘红，团队必然抵触。应使用**“渐进式提升”**策略。

#### 策略：利用 `fail_under` 的分阶段推进

| 阶段 | 目标阈值 | 时间窗口 | 执行策略 |
| :--- | :--- | :--- | :--- |
| **阶段1（探索期）** | 50% | 1个月 | 仅作为警告（不阻断），先建立基线 |
| **阶段2（提升期）** | 65% | 第2个月 | 设为门禁（阻断），但允许特定模块`# pragma: no cover`临时豁免 |
| **阶段3（巩固期）** | 80% | 第3个月 | 强制门禁，取消大部分豁免，仅保留`if __name__ == "__main__"`等标准排除 |
| **阶段4（卓越期）** | 90% | 半年后 | 逐步推进至行业标杆水平 |

**配置示例（阶段2）**：
```toml
[tool.coverage.report]
fail_under = 65
# 允许一定数量的未覆盖行（不计入门禁）
exclude_lines = [
    "if __name__ == .__main__.:",
    "pragma: no cover",
]
```

### 4. 极易踩中的 3 个致命陷阱

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **覆盖率显示为 0%，即使有测试** | `--cov` 指向的路径与源码导入路径不一致（如 `--cov=src` 但导入为 `mypkg`） | 检查导入路径：在测试中 `print(mypkg.__file__)` 确认真实路径，或使用 `--cov=mypkg` 按包名测量 |
| **`omit` 误排除了核心代码** | 写成了 `omit = ["*/tests/*"]`，但测试代码在 `src/tests/` 下，导致 `src/` 也被排除 | 优先使用 **`source`** 指定要测量的目录，`omit` 只排除明确不需要的部分 |
| **`.coveragerc` 中的 `exclude_lines` 正则写错，导致预期行未排除** | 例如 `exclude_lines = ["if TYPE_CHECKING:"]` 需要严格匹配空格；`if TYPE_CHECKING:` 与 `if TYPE_CHECKING:` 在源码中可能因格式化（如 `if TYPE_CHECKING:  # noqa`）而不匹配 | 使用更宽松的正则：`exclude_lines = ["if\\s+TYPE_CHECKING:"]`，并添加 `[report]` 下的 `ignore_errors = True` 来忽略配置错误 |

### 5. 诊断与验证命令

在设定阈值之前，先全面了解当前项目覆盖率状况，避免盲目设定。

```bash
# 1. 查看详细的单文件覆盖率（含未覆盖行号）
pytest --cov=src --cov-report=term-missing

# 2. 生成HTML报告，点击查看每个文件的详细覆盖情况
pytest --cov=src --cov-report=html
# 然后在浏览器中打开 htmlcov/index.html

# 3. 检查当前覆盖率是否满足门禁（不生成完整报告，快速反馈）
pytest --cov=src --cov-fail-under=70 --cov-report=term
```

### 6. 终极实践模板

假设我们有一个 Django 项目，目录结构如下：
```python
myproject/
├── manage.py
├── myapp/
│   ├── models.py
│   ├── views.py
│   └── admin.py
├── tests/
└── scripts/  # 运维脚本，无需测试
```

**`pyproject.toml` 完整配置（可直接复制）**：
```toml
[tool.coverage.run]
source = ["myapp"]  # 只测量 myapp 包
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__pycache__/*",
    "*/admin.py",      # Django Admin 通常无需测试
]

[tool.coverage.report]
fail_under = 85
precision = 2
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]

[tool.pytest.ini_options]
addopts = [
    "--cov=myapp",
    "--cov-report=term-missing",
    "--cov-report=html:reports/html",
    "--cov-report=xml:reports/coverage.xml",
]
```

**CI 命令（GitHub Actions 示例）**：
```yaml
- name: Run tests with coverage
  run: |
    pytest --cov-fail-under=85
```

你现在是想**为遗留项目设定一个合理的初始阈值**，还是想**配置 `.coveragerc` 以排除大量第三方代码**？告诉我你的项目结构（包名、迁移目录、配置目录），我可以给你一份直接可用的 `pyproject.toml` 配置模板，并说明每个排除项的理由。你选哪个场景？

## 🔗 关联笔记
- [[内置标记]]
- [[pytest命令行参数详解]]
- [[pytest-cov配置与多模式报告生成]]
- [[警告捕获与断言pytest.warns]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, coverage, markers, cli, reporting, warnings, exclusion, threshold）
> - [+] 新增 H1「排除代码（exclude）与覆盖率阈值设定」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
