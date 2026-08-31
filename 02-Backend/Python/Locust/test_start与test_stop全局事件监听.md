---
tags: [locust, 事件, 钩子]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: test_start与test_stop全局事件监听.md
---
# test_start与test_stop全局事件监听

`test_start` 与 `test_stop` 是 Locust 中**全局生命周期级别**的事件监听器，它们在压测任务**开始前**和**完全结束后**各触发一次。

与 `on_start`（每个用户执行一次）不同，`test_start`/`test_stop` 在整个测试进程中只执行一次，非常适合做**全局资源初始化**、**共享数据预热**以及**最终报告生成**。

---

### 1. 核心机制：执行时机与作用域

| 事件 | 触发时机 | 典型用途 | 执行频率 |
| :--- | :--- | :--- | :--- |
| **`test_start`** | 用户开始孵化（Swarming）**之前** | 初始化共享数据库连接池、加载全局测试数据、清理上一轮残留数据 | 整个测试生命周期**仅 1 次** |
| **`test_stop`** | 所有用户完全停止、统计聚合完成**之后** | 生成 SLA 报告、导出最终统计数据、关闭全局连接、发送测试完成通知 | 整个测试生命周期**仅 1 次** |

> **重要时机**：`test_start` 在 Web UI 点击 "Start Swarming" 或命令行 `--headless` 启动时触发；`test_stop` 在点击 "Stop" 或 `-t` 运行时长耗尽后触发。

---

### 2. 基本用法：装饰器注册

```python
from locust import events
import time

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """压测开始前执行：打印启动日志，加载数据"""
    print(f"[{time.ctime()}] 压测启动，目标并发: {environment.runner.target_user_count}")
    # 例如：加载账号池到 Redis
    # load_account_pool()

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """压测结束后执行：打印总结，导出报告"""
    stats = environment.runner.stats
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    print(f"[{time.ctime()}] 压测结束，总请求: {total_requests}, 失败: {total_failures}")
    # 例如：将结果写入数据库
    # save_final_report(stats)
```


### 3. 分布式环境下的关键行为（Master vs Worker）

这是**最容易被忽略的陷阱**：`test_start` 和 `test_stop` **会在 Master 和所有 Worker 节点上同时触发**。

- **影响**：如果你在 `test_start` 中初始化了一个数据库连接池，每个 Worker 都会创建一份，可能导致连接数爆炸。
- **解决方案**：通过判断 `environment.runner` 的类型来区分角色。

```python
from locust import events
from locust.runners import MasterRunner, WorkerRunner

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        # 仅在 Master 执行：发送通知、记录主日志
        print("Master 启动，准备调度任务")
    elif isinstance(environment.runner, WorkerRunner):
        # 仅在 Worker 执行：连接本地缓存、准备数据
        print("Worker 启动，准备执行任务")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        # 仅在 Master 执行 SLA 校验（因为统计数据在 Master 聚合）
        check_sla(environment)
```

---

### 4. 实战场景与代码模板

#### A. 场景一：在 `test_start` 中预加载共享测试数据
避免在用户 `on_start` 中反复读取 CSV/DB，减少启动时的资源竞争。

```python
import csv
from locust import events

TEST_ACCOUNTS = []  # 全局变量，所有 User 共享

@events.test_start.add_listener
def load_test_data(environment, **kwargs):
    """只在 Worker 启动时加载一次 CSV 数据"""
    if isinstance(environment.runner, WorkerRunner):
        with open("accounts.csv", "r") as f:
            reader = csv.DictReader(f)
            TEST_ACCOUNTS.extend(list(reader))
        print(f"加载 {len(TEST_ACCOUNTS)} 个测试账号")

# 在 User 中使用全局变量
class MyUser(HttpUser):
    @task
    def login(self):
        account = random.choice(TEST_ACCOUNTS)  # 共享只读，安全
        self.client.post("/login", json=account)
```

#### B. 场景二：在 `test_stop` 中生成 SLA 合规报告（与上一节联动）
结合上一讲的 SLA 校验，在测试结束时输出 JSON 格式报告。

