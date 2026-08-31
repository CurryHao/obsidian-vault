---
tags: [pytest, testing, python, coverage, plugins, xfail, reporting, env, incremental, pipeline]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: 主流CI平台配置模板.md
---
# 主流CI平台配置模板

## 📌 一句话总结
> 将 PyTest 集成到 CI/CD 流水线是自动化质量保障的最终一环。以下提供 **GitHub Actions**、**GitLab CI** 和 **Jenkins** 三大主流平台的配置模板，涵盖测试执行、覆盖率收集、并行分片和结果报告等关键实践。

## 🎯 核心概念

### 1. GitHub Actions（最常用）

以下是一个完整的工作流，支持分片并行、覆盖率门禁和报告上传。

```yaml
# .github/workflows/pytest.yml
name: PyTest CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        # 分片：将测试分成 3 个并行组
        shard: [1, 2, 3]

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 供 diff-cover 使用

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[test]  # 安装项目及测试依赖（pytest, pytest-cov, pytest-xdist等）

      - name: Run tests with coverage (shard ${{ matrix.shard }})
        env:
          PYTEST_ADDOPTS: "-v --tb=short"
        run: |
          # 使用 pytest-split 或自定义分片脚本，此处用 --shard 参数（需安装 pytest-shard）
          pytest --cov=src --cov-report=xml --cov-report=html \
                 --shard=${{ matrix.shard }}/${{ strategy.job-total }} \
                 tests/

      - name: Upload coverage reports (HTML) as artifact
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report-${{ matrix.shard }}
          path: htmlcov/

      - name: Upload XML coverage for merging (if needed)
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml-${{ matrix.shard }}
          path: coverage.xml

  # 可选：合并覆盖率报告并检查总体门禁
  coverage-check:
    needs: test
    runs-on: ubuntu-latest
    if: always()
    steps:
      - uses: actions/checkout@v4
      - name: Download all coverage XML files
        uses: actions/download-artifact@v4
        with:
          path: coverage-artifacts
      - name: Merge coverage and check threshold
        run: |
          pip install coverage diff-cover
          coverage combine coverage-artifacts/**/coverage.xml
          coverage report --fail-under=80
          # 检查增量覆盖率（针对PR）
          if [ "${{ github.event_name }}" == "pull_request" ]; then
            diff-cover coverage.xml --compare-branch=origin/${{ github.base_ref }} --fail-under=90
          fi
```

**要点**：
- 使用分片（`--shard`）加速大型套件。
- 覆盖率文件作为 artifacts 保存，便于下载查看。
- 合并覆盖率（`coverage combine`）实现整体门禁。
- 在 PR 中启用增量覆盖率检查。

### 2. GitLab CI（`.gitlab-ci.yml`）

GitLab CI 内置了 coverage 解析功能，可自动在 MR 中显示覆盖率变化。

```yaml
# .gitlab-ci.yml
image: python:3.11

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  COVERAGE_REPORT: "coverage.xml"

cache:
  paths:
    - .cache/pip
    - .pytest_cache/

stages:
  - test
  - coverage

before_script:
  - python -m pip install --upgrade pip
  - pip install -e .[test]

# 使用并行测试矩阵（GitLab CI 13.3+）
.test:
  stage: test
  script:
    - pytest --cov=src --cov-report=xml --cov-report=html --shard=$CI_NODE_INDEX/$CI_NODE_TOTAL tests/
  coverage: '/^TOTAL.*\s+(\d+%)$/'
  artifacts:
    paths:
      - htmlcov/
      - coverage.xml
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    expire_in: 7 days

test:shard1:
  extends: .test
  parallel: 3  # 自动分片为3个并行job

# 合并覆盖率报告（可选）
coverage-merge:
  stage: coverage
  needs: ["test:shard1", "test:shard2", "test:shard3"]
  script:
    - pip install coverage
    - coverage combine coverage-*/coverage.xml
    - coverage report --fail-under=80
  coverage: '/^TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: combined-coverage.xml
```

