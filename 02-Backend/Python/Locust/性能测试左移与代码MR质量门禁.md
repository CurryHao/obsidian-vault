---
tags: [locust, CI/CD, 质量门禁]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 性能测试左移与代码MR质量门禁.md
---
# 性能测试左移与代码MR质量门禁

## 性能测试左移与MR质量门禁（Performance Gate）体系建设

性能测试左移的目标是：**在代码合并到主分支之前，以极低的成本和极短的耗时，完成对变更引入的性能风险的评估**。它不是要在MR阶段完成全链路容量测试，而是构建一道**快速、可靠、增量式**的质量门禁，拦截明显的性能回归。

---

### 一、左移压测与MR门禁的设计理念

| 维度       | 传统压测（右移）                | 左移MR门禁                      |
| -------- | ----------------------- | --------------------------- |
| **触发时机** | 版本发布前/上线后               | 每次MR/PR                     |
| **测试范围** | 全链路、全场景                 | 变更相关的核心API + 烟雾基线           |
| **并发量级** | 生产级（数千~数万）              | 中等量级（50~500）或增量对比           |
| **运行时长** | 10分钟~数小时                | 1~3分钟                       |
| **环境**   | 专属压测环境/生产镜像             | 特性环境或共享测试环境                 |
| **评判标准** | 绝对SLA（失败率<1%，P95<500ms） | **相对基线**（P95恶化<10%，绝对阈值双重卡） |
| **失败处理** | 输出报告，人工分析               | **阻断MR**，强制修复               |

**核心逻辑**：不要求单次MR跑出系统的极限，而是**与上一次基线运行对比**，确认本次变更没有显著拖慢响应时间或增加错误率。

---

### 二、整体架构与数据流

```────────────┐    ┌─────────────────┐    ┌──────────────────┐    ┌────────────┐
│ 开发者提交MR │───▶│ CI触发性能门禁Job │───▶│ 启动特性环境/部署 │───▶│ 执行基准   │
└─────────────┘    └─────────────────┘    └──────────────────┘    │ 压测(5个   │
                                                                  │ 核心API)   │
                                                                  └─────┬──────┘
                                                                        │
┌───────────────────────────────────────────────────────────────────────┘
│
▼
┌──────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│  获取基线数据     │◀───│  比较逻辑            │───▶│  判断/输出报告    │
│  (最近一次主分支  │    │  (相对变化率 + 绝对阈值)│    │  阻断/通过MR     │
│   压测结果存储)   │    └─────────────────────┘    └──────────────────┘
└──────────────────┘
```

---

### 三、Locustfile 设计：专为门禁设计的轻量级测试

门禁场景不需要全量业务，只覆盖**变更最可能影响的2~5个核心读/写接口**，压测时长控制在**60~120秒**。

```python
# perf_gate_locustfile.py
from locust import HttpUser, task, between, events
import os
import json
import time

class GateUser(HttpUser):
    """MR门禁专用用户：轻量、快速、稳定"""
    
    # 固定思考时间短（模拟机器流量）
    wait_time = between(0.5, 1.5)
    
    # 只压测核心读接口和关键写接口
    @task(5)
    def get_user_profile(self):
        self.client.get("/api/v1/users/me", name="01_get_profile")
    
    @task(3)
    def list_orders(self):
        self.client.get("/api/v1/orders?limit=10", name="02_list_orders")
    
    @task(2)
    def create_order(self):
        # 写操作需使用幂等数据
        payload = {
            "product_id": "GATE_TEST_001",
            "quantity": 1,
            "timestamp": int(time.time())
        }
        self.client.post("/api/v1/orders", json=payload, name="03_create_order")
    
    @task(1)
    def search_products(self):
        self.client.get("/api/v1/products?keyword=test", name="04_search")

# 测试结束时，将关键指标输出到标准输出，便于CI捕获
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    result = {
        "timestamp": int(time.time()),
        "total_requests": total.num_requests,
        "failure_rate": total.num_failures / max(1, total.num_requests),
        "avg_rt_ms": total.avg_response_time,
        "p95_ms": total.get_response_time_percentile(0.95),
        "p99_ms": total.get_response_time_percentile(0.99),
        "endpoints": {}
    }
    for (name, method), entry in stats.entries.items():
        result["endpoints"][name] = {
            "requests": entry.num_requests,
            "failures": entry.num_failures,
            "p95_ms": entry.get_response_time_percentile(0.95)
        }
    
    # 输出JSON到文件，供流水线解析
    with open("gate_result.json", "w") as f:
        json.dump(result, f, indent=2)
    
    # 同时打印到控制台，便于流水线日志查看
    print("\n" + "="*60)
    print(f"PERF GATE RESULT: P95={result['p95_ms']:.0f}ms, Failure={result['failure_rate']*100:.2f}%")
    print("="*60)
```

