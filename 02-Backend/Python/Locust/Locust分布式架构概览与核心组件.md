---
tags: [locust, architecture, master-worker]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: Locust分布式架构概览与核心组件.md
---
# Locust分布式架构概览与核心组件

理解 Locust 的分布式架构是走向**生产级压测**的关键一步。当单台机器的 CPU 或内存无法模拟目标并发数时，分布式集群能将负载生成能力线性扩展。

Locust 的分布式设计遵循 **“协调-执行”分离** 的原则，架构极其轻量，基于 **ZeroMQ** 实现高速通信。下面我从**顶层拓扑**、**核心组件职责**、**通信机制**、**数据流**和**状态同步陷阱**五个层面为你深度拆解。

---

### 1. 顶层拓扑：一主多从（Master-Worker）

Locust 采用标准的 **Master-Worker** 星型拓扑：

-   **1 个 Master 节点**：不发送任何请求，负责调度、统计聚合和 Web UI 展示。
-   **N 个 Worker 节点**：真正执行压测的“苦力”，运行 `User` 类中的 `@task` 逻辑。
-   **通信端口**：
    -   `5557` (控制端口)：Master 向 Worker 下发指令（启动、停止、调整并发）。
    -   `5558` (数据端口)：Worker 定期向 Master 上报实时统计数据（RPS、响应时间、失败数）。

```text
        [ Web UI / CLI ] 
              |
        +-----v------+
        |   Master   | (协调者 + 统计聚合器)
        | (Port 5557)| (Port 5558)
        +-----+------+
              |
      ZeroMQ 集群通信
              |
    +---------+---------+---------+
    |         |         |         |
+---v---+ +---v---+ +---v---+ +---v---+
|Worker1| |Worker2| |Worker3| |WorkerN| (执行者)
| 协程池 | | 协程池 | | 协程池 | | 协程池 |
+-------+ +-------+ +-------+ +-------+
```


### 2. 核心组件职责详解

#### A. Master 节点（大脑）
-   **调度器 (Scheduler)**：接收 CLI/Web 的并发指令，计算每个 Worker 应分配的用户数（`spawn_count`），通过 ZeroMQ 广播 `spawn` 消息。
-   **统计聚合器 (Stats Aggregator)**：接收所有 Worker 上报的原始请求记录（成功/失败/耗时），进行**归并排序**，计算全局的 RPS、P50/P95/P99、异常率。**注意**：Master 不执行任何 `self.client.get`，它只做 CPU 轻量的计算。
-   **Web Server (Flask)**：提供实时监控界面和 REST API（供 CI/CD 查询状态）。

#### B. Worker 节点（肌肉）
-   **Local Runner**：每个 Worker 内部运行一个独立的 `Runner` 实例。它维护本地的 Greenlet 协程池。
-   **Task Executor**：实例化 `User` 类，按 `wait_time` 和 `@task` 权重循环执行。
-   **Stats Publisher**：每 **3 秒**（默认 `--stats-interval`）将本地的累积统计快照打包，通过 `5558` 端口推送给 Master。

#### C. 通信总线（ZeroMQ）
Locust 选型 ZeroMQ 而非 RabbitMQ/Kafka，因为 ZMQ 是**嵌入式网络库**，不需要额外安装中间件，且延迟极低（微秒级）。
-   **REQ/REP 模式**：用于控制命令，确保指令可靠送达（Worker 必须回复 ACK）。
-   **PUB/SUB 模式**：用于统计数据推送，Worker 发布（PUB），Master 订阅（SUB），允许断连重试，适合高频数据流。

---

### 3. 关键启动与握手流程（运行时序）

当你执行启动命令时，背后发生了一系列精密的握手：

1.  **Worker 注册**：Worker 启动后，通过 `5557` 发送 `client_ready` 消息，携带本机 IP 和 Worker ID。
2.  **Master 确认**：Master 记录活跃 Worker 列表，回复 `spawning` 消息（告知当前无任务）。
3.  **下发负载**：用户在 Web 点击 "Start Swarming"，Master 计算目标数：`per_worker = total_users // worker_count`，下发 `spawn` 指令（包含 User 类名和权重配置）。
4.  **Worker 执行**：Worker 收到指令，立即开始孵化 Greenlet 协程。执行过程**完全自主**，Master 不干涉每个请求的细节。
5.  **心跳保活**：Worker 每秒发送 `heartbeat`，若 Master 超过 3 秒未收到某 Worker 的心跳，则将其标记为 Dead，并在 Web 界面显示掉线。
6.  **数据上报**：Worker 每 3 秒上报统计，Master 实时更新 Web 图表。

---

### 4. 数据流与状态聚合（如何看全局指标）

分布式下，你在 Master Web 界面看到的 **"Total Requests per Second"** 是精确聚合值，但注意以下机制：