**要点**：
- 使用 `parallel: 3` 自动分片，`CI_NODE_INDEX` 和 `CI_NODE_TOTAL` 环境变量可用。
- 内置 coverage 报告集成，MR 中会显示覆盖率变化。
- 使用 `needs` 显式指定依赖，减少等待时间。

### 3. Jenkins（Declarative Pipeline）

Jenkins 是传统的 CI 工具，通常与 `pytest` + `coverage` + `HTML Publisher` 插件集成。

```groovy
// Jenkinsfile (Declarative Pipeline)
pipeline {
    agent any

    environment {
        PYTHONPATH = "${env.WORKSPACE}"
        PYTEST_ADDOPTS = "-v --tb=short"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup') {
            steps {
                sh '''
                    python -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -e .[test]
                '''
            }
        }

        stage('Test') {
            parallel {
                stage('Shard 1') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            pytest --cov=src --cov-report=xml --cov-report=html \
                                   --shard=1/3 tests/
                        '''
                    }
                    post {
                        always {
                            // 存档 XML 报告供后续合并
                            stash name: 'coverage-shard1', includes: 'coverage.xml,htmlcov/'
                        }
                    }
                }
                stage('Shard 2') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            pytest --cov=src --cov-report=xml --cov-report=html \
                                   --shard=2/3 tests/
                        '''
                    }
                    post {
                        always {
                            stash name: 'coverage-shard2', includes: 'coverage.xml,htmlcov/'
                        }
                    }
                }
                stage('Shard 3') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            pytest --cov=src --cov-report=xml --cov-report=html \
                                   --shard=3/3 tests/
                        '''
                    }
                    post {
                        always {
                            stash name: 'coverage-shard3', includes: 'coverage.xml,htmlcov/'
                        }
                    }
                }
            }
        }

        stage('Merge Coverage & Check') {
            steps {
                sh '''
                    . venv/bin/activate
                    # 从 stash 中取回所有覆盖率文件
                    coverage combine coverage-shard*/coverage.xml
                    coverage report --fail-under=80
                    # 生成合并的 HTML 报告
                    coverage html -d merged_htmlcov
                '''
            }
            post {
                always {
                    // 发布 HTML 报告到 Jenkins
                    publishHTML (target: [
                        reportDir: 'merged_htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }
    }

    post {
        failure {
            // 可选：发送通知等
            echo 'Tests failed!'
        }
    }
}
```

**要点**：
- 使用 `parallel` 块并行执行分片。
- 使用 `stash` / `unstash` 传递产物。
- 利用 `publishHTML` 插件展示覆盖率报告。
- 结合 `coverage combine` 合并数据。

### 4. 通用最佳实践

| 实践 | 说明 |
| :--- | :--- |
| **缓存依赖** | 缓存 `pip` 和 `pytest` 缓存目录，加速重复构建。 |
| **并行分片** | 按测试数量或历史耗时动态分片，使用 `pytest-shard` 或 `pytest-xdist` 的 `--dist`。 |
| **覆盖率门禁** | 设置全局 `fail_under` 和增量门禁，防止质量下滑。 |
| **报告归档** | 将 HTML 报告作为构建产物，便于团队查看。 |
| **失败快速反馈** | 使用 `--maxfail=2` 或 `-x` 及早停止，节省 CI 资源。 |
| **环境隔离** | 确保 CI 使用与本地一致的 Python 版本和依赖（锁文件）。 |

你现在使用哪种 CI 平台？如果已有配置文件，我可以帮你优化；如果从零开始，可以直接复制上述模板，并根据项目结构调整 `--cov` 路径和分片数量。

## 🔗 关联笔记
- [[基于标记的条件执行与过滤筛选]]
- [[pytest-cov配置与多模式报告生成]]
- [[分布式执行与测试分片（Sharding）策略]]
- [[增量覆盖率与质量门禁（Quality Gate）策略]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, coverage, plugins, xfail, reporting, env, incremental, pipeline）
> - [+] 新增 H1「主流CI平台配置模板」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