---

### 四、基线存储与管理

MR门禁的核心是**与基线对比**，基线通常是最近一次主分支通过的压测结果。

#### 方案A：存储为JSON文件（Git LFS或制品库）
```json
// baseline.json (存储在制品库或Git LFS)
{
  "commit_sha": "abc123",
  "timestamp": 1721800000,
  "p95_ms": 120,
  "failure_rate": 0.001,
  "endpoints": {
    "01_get_profile": {"p95_ms": 100, "failure_rate": 0.001},
    "02_list_orders": {"p95_ms": 150, "failure_rate": 0.002},
    "03_create_order": {"p95_ms": 200, "failure_rate": 0.001},
    "04_search": {"p95_ms": 80, "failure_rate": 0.0}
  }
}
```

#### 方案B：存储于InfluxDB/TimescaleDB（推荐）
便于历史趋势与多人协作：
```sql
-- 存储基线
INSERT INTO performance_baseline (branch, commit_sha, p95_ms, failure_rate, endpoints_json, created_at)
VALUES ('main', 'abc123', 120, 0.001, '{"01_get_profile": {...}}', NOW());
```

在门禁流水线中查询最近一次主分支通过的基线：
```sql
SELECT * FROM performance_baseline 
WHERE branch = 'main' AND status = 'passed' 
ORDER BY created_at DESC LIMIT 1;
```

---

### 五、质量门禁判定逻辑（Python脚本）

```python
# scripts/perf_gate_judge.py
import json
import sys
import math

def load_baseline(baseline_path):
    with open(baseline_path, 'r') as f:
        return json.load(f)

def load_current_result(result_path):
    with open(result_path, 'r') as f:
        return json.load(f)

def judge(baseline, current, 
          p95_regression_threshold=10,   # P95恶化百分比阈值（%）
          failure_rate_abs_threshold=1.0, # 失败率绝对阈值（%）
          p95_abs_threshold=500,          # P95绝对上限（ms）
          required_endpoints=None):       # 必须覆盖的端点列表
    
    # 1. 检查端点覆盖率（防止因为404/500导致测试失效）
    if required_endpoints:
        current_endpoints = set(current['endpoints'].keys())
        missing = set(required_endpoints) - current_endpoints
        if missing:
            print(f"❌ 缺少关键端点压测数据: {missing}")
            return False, "missing_endpoints"
    
    # 2. 绝对失败率检查
    failure_rate_pct = current['failure_rate'] * 100
    if failure_rate_pct > failure_rate_abs_threshold:
        print(f"❌ 失败率 {failure_rate_pct:.2f}% > {failure_rate_abs_threshold}%")
        return False, "failure_rate_high"
    
    # 3. 绝对P95检查
    if current['p95_ms'] > p95_abs_threshold:
        print(f"❌ P95 {current['p95_ms']:.0f}ms > {p95_abs_threshold}ms")
        return False, "p95_abs_exceed"
    
    # 4. 相对基线回归检查（各端点分别检查）
    regression_detected = False
    for endpoint, ep_data in current['endpoints'].items():
        if endpoint not in baseline['endpoints']:
            continue  # 新增端点，跳过回归检查
        baseline_p95 = baseline['endpoints'][endpoint]['p95_ms']
        current_p95 = ep_data['p95_ms']
        if baseline_p95 > 0:
            change_pct = (current_p95 - baseline_p95) / baseline_p95 * 100
            if change_pct > p95_regression_threshold:
                print(f"⚠️ 端点 [{endpoint}] P95 恶化: {baseline_p95:.0f}ms -> {current_p95:.0f}ms ({change_pct:+.1f}%)")
                regression_detected = True
    
    if regression_detected:
        print(f"❌ 检测到性能回归（P95恶化 > {p95_regression_threshold}%）")
        return False, "p95_regression"
    
    # 5. 全部通过
    print("✅ 性能门禁通过：无显著回归，指标在阈值范围内")
    return True, "passed"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, help="基线JSON文件路径")
    parser.add_argument("--current", required=True, help="当前压测结果JSON路径")
    parser.add_argument("--p95-threshold", type=float, default=10, help="P95恶化百分比阈值")
    parser.add_argument("--failure-rate", type=float, default=1.0, help="失败率绝对阈值(%)")
    parser.add_argument("--p95-abs", type=int, default=500, help="P95绝对阈值(ms)")
    parser.add_argument("--required-endpoints", nargs='+', default=[], help="必须覆盖的端点名列表")
    args = parser.parse_args()
    
    baseline = load_baseline(args.baseline)
    current = load_current_result(args.current)
    
    passed, reason = judge(
        baseline, current,
        p95_regression_threshold=args.p95_threshold,
        failure_rate_abs_threshold=args.failure_rate,
        p95_abs_threshold=args.p95_abs,
        required_endpoints=args.required_endpoints if args.required_endpoints else None
    )
    
    if not passed:
        sys.exit(1)  # 阻断流水线
    sys.exit(0)
```