```python
import json
from locust import events
from locust.runners import MasterRunner

@events.test_stop.add_listener
def generate_sla_report(environment, **kwargs):
    if not isinstance(environment.runner, MasterRunner):
        return  # 仅在 Master 执行
    
    stats = environment.runner.stats
    report = {
        "timestamp": time.time(),
        "total_requests": stats.total.num_requests,
        "failure_rate": stats.total.fail_ratio,
        "avg_response_time": stats.total.avg_response_time,
        "p95": stats.total.get_response_time_percentile(0.95),
        "p99": stats.total.get_response_time_percentile(0.99),
    }
    
    # 写入文件供 CI/CD 解析
    with open("sla_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # 设置退出码（若不符合预期）
    if report["failure_rate"] > 0.01 or report["p95"] > 500:
        environment.process_exit_code = 1
```

#### C. 场景三：外部集成（发送 Webhook 或钉钉通知）

```python
import requests
from locust import events

@events.test_start.add_listener
def notify_start(environment, **kwargs):
    requests.post("https://webhook.example.com/start", json={"status": "load_test_started"})

@events.test_stop.add_listener
def notify_stop(environment, **kwargs):
    requests.post("https://webhook.example.com/stop", json={"status": "load_test_finished"})
```

---

### 5. 与 `init` 事件的区别（容易混淆）

| 维度 | **`init`** | **`test_start`** |
| :--- | :--- | :--- |
| **触发时机** | Locust **进程启动时**（导入脚本阶段） | 压测**实际开始施压时**（用户孵化开始前） |
| **命令行影响** | `--list`、`--help` 也会触发 `init` | 只有真正运行测试才触发 |
| **典型用途** | 注册命令行参数、设置全局日志格式 | 加载动态数据、预热缓存 |
| **能否访问 `runner`** | ❌ `environment.runner` 可能为 `None` | ✅ `environment.runner` 已初始化 |

---

### 6. 关键陷阱与最佳实践

| 陷阱 | 后果 | 解决方案 |
| :--- | :--- | :--- |
| **在 `test_start` 中执行耗时操作（>5秒）** | 延迟用户孵化，导致启动阶段超时 | 使用 `gevent.spawn` 异步执行，或提前在 `init` 中加载静态数据。 |
| **在 `test_stop` 中调用 `response.failure()`** | 失败统计已固化，新失败不会被记录 | 仅使用 `events.request.fire` 或打印日志，不要尝试修改统计。 |
| **未区分 Master/Worker，重复执行写操作** | 多个 Worker 同时写同一文件导致冲突 | 始终用 `isinstance(environment.runner, MasterRunner)` 保护写操作。 |
| **`test_stop` 中访问 `environment.runner.stats` 为空** | 测试未启动或中途崩溃 | 增加空值判断：`if environment.runner and environment.runner.stats`。 |
| **测试进程被 `SIGKILL` 强制杀死** | `test_stop` 不会执行 | 依赖进程信号捕获（`signal.signal`）处理极端情况，但无法完全保证。 |

---

### 7. 完整的生命周期时序图

```text
[ Locust 进程启动 ]
        |
  触发 `init` 事件 (注册自定义参数)
        |
[ 点击 Start / 启动 headless ]
        |
  触发 `test_start` (Master & Worker)  <--- 适合预热数据
        |
  开始孵化用户 (调用 `on_start`)
        |
  执行 `@task` 循环
        |
[ 点击 Stop / 运行时间到 ]
        |
  停止所有用户 (调用 `on_stop`)
        |
  聚合最终统计数据
        |
  触发 `test_stop` (Master & Worker)  <--- 适合生成报告、SLA校验
        |
[ 进程退出 ]
```

---

### 💎 总结

- **`test_start`** 是你的“**发令枪**”：用于全局资源的**一次性准备**，避免在成千上万的用户中重复初始化。
- **`test_stop`** 是你的“**终点线**”：用于**收尾工作**和 **SLA 终验**，是 CI/CD 流水线质量门禁的核心钩子。
- **黄金法则**：若涉及写文件/数据库/网络请求，务必用 `isinstance(environment.runner, MasterRunner)` 包裹，确保只执行一次。

如果你需要**在 `test_start` 中启动一个后台协程，持续监控 CPU/内存并实时输出到 CSV**，或者想了解**如何通过 `test_stop` 将压测结果自动回传到 JIRA/TestLink**，可以告诉我，我们继续深化。

## 🔗 关联笔记

[[_MOC-locust]] | [[on_start与on_stop生命周期钩子方法]] | [[Master-Worker架构通信机制与零MQ基础]] | [[LoadTestShape基类与核心tick方法重写]]
