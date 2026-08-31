---
tags: [locust, 断言, SLA]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 响应时间阈值断言与SLA合规性校验.md
---
# 响应时间阈值断言与SLA合规性校验

在 Locust 中，**响应时间阈值断言**与 **SLA 合规性校验**，是性能测试从“发现性能问题”到“验证性能目标”的关键环节。与业务逻辑断言不同，**响应时间断言是统计性的**——它检验的不是单次请求的快慢，而是**在压测周期内，整个请求集合的百分位数（Percentile）是否满足预设标准**。

---

### 1. 核心区别：单次断言 vs. 统计断言

| 维度 | 业务逻辑断言（内容/状态码） | 响应时间 SLA 断言 |
| :--- | :--- | :--- |
| **断言目标** | 单个请求的响应内容 | **整个压测周期内的请求延迟分布** |
| **校验对象** | `resp.json().get("code")` | `stats` 中的 P95、P99、平均响应时间 |
| **触发时机** | 请求返回时立即校验 | **测试结束后**（或定期检查） |
| **失败后果** | 标记该请求失败，影响 `# Failures` | 标记整体测试失败，影响 CI/CD 退出码 |

Locust 本身**不内置** SLA 断言，但通过其丰富的统计 API，你可以轻松实现。

---

### 2. 方案一：测试结束后进行静态 SLA 校验（最常用）

在 `@events.test_stop` 监听器中，从 `environment.runner.stats` 提取统计数据，与预设阈值比较。

```python
from locust import events

# 预设 SLA 阈值（单位：毫秒）
SLA_CONFIG = {
    "/api/order": {"p95": 200, "p99": 500},
    "/api/login": {"p95": 100, "p99": 300},
    "/api/search": {"p95": 500, "p99": 1000},
}

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    测试结束时执行 SLA 校验，若失败则通过环境变量标记状态。
    """
    stats = environment.runner.stats
    # 获取所有请求的统计条目
    entries = stats.entries.values()
    
    sla_passed = True
    for entry in entries:
        name = entry.name
        if name not in SLA_CONFIG:
            continue  # 忽略未定义 SLA 的接口
        
        p95 = entry.get_response_time_percentile(0.95)
        p99 = entry.get_response_time_percentile(0.99)
        expected = SLA_CONFIG[name]
        
        if p95 > expected["p95"]:
            print(f"[SLA 失败] {name} P95={p95}ms > 阈值 {expected['p95']}ms")
            sla_passed = False
        if p99 > expected["p99"]:
            print(f"[SLA 失败] {name} P99={p99}ms > 阈值 {expected['p99']}ms")
            sla_passed = False
    
    # 将结果写入文件或环境变量，供 CI/CD 读取
    with open("sla_result.txt", "w") as f:
        f.write("PASS" if sla_passed else "FAIL")
    
    # 若希望测试进程以非 0 退出码结束（CI/CD 识别失败）
    if not sla_passed:
        environment.process_exit_code = 1
```
**注意**：在 `test_stop` 中设置 `environment.process_exit_code = 1` 后，Locust 进程将以非 0 状态码退出，适用于 Jenkins/GitLab CI 的判断。

---

### 3. 方案二：动态 SLA 监控（压测中途检查）

对于长时间运行的压测（如 24 小时稳定性测试），你可能希望在测试进行中就能检测到 SLA 劣化，并触发告警或自动停止。

```python
import gevent
from locust import events

@events.init.add_listener
def start_sla_monitor(environment, **kwargs):
    """启动一个后台协程，定期检查 SLA 状态"""
    def monitor_loop():
        while True:
            gevent.sleep(60)  # 每 60 秒检查一次
            if environment.runner is None:
                break
            stats = environment.runner.stats
            # 检查关键接口的 P95
            for name, threshold in SLA_CONFIG.items():
                entry = stats.get(name, None)
                if entry and entry.num_requests > 100:  # 有足够样本才判断
                    p95 = entry.get_response_time_percentile(0.95)
                    if p95 > threshold["p95"] * 1.5:  # 超出阈值 50% 视为严重
                        print(f"[告警] {name} P95={p95}ms 严重超阈值！")
                        # 可选：触发环境告警、发送消息、或停止测试
                        # environment.runner.quit()
    gevent.spawn(monitor_loop)
```

---

### 4. 方案三：请求级硬阈值（针对单次请求的绝对上限）

对于某些**极关键接口**（如支付、登录），你可能有单次请求不能超过某值的硬约束（如 >5s 即算失败）。这种方式通过 **`catch_response` + `response_time`** 实现。

```python
@task
def critical_pay(self):
    with self.client.post("/pay", json={...}, catch_response=True) as resp:
        # 假设断言业务成功
        if resp.json().get("code") != 0:
            resp.failure("业务失败")
            return
        
        # 响应时间硬断言
        if resp.elapsed.total_seconds() > 5.0:  # 5 秒绝对上限
            resp.failure(f"响应超时: {resp.elapsed.total_seconds():.2f}s")
        else:
            resp.success()
```

