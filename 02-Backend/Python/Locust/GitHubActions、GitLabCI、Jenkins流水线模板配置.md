---
tags: [locust, CI/CD, 流水线]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: GitHubActions、GitLabCI、Jenkins流水线模板配置.md
---
# GitHubActions、GitLabCI、Jenkins流水线模板配置

## Locust 性能测试 CI/CD 流水线模板配置

将 Locust 压测集成到 CI/CD 流水线中，可以实现 **“代码提交 → 自动构建 → 自动部署 → 自动压测 → 质量门禁”** 的全自动化闭环。下面分别给出 GitHub Actions、GitLab CI 和 Jenkins 的完整流水线模板，涵盖单机快速验证和分布式集群压测两种场景。

---

### 一、通用设计原则

| 原则 | 说明 |
|------|------|
| **参数化** | 将目标主机、并发数、运行时长、SLA 阈值等作为流水线参数，便于不同环境复用 |
| **结果持久化** | 将 CSV/HTML 报告作为流水线制品（Artifacts）保存，便于事后分析 |
| **质量门禁** | 基于失败率、P95 响应时间等指标判定构建是否通过 |
| **环境隔离** | 压测环境与生产环境严格隔离，避免影响线上业务 |
| **清理机制** | 无论成功或失败，确保释放资源（如 Kubernetes Pods、Docker 容器） |

---

### 二、GitHub Actions 流水线模板

#### 2.1 单机模式（快速验证）

```yaml
# .github/workflows/locust-single.yml
name: Locust Performance Test (Single)

on:
  workflow_dispatch:                     # 手动触发
  push:
    branches: [ main, develop ]
    paths:
      - 'locustfile.py'
      - 'requirements.txt'

env:
  TARGET_HOST: https://staging-api.example.com
  USERS: 100
  SPAWN_RATE: 10
  RUN_TIME: 2m
  MAX_FAILURE_RATE: 1.0                  # 失败率阈值 (%)
  MAX_P95_MS: 500                        # P95 响应时间阈值 (ms)

jobs:
  performance-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt  # 包含 locust

      - name: Run Locust (headless)
        run: |
          mkdir -p reports
          locust -f locustfile.py \
            --headless \
            --host ${{ env.TARGET_HOST }} \
            -u ${{ env.USERS }} \
            -r ${{ env.SPAWN_RATE }} \
            -t ${{ env.RUN_TIME }} \
            --csv=reports/report \
            --html=reports/report.html \
            --loglevel WARNING

      - name: Validate SLA
        run: |
          python scripts/validate_sla.py \
            --csv-prefix reports/report \
            --max-failure-rate ${{ env.MAX_FAILURE_RATE }} \
            --max-p95 ${{ env.MAX_P95_MS }}

      - name: Upload test reports
        uses: actions/upload-artifact@v4
        if: always()                       # 无论测试是否通过都上传
        with:
          name: locust-reports
          path: reports/
```
```code## 2.2 分布式模式（Kubernetes + KEDA 自动伸缩）

```yaml
# .github/workflows/locust-distributed.yml
name: Locust Distributed Test (K8s)

on:
  workflow_dispatch:
    inputs:
      users:
        description: 'Total users'
        required: true
        default: 1000
      run_time:
        description: 'Run time (e.g. 10m)'
        required: true
        default: '10m'
      target_host:
        description: 'Target host'
        required: true
        default: 'https://prod-api.example.com'