---

### 六、GitLab CI 流水线模板（集成门禁）

```yaml
# .gitlab-ci.yml (性能门禁Job)
stages:
  - deploy-test-env
  - performance-gate
  - e2e-test

variables:
  PERF_GATE_USERS: 50
  PERF_GATE_RUN_TIME: "2m"
  PERF_GATE_SPAWN_RATE: 10

# 仅当MR涉及API代码变更时触发门禁
.performance_gate_rules: &perf_gate_rules
  rules:
    - if: '$CI_MERGE_REQUEST_IID && ($CI_MERGE_REQUEST_TARGET_BRANCH_NAME == "main" || $CI_MERGE_REQUEST_TARGET_BRANCH_NAME == "develop")'
      changes:
        - src/api/**/*
        - src/controllers/**/*
        - locustfile.py

performance-gate:
  stage: performance-gate
  image: python:3.11-slim
  rules:
    - *perf_gate_rules
  before_script:
    - pip install locust pandas requests
  script:
    # 1. 下载基线数据（来自主分支最近的压测制品）
    - |
      if [ -f "baseline.json" ]; then
        echo "使用本地基线文件"
      else
        echo "从制品库拉取基线..."
        # 假设基线存储在 MinIO/S3 或 GitLab 通用包库
        curl -o baseline.json ${BASE_URL}/baseline.json || echo "基线不存在，使用保守默认值"
      fi
    
    # 2. 启动目标服务（假设已在 pre-stage 完成部署）
    # 3. 运行门禁压测
    - mkdir -p reports
    - locust -f perf_gate_locustfile.py --headless 
        --host ${TARGET_HOST} 
        -u ${PERF_GATE_USERS} 
        -r ${PERF_GATE_SPAWN_RATE} 
        -t ${PERF_GATE_RUN_TIME} 
        --loglevel WARNING 
        --html=reports/gate_report.html
    
    # 4. 执行判定
    - python scripts/perf_gate_judge.py 
        --baseline baseline.json 
        --current gate_result.json 
        --p95-threshold 10 
        --failure-rate 1.0 
        --p95-abs 500 
        --required-endpoints 01_get_profile 02_list_orders
    
    # 5. 如果当前MR通过，更新基线（可选：仅当分支为main时）
    - |
      if [ "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" == "main" ] && [ $? -eq 0 ]; then
        echo "MR合并到主分支，更新基线..."
        cp gate_result.json baseline.json
        # 上传到制品库
        curl -X PUT -T baseline.json ${BASE_URL}/baseline.json
      fi
  artifacts:
    when: always
    paths:
      - reports/gate_report.html
      - gate_result.json
    expire_in: 7 days
```

---

### 七、GitHub Actions 集成

```yaml
# .github/workflows/perf-gate.yml
name: Performance Gate

on:
  pull_request:
    branches: [ main, develop ]
    paths:
      - 'src/api/**'
      - 'src/controllers/**'
      - 'locustfile.py'

jobs:
  perf-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install locust pandas
      
      - name: Download baseline from main branch
        run: |
          curl -s -o baseline.json \
            https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main/perf_baseline.json \
            || echo '{"p95_ms": 200, "failure_rate": 0.001, "endpoints": {}}' > baseline.json
      
      - name: Deploy target service (mini)
        run: |
          # 如果是微服务，可快速启动单体测试模式
          docker-compose -f docker-compose.test.yml up -d
          sleep 10
      
      - name: Run performance gate
        run: |
          locust -f perf_gate_locustfile.py --headless \
            --host http://localhost:8080 \
            -u 50 -r 10 -t 2m \
            --loglevel WARNING
      
      - name: Judge gate result
        id: judge
        run: |
          python scripts/perf_gate_judge.py \
            --baseline baseline.json \
            --current gate_result.json
      
      - name: Upload gate report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: perf-gate-report
          path: reports/gate_report.html
      
      - name: Comment PR with result
        if: always()
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          header: perf-gate
          message: |
            ## 🚦 Performance Gate Result
            - **P95**: `${{ fromJSON(gate_result.json).p95_ms }}ms`
            - **Failure Rate**: `${{ fromJSON(gate_result.json).failure_rate * 100 }}%`
            - **Status**: ${{ steps.judge.outputs.passed == 'true' && '✅ Pass' || '❌ Block' }}
            > [View Full Report](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})
```