> **注意**：这种方式会影响**失败率**（`# Failures`）指标，而非单独生成 SLA 报告。

---

### 5. 高级实践：百分位数计算原理与验证

Locust 的 `get_response_time_percentile(percentile)` 使用 **HdrHistogram** 算法，以压缩方式存储延迟数据，误差在 1% 以内。

**手动验证百分位数**：可以通过导出的 CSV 文件（`--csv` 参数）离线计算，与 Locust 内置值对比，确保 SLA 校验的准确性。

```python
# 从 CSV 中计算 P95（示例）
import pandas as pd

df = pd.read_csv("stats_stats.csv")
p95 = df[df["Name"] == "/api/order"]["95%"].iloc[0]
```

---

### 6. 多维度 SLA（吞吐量、失败率）

响应时间不是唯一的 SLA 指标。一个完整的 SLA 校验通常包含：

| 指标 | 阈值示例 | 校验方式 |
| :--- | :--- | :--- |
| **P95 响应时间** | < 200ms | `entry.get_response_time_percentile(0.95)` |
| **失败率** | < 0.1% | `entry.num_failures / entry.num_requests` |
| **平均吞吐量（RPS）** | > 1000 | `entry.total_rps` 或 `environment.runner.stats.total.current_rps` |
| **总请求数**（验证是否达到目标压力） | > 100000 | `entry.num_requests` |

```python
def comprehensive_sla_check(environment):
    stats = environment.runner.stats
    for entry in stats.entries.values():
        failure_rate = entry.num_failures / (entry.num_requests + 1e-9)
        if failure_rate > 0.001:  # 0.1%
            print(f"[SLA 失败] {entry.name} 失败率 {failure_rate*100:.2f}%")
            return False
        # 吞吐量检查...
    return True
```

---

### 7. 分布式环境下的 SLA 聚合

在 Master-Worker 模式下，**所有统计在 Master 节点聚合**，因此 SLA 校验只需在 Master 端执行（通常使用 `@events.test_stop` 监听器，它仅在 Master 触发）。

> **重要**：`events.test_stop` 在 **Master 和 Worker 都会触发**。为避免重复校验，可以在监听器中判断 `isinstance(environment.runner, MasterRunner)`（需导入 `MasterRunner`）。

```python
from locust.runners import MasterRunner

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    if not isinstance(environment.runner, MasterRunner):
        return  # Worker 节点跳过
    # 仅在 Master 执行 SLA 校验
```

---

### 8. CI/CD 集成流水线示例

```yaml
# .gitlab-ci.yml 片段
performance-test:
  script:
    - locust -f locustfile.py --headless -u 1000 -r 100 -t 5m --html=report.html
    - python -c "from sla_check import run_sla; run_sla()"  # 自定义 SLA 校验脚本
  after_script:
    - if [ -f sla_result.txt ] && grep -q "FAIL" sla_result.txt; then exit 1; fi
```

---

### 9. 常见陷阱与避坑指南

| 陷阱 | 现象 | 解决方案 |
| :--- | :--- | :--- |
| **样本量不足时百分位数无效** | 刚启动时 P95 异常波动，误判 SLA 失败 | 在 `test_stop` 中检查 `entry.num_requests > 100` 再校验。 |
| **`test_stop` 在 Worker 重复触发** | 同一校验逻辑执行多次，产生多余日志 | 使用 `isinstance(environment.runner, MasterRunner)` 判断。 |
| **SLA 阈值硬编码在脚本中** | 环境不同（dev/staging/prod）需改代码 | 从环境变量或配置文件读取：`os.getenv("SLA_P95_ORDER", 200)`。 |
| **未考虑响应时间单位** | Locust 内部以毫秒存储，配置值用秒表示 | 统一单位，建议配置使用**毫秒**，避免乘以 1000。 |
| **CSV 报告与内存统计不一致** | 命令行 `--csv` 导出的 P95 与 `test_stop` 中计算的有偏差 | 以内存统计为准（实时聚合），CSV 仅作离线备份。 |

---

### 💎 总结

- **SLA 校验是压测的“质量门禁”**，建议作为 CI/CD 流水线的强制检查项。
- **标准做法**：在 `@events.test_stop` 中使用 `get_response_time_percentile` 校验 P95/P99，并设置 `process_exit_code`。
- **进阶需求**：结合后台协程实现**动态 SLA 监控**，在压测中途提前发现性能劣化。
- **完整 SLA 定义**：应包含响应时间、失败率、吞吐量三个维度，全面评估系统表现。

如果你需要**将 SLA 结果以 JSON 格式输出，便于集成到 Prometheus/Grafana 或 Allure 测试报告**，或者想了解**如何将响应时间阈值动态调整为“随并发数升高而放宽”**，可以告诉我，我们继续深入。

## 🔗 关联笔记

[[_MOC-locust]] | [[test_start与test_stop全局事件监听]] | [[GitHubActions、GitLabCI、Jenkins流水线模板配置]] | [[on_start与on_stop生命周期钩子方法]]