jobs:
  distributed-load-test:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: 'latest'

      - name: Set up Kubeconfig
        run: |
          mkdir -p $HOME/.kube
          echo "${{ secrets.KUBECONFIG }}" | base64 -d > $HOME/.kube/config

      - name: Install Helm (if not present)
        uses: azure/setup-helm@v4
        with:
          version: 'v3.14.0'

      - name: Deploy Locust cluster with Helm
        run: |
          helm upgrade --install locust ./helm/locust \
            --namespace locust --create-namespace \
            --set master.resources.requests.cpu=500m \
            --set worker.replicas=0 \
            --set worker.resources.requests.cpu=1000m \
            --set worker.resources.requests.memory=2Gi \
            --set locustfile.configmap=locust-scripts \
            --set env.TARGET_HOST=${{ github.event.inputs.target_host || env.TARGET_HOST }} \
            --wait

      - name: Scale workers to target
        run: |
          kubectl scale deployment locust-worker -n locust --replicas=${{ github.event.inputs.users && (github.event.inputs.users / 200) | int || 5 }}

      - name: Wait for workers ready
        run: |
          kubectl wait --for=condition=available deployment/locust-worker -n locust --timeout=120s

      - name: Start load test via API
        run: |
          # 通过 Master API 启动测试（需使用 locust-swarm 或直接调用）
          pip install locust-swarm
          locust-swarm --master-host locust-master.locust.svc.cluster.local \
            --users ${{ github.event.inputs.users || 1000 }} \
            --spawn-rate 100 \
            --run-time ${{ github.event.inputs.run_time || '10m' }} \
            --host ${{ github.event.inputs.target_host || env.TARGET_HOST }}

      - name: Wait for test completion and collect results
        run: |
          # 轮询 Master API 等待测试结束
          while true; do
            state=$(curl -s http://localhost:8089/stats/state | jq -r .state)
            if [ "$state" = "stopped" ]; then
              break
            fi
            sleep 5
          done
          # 下载报告
          curl -o reports/report.html http://localhost:8089/stats/report
          # 导出 CSV（需通过 API 或直接访问 Master Pod 的 /stats/requests）
          kubectl exec deployment/locust-master -n locust -- cat /home/locust/worker_stats.csv > reports/report_stats.csv 2>/dev/null || true

      - name: Validate SLA
        run: |
          python scripts/validate_sla.py --csv-prefix reports/report --max-failure-rate 1.0 --max-p95 500

      - name: Upload reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: locust-distributed-reports
          path: reports/

      - name: Cleanup
        if: always()
        run: |
          helm uninstall locust -n locust
          kubectl delete namespace locust
```

> **说明**：上述示例中使用了 `locust-swarm` 工具来触发分布式测试，也可以直接通过 Master Web API (`/swarm` 和 `/stop`) 实现。

---

### 三、GitLab CI 流水线模板

#### 3.1 单机模式

```yaml
# .gitlab-ci.yml
image: python:3.11-slim

variables:
  TARGET_HOST: "https://staging-api.example.com"
  USERS: 50
  SPAWN_RATE: 5
  RUN_TIME: "1m"
  MAX_FAILURE_RATE: "1.0"
  MAX_P95_MS: "500"

stages:
  - test
  - report

cache:
  paths:
    - .cache/pip

before_script:
  - pip install --upgrade pip
  - pip install -r requirements.txt

.locust_base: &locust_base
  stage: test
  script:
    - mkdir -p reports
    - locust -f locustfile.py --headless --host $TARGET_HOST -u $USERS -r $SPAWN_RATE -t $RUN_TIME --csv=reports/report --html=reports/report.html --loglevel WARNING
    - python scripts/validate_sla.py --csv-prefix reports/report --max-failure-rate $MAX_FAILURE_RATE --max-p95 $MAX_P95_MS
  artifacts:
    when: always
    paths:
      - reports/
    expire_in: 7 days

single-test:
  extends: .locust_base
  only:
    - merge_requests
    - main

# 分布式测试（Kubernetes）
distributed-test:
  stage: test
  image: bitnami/kubectl:latest
  only:
    - schedules                     # 定时触发
  variables:
    KUBECONFIG: /tmp/config
  before_script:
    - echo "$KUBE_CONFIG" | base64 -d > $KUBECONFIG
  script:
    - helm upgrade --install locust ./helm/locust -n locust --create-namespace --set worker.replicas=0 --wait
    - kubectl scale deployment locust-worker -n locust --replicas=5
    - kubectl wait --for=condition=available deployment/locust-worker -n locust --timeout=120s
    - |
      # 通过 port-forward 访问 Master API
      kubectl port-forward service/locust-master -n locust 8089:8089 &
      sleep 5
      curl -X POST http://localhost:8089/swarm -H "Content-Type: application/json" -d '{"user_count": 1000, "spawn_rate": 100, "host": "'"$TARGET_HOST"'"}'
      sleep $RUN_TIME
      curl -X POST http://localhost:8089/stop
      curl -o reports/report.html http://localhost:8089/stats/report
      kill %1
    - python scripts/validate_sla.py --csv-prefix reports/report --max-failure-rate 1.0 --max-p95 500
  artifacts:
    when: always
    paths:
      - reports/
  after_script:
    - helm uninstall locust -n locust || true
    - kubectl delete namespace locust || true
```

#### 3.2 使用 GitLab CI 的 Schedule 定时压测

在项目 CI/CD → Schedules 中创建定时任务，触发 `distributed-test` 作业，实现每日凌晨自动执行压测。

---

### 四、Jenkins 流水线模板（Declarative Pipeline）

#### 4.1 单机模式

```groovy
// Jenkinsfile
pipeline {
    agent any

    environment {
        TARGET_HOST = 'https://staging-api.example.com'
        USERS = '100'
        SPAWN_RATE = '10'
        RUN_TIME = '2m'
        MAX_FAILURE_RATE = '1.0'
        MAX_P95_MS = '500'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run Locust') {
            steps {
                sh '''
                    . venv/bin/activate
                    mkdir -p reports
                    locust -f locustfile.py \
                      --headless \
                      --host ${TARGET_HOST} \
                      -u ${USERS} \
                      -r ${SPAWN_RATE} \
                      -t ${RUN_TIME} \
                      --csv=reports/report \
                      --html=reports/report.html \
                      --loglevel WARNING
                '''
            }
        }

        stage('Validate SLA') {
            steps {
                sh '''
                    . venv/bin/activate
                    python scripts/validate_sla.py \
                      --csv-prefix reports/report \
                      --max-failure-rate ${MAX_FAILURE_RATE} \
                      --max-p95 ${MAX_P95_MS}
                '''
            }
        }

        stage('Archive Reports') {
            steps {
                archiveArtifacts artifacts: 'reports/**', fingerprint: true
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
```

#### 4.2 分布式模式（Kubernetes + KEDA）

```groovy
pipeline {
    agent any

    parameters {
        string(name: 'TARGET_HOST', defaultValue: 'https://prod-api.example.com', description: 'Target host')
        string(name: 'USERS', defaultValue: '1000', description: 'Total users')
        string(name: 'RUN_TIME', defaultValue: '10m', description: 'Run time')
        choice(name: 'KEDA_ENABLED', choices: ['true', 'false'], description: 'Enable KEDA autoscaling')
    }

    environment {
        KUBECONFIG = credentials('kubeconfig-file')   // Jenkins credential
    }

    stages {
        stage('Deploy Locust Cluster') {
            steps {
                script {
                    sh """
                        helm upgrade --install locust ./helm/locust \
                          -n locust --create-namespace \
                          --set worker.replicas=0 \
                          --set env.TARGET_HOST=${params.TARGET_HOST} \
                          --wait
                    """
                    if (params.KEDA_ENABLED == 'true') {
                        sh "kubectl apply -f keda-scaledobject.yaml -n locust"
                    } else {
                        def workers = (params.USERS as int) / 200
                        sh "kubectl scale deployment locust-worker -n locust --replicas=${workers.intValue()}"
                    }
                    sh "kubectl wait --for=condition=available deployment/locust-worker -n locust --timeout=120s"
                }
            }
        }

        stage('Start Test') {
            steps {
                script {
                    // 使用 port-forward 或直接通过 Ingress 访问 Master API
                    sh """
                        kubectl port-forward service/locust-master -n locust 8089:8089 &
                        sleep 5
                        curl -X POST http://localhost:8089/swarm \
                          -H "Content-Type: application/json" \
                          -d '{"user_count": ${params.USERS}, "spawn_rate": 100, "host": "${params.TARGET_HOST}"}'
                        sleep ${params.RUN_TIME}
                        curl -X POST http://localhost:8089/stop
                        mkdir -p reports
                        curl -o reports/report.html http://localhost:8089/stats/report
                        kill %1
                    """
                }
            }
        }

        stage('Validate and Collect') {
            steps {
                sh '''
                    # 从 Master Pod 复制 CSV 统计（需配置共享存储）
                    kubectl exec deployment/locust-master -n locust -- cat /home/locust/stats.csv > reports/report_stats.csv || true
                    python scripts/validate_sla.py --csv-prefix reports/report --max-failure-rate 1.0 --max-p95 500
                '''
            }
        }
    }

    post {
        always {
            sh 'helm uninstall locust -n locust || true'
            sh 'kubectl delete namespace locust || true'
            archiveArtifacts artifacts: 'reports/**'
        }
    }
}
```

---

### 五、SLA 验证脚本 (`scripts/validate_sla.py`)

```python
import pandas as pd
import sys
import argparse

def validate_sla(csv_prefix, max_failure_rate, max_p95):
    stats = pd.read_csv(f"{csv_prefix}_stats.csv")
    total = stats[stats['Name'] == 'Aggregated'].iloc[0]
    failure_rate = total['Fails'] / total['Requests'] * 100
    p95 = total['95%ile']

    exit_code = 0
    if failure_rate > max_failure_rate:
        print(f"❌ Failure rate {failure_rate:.2f}% > {max_failure_rate}%")
        exit_code = 1
    if p95 > max_p95:
        print(f"❌ P95 {p95:.0f}ms > {max_p95}ms")
        exit_code = 1

    if exit_code == 0:
        print(f"✅ SLA passed: Failure={failure_rate:.2f}%, P95={p95:.0f}ms")
    sys.exit(exit_code)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-prefix", required=True)
    parser.add_argument("--max-failure-rate", type=float, default=1.0)
    parser.add_argument("--max-p95", type=int, default=500)
    args = parser.parse_args()
    validate_sla(args.csv_prefix, args.max_failure_rate, args.max_p95)
```

---

### 六、最佳实践总结

| 实践 | 说明 |
|------|------|
| **统一脚本仓库** | 将 `locustfile.py`、`requirements.txt`、Helm Chart 等放在同一个代码仓库，保持版本一致 |
| **敏感信息管理** | 目标主机认证信息（如 API Key）通过 CI/CD 的 Secret 变量注入，避免硬编码 |
| **测试数据隔离** | 使用独立测试环境或专属租户，防止压测数据污染生产 |
| **结果对比基线与回归** | 将每次压测的关键指标存入 InfluxDB，通过 Grafana 展示历史趋势 |
| **渐进式伸缩** | 分布式模式启动时先保证 Worker 全部就绪，再开始测试；结束时先停止测试再释放资源 |
| **日志采样** | 高并发时降低日志级别（`--loglevel WARNING`），避免日志 I/O 成为性能瓶颈 |
| **Pipeline 状态** | 通过 SLA 验证脚本的退出码决定 Pipeline 成败，实现质量门禁 |
| **清理保障** | 使用 `post` / `always` / `if: always()` 确保资源回收，避免产生残留 Pods 产生费用 |

通过上述模板，你可以快速将 Locust 性能测试纳入 CI/CD 体系，实现 **“代码提交即压测”** 的自动化流程，为系统稳定性提供持续保障。

## 🔗 关联笔记

[[_MOC-locust]] | [[docker-compose编排Master-Worker分布式集群]] | [[InfluxDB持久化存储与历史趋势对比]] | [[Master-Worker架构通信机制与零MQ基础]]