---

### 八、Jenkins 流水线实现（Groovy）

```groovy
// Jenkinsfile (性能门禁)
pipeline {
    agent any
    
    parameters {
        booleanParam(name: 'SKIP_PERF_GATE', defaultValue: false, description: '跳过性能门禁？')
    }
    
    stages {
        stage('Performance Gate') {
            when {
                expression { 
                    // 仅对MR且包含API变更时触发
                    return (env.CHANGE_TARGET == 'main' || env.CHANGE_TARGET == 'develop') 
                           && !params.SKIP_PERF_GATE
                }
            }
            steps {
                script {
                    // 1. 准备基线
                    if (fileExists('baseline.json')) {
                        echo '使用本地基线'
                    } else {
                        // 从制品服务器下载基线
                        sh 'curl -o baseline.json ${BASELINE_SERVER_URL}/locust_baseline.json'
                    }
                    
                    // 2. 运行压测
                    sh '''
                        pip install locust
                        locust -f perf_gate_locustfile.py --headless \
                            --host ${TARGET_HOST} \
                            -u 50 -r 10 -t 2m \
                            --loglevel WARNING
                    '''
                    
                    // 3. 执行判定并设置构建状态
                    def judgeResult = sh(
                        script: '''
                            python scripts/perf_gate_judge.py \
                                --baseline baseline.json \
                                --current gate_result.json \
                                --p95-threshold 10
                        ''',
                        returnStatus: true
                    )
                    
                    if (judgeResult != 0) {
                        error("性能门禁未通过，请检查性能回归！")
                    }
                }
            }
            post {
                always {
                    // 归档报告
                    archiveArtifacts artifacts: 'reports/*.html, gate_result.json', fingerprint: true
                    // 更新基线（如果当前是主分支且通过）
                    if (env.BRANCH_NAME == 'main' && currentBuild.result == 'SUCCESS') {
                        sh 'cp gate_result.json baseline.json'
                        // 上传到制品服务器
                    }
                }
            }
        }
    }
}
```

---

### 九、常见挑战与解决方案

| 挑战 | 解决方案 |
|------|---------|
| **环境差异导致响应时间波动** | 使用**相对变化率**（如 <10%）而非绝对数值作为主要判定依据；对读写操作使用幂等数据；预热运行 10s 后再采集指标 |
| **基线数据不可靠** | 基线应取 **最近 3 次主分支通过结果的中位数**，而非单次值；基线需带有 `commit_sha`，自动更新 |
| **测试数据污染** | 为每条压测使用**独立租户**或 **`test_user_{timestamp}`** 动态身份；写操作使用**幂等性设计**或测试后数据回滚 |
| **压测结果不稳定** | 将 MR 门禁的并发数控制在 **20~200** 的低水位，避免触发系统限流/熔断干扰评判；重复执行 3 轮取中位数 |
| **新接口无基线** | 新接口跳过回归比较，但必须通过**绝对阈值**（P95 < 500ms，失败率 < 1%） |
| **门禁耗时过长** | 限定总时长 < 3 分钟；使用分布式模式时预置 Worker，避免拉起耗时；必要时允许高级用户通过 `/skip-perf` 跳过 |

---

### 十、最佳实践总结

1. **门禁指标双轨制**：绝对阈值兜底 + 相对回归拦截，防止基线下沉。
2. **基线智能化**：基线自动更新（仅主分支通过时），无需人工维护。
3. **快速反馈**：门禁总耗时控制在 **3 分钟以内**，避免拖慢研发流转。
4. **可观测性透传**：将门禁结果以 **PR/MR 评论** 形式自动呈现，便于开发者理解失败原因。
5. **分层策略**：MR 门禁仅做轻量烟雾测试（50~100 并发），**定期夜间任务**再做全链路容量测试（数千并发），形成“日常左移快速反馈 + 夜间深度扫描”的组合拳。

通过以上体系，你可以在不牺牲研发效率的前提下，将性能风险拦截在合并之前，真正实现性能测试的 **“左移”与“自动化”**。

## 🔗 关联笔记

[[_MOC-locust]] | [[GitHubActions、GitLabCI、Jenkins流水线模板配置]] | [[InfluxDB持久化存储与历史趋势对比]] | [[LoadTestShape基类与核心tick方法重写]]