```python
# Worker 端（简化逻辑）
def send_stats():
    stats = {
        "entries": [
            {"name": "/api/order", "num_requests": 120, "total_response_time": 24000, "failures": 2}
        ],
        "current_rps": 150.5
    }
    zmq_socket.send_json(stats)  # 推送给 Master

# Master 端（聚合逻辑）
def aggregate(stats_from_all_workers):
    global_rps = sum([w["current_rps"] for w in stats_from_all_workers])
    global_total_requests = sum([w["entries"]["num_requests"] ...])
    # 计算平均响应时间：总耗时 / 总请求数（加权平均）
    global_avg_rt = total_time_sum / total_count
```

-   **响应时间百分位（P95/P99）**：Master 默认**不保留原始全量数据**以节省内存，它使用 **HdrHistogram** 算法进行压缩存储，误差在 1% 以内，用于展示长尾延迟。

---

### 5. 分布式下的关键陷阱与架构限制（实战血泪史）

| 陷阱 | 原因分析 | 解决方案 |
| :--- | :--- | :--- |
| **Worker 间状态不同步** | Worker 进程间内存隔离。例如：每个 Worker 都独立执行 `on_start` 登录，可能导致测试账号被踢下线或 Token 刷新冲突。 | **不要依赖共享内存**。使用 **Redis 或消息队列**在 Worker 间分发唯一 Token 池（使用 `queue.Queue` 在 Worker 启动时预取）。 |
| **Master 成为瓶颈** | 若有 100 个 Worker，每 3 秒上报大量数据，Master 的 Python GIL 在解析 JSON 和聚合计算时可能跑满单核 CPU。 | 减少上报频率（`--stats-interval 10`），或使用 `--processes` 仅用于单机多进程（不推荐分布式混用）。 |
| **网络分区（脑裂）** | Worker 网络闪断，但仍在发送请求，Master 显示 Worker 掉线但仍收到统计数据。 | 设置严格的 `--master-heartbeat-timeout`（默认 3s），超时后 Master 主动断开并尝试重连。 |
| **测试账号资源耗尽** | 分布式下总并发是 `Worker数 × 每Worker并发`，若每个用户需占用一个真实手机号/邮箱，极易耗尽。 | 使用 **参数化数据池**，在 Worker 的 `on_start` 中从共享 Redis List 中 `LPOP` 唯一数据，测试结束 `RPUSH` 归还。 |
| **ZeroMQ 文件描述符限制** | 高并发下 ZMQ 连接数激增，触发 Linux `ulimit -n` 限制。 | 在所有 Worker 机器上执行 `ulimit -n 65535` 再启动 Locust。 |

---

### 6. 分布式容器化部署（K8s / Docker Compose）

生产级分布式压测通常使用容器编排，保证 Worker 的快速扩缩容：

```yaml
# docker-compose.yml 核心片段
services:
  master:
    image: locustio/locust:latest
    ports:
      - "8089:8089"   # Web UI
      - "5557:5557"   # Control
      - "5558:5558"   # Data
    command: -f /mnt/locustfile.py --master --host=https://api.example.com

  worker:
    image: locustio/locust:latest
    # 使用 scale 参数动态扩容
    command: -f /mnt/locustfile.py --worker --master-host=master
    deploy:
      replicas: 10    # 10 个 Worker 并发执行
```

**Kubernetes 下扩容**：直接 `kubectl scale deployment locust-worker --replicas=50`，集群瞬间增加 50 倍压力，非常适合混沌工程。

---

### 7. 你的决策点：单机多进程 vs. 分布式

-   **单机多进程 (`--processes N`)**：适用于单台**物理大内存、多核 CPU** 的机器，通过启动多个 Worker 进程绕开 Python GIL。优点是无需网络通信，数据聚合在本地，延迟最低。
-   **分布式 (`--master` + `--worker`)**：适用于**跨机器**或**K8s 集群**，能突破单机网卡带宽和 TCP 端口限制。

---

### 下一步实战方向

理解了架构后，实际编码中最棘手的往往是 **“分布式环境下如何安全共享动态数据（如 OTP 验证码、库存扣减结果）”**。

如果你想掌握生产级技巧，我建议我们接着探讨以下任一主题：

1.  **分布式数据池设计**：如何结合 Redis 实现 Token 的`申请-使用-释放`机制，避免并发冲突。
2.  **自定义 Master- Worker 消息**：如何让 Worker 向 Master 上报自定义业务指标（如“购物车加购成功数”），并在 Web UI 展示。
3.  **Kubernetes 弹性压测**：如何在压测过程中根据 Master 检测到的 RPS 瓶颈，自动调用 K8s API 水平扩容 Worker 数量。

你对哪个实操方向更感兴趣？我直接给你可运行的代码模板。

## 🔗 关联笔记

[[_MOC-locust]] | [[docker-compose编排Master-Worker分布式集群]] | [[Master-Worker架构通信机制与零MQ基础]] | [[task装饰器定义与任务权重分配]]
