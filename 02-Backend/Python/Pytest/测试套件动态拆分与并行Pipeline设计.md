---
tags: [pytest, testing, python, fixture, plugins, scope, reporting, env, pipeline, parallel]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 测试套件动态拆分与并行Pipeline设计.md
---
# 测试套件动态拆分与并行Pipeline设计

## 📌 一句话总结
> 设计一套高效的并行Pipeline，核心在于解决一个关键问题：**如何将测试任务“动态且均衡”地拆分给多个CI执行者**。

这通常通过“**CI-level分片**”与“**Test-level并发**”相结合的分层策略来实现。

## 🎯 核心概念

### 🧩 核心策略：分层并行

1.  **CI-level 分片 (Sharding)**：在CI平台上，将整个测试套件切分成多个逻辑子集（分片），分发到**不同的CI Job**（如不同的Runner、容器）中并行执行。
2.  **Test-level 并发 (Concurrency)**：在每个CI Job内部，利用`pytest-xdist`等工具，将分配到该Job的测试子集，进一步分发到**多个Worker进程**中并发执行。

这种组合策略能最大化利用并行资源，显著缩短流水线总耗时。

### 🛠️ 核心工具对比与选型

选择合适的工具是实现动态拆分的基石。以下是主流的几种方案对比：

| 工具 | 核心机制 | 优势 | 适用场景 | 关键命令/配置 |
| :--- | :--- | :--- | :--- | :--- |
| **pytest-split** | **基于历史执行时间**的智能分片。需先运行`--store-durations`生成`.test_durations`文件。 | 分片**高度均衡**，能有效避免因个别慢测试导致的Job拖尾。 | 测试用例执行时间差异较大的大型项目。 | `pytest --splits 3 --group 1` |
| **pytest-shard** | 提供 `roundrobin`, `hash`, `duration` 等多种分片模式。 | 灵活性高；`hash`模式可保证测试分配的**确定性**。 | 对分片策略有特定要求（如确定性）的场景。 | `pytest --shard-id=0 --num-shards=3` |
| **pytest-cdist** | 按**测试项（Item）** 粒度进行分组。支持`file`和`scope`两种`justify-items`模式。 | 能将同一文件或作用域内的测试**聚合**到同一个分片。 | 测试间存在较强的**状态依赖**（如共享昂贵的session级fixture）。 | `pytest --cdist-group=1/4` |
| **pytest-xdist** | **进程级并发**，在单个Job内将测试分发给多个Worker。 | **配置简单**，加速效果明显。 | 所有场景的基础并发层，常与其他分片工具**组合使用**。 | `pytest -n auto` |

**选型建议**：
*   **追求最优的负载均衡**：首选 `pytest-split`。
*   **对分片确定性有要求**：`pytest-shard` 的 `hash` 模式是理想选择。
*   **需要聚合有状态依赖的测试**：`pytest-cdist` 能确保它们被分配到同一分片。

### 📋 CI平台集成实战

以下是在主流CI平台上配置分片Pipeline的模板。

#### GitHub Actions (with `pytest-split`)

利用 `matrix` 策略定义并行Job，每个Job运行一个分片。

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  # 1. 用于存储测试时长的Job（可定期运行）
  store-durations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pytest pytest-split
      - name: Store test durations
        run: pytest --store-durations
      - name: Upload .test_durations
        uses: actions/upload-artifact@v4
        with:
          name: test-durations
          path: .test_durations

  # 2. 主要的测试分片Job
  test:
    needs: store-durations  # 等待时长文件准备好
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3]  # 定义3个分片

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pytest pytest-split pytest-xdist
      - name: Download test durations
        uses: actions/download-artifact@v4
        with:
          name: test-durations
      - name: Run tests (shard ${{ matrix.shard }})
        run: |
          pytest --splits 3 --group ${{ matrix.shard }} \
                 --splitting-algorithm least_duration \
                 -n auto  # 在每个分片内部启用并发
```

#### GitLab CI (with `pytest-gitlabci-parallelized`)

利用 `parallel` 关键字定义并行Job数量，插件会自动读取 `CI_NODE_INDEX` 和 `CI_NODE_TOTAL` 环境变量。

```yaml
# .gitlab-ci.yml
image: python:3.11

before_script:
  - pip install pytest pytest-gitlabci-parallelized pytest-xdist

stages:
  - test

test:
  stage: test
  parallel: 3  # 启动3个并行Job
  script:
    # 插件会根据CI_NODE_INDEX和CI_NODE_TOTAL自动分片
    - pytest -n auto  # 在每个分片内部启用并发
```

#### Jenkins (Pipeline)

通过 `parallel` 步骤动态生成并行任务。

```groovy
// Jenkinsfile
pipeline {
    agent any
    environment {
        TOTAL_SHARDS = '3'
    }
    stages {
        stage('Parallel Test Execution') {
            steps {
                script {
                    // 定义并行任务
                    def parallelStages = [:]
                    // 循环创建分片
                    for (int i = 1; i <= TOTAL_SHARDS.toInteger(); i++) {
                        def shardIndex = i
                        parallelStages["Shard-${shardIndex}"] = {
                            node('your-agent-label') {
                                checkout scm
                                sh """
                                    # 使用 pytest-shard 进行分片
                                    pytest --shard-id=${shardIndex-1} --num-shards=${TOTAL_SHARDS} -n auto
                                """
                            }
                        }
                    }
                    parallel parallelStages
                }
            }
        }
    }
}
```

### ⚙️ 高级设计模式

*   **两级调度**：在CI层面使用`pytest-split`或`pytest-shard`进行粗粒度分片，在每个分片内部再使用`pytest-xdist`进行细粒度并发，这是大型项目最有效的组合。
*   **时长数据存储与更新**：使用`pytest-split`时，需将生成的`.test_durations`文件作为构建产物存储。建议定期（如每周）运行`--store-durations`更新该文件，以反映测试用例耗时的变化。
*   **智能分组**：对有状态依赖的测试，使用`pytest-cdist`的`--cdist-justify-items=scope`，或`pytest-xdist`的`--dist loadscope`等选项，将相关测试聚合，减少资源竞争。

### ⚠️ 注意事项与常见陷阱

1.  **Fixture隔离**：并行执行时，需确保`session`级别的Fixture是线程/进程安全的，或使用`tmp_path`等机制进行隔离。
2.  **测试顺序依赖**：`pytest-split`的`duration_based_chunks`算法与随机化测试顺序的插件（如`pytest-randomly`）不兼容。如需随机化，应使用`pytest-shard`的`hash`模式以保证确定性。
3.  **报告合并**：分片执行后，需将各分片生成的JUnit XML等报告进行合并，以便获得统一的测试结果视图。可使用如`junitparser`等工具，或在CI平台配置报告聚合功能。
4.  **资源竞争**：多个分片同时运行时，应避免对同一资源（如数据库、文件系统）的争用，可通过为每个分片分配独立资源或使用锁机制来解决。

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[内置作用域层级]]
- [[分布式执行与测试分片（Sharding）策略]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, plugins, scope, reporting, env, pipeline, parallel）
> - [+] 新增 H1「测试套件动态拆分与并行Pipeline设计」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
