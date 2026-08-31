---
tags: [locust, 分布式, 监控]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 多Worker节点状态监控与异常节点隔离.md
---
# 多Worker节点状态监控与异常节点隔离

在 Locust 分布式压测中，Master 节点通过 **心跳机制** 来监控所有 Worker 的状态，并对异常节点进行 **自动隔离**。

### 💓 核心机制：心跳与状态管理

每个 Worker 节点会定期（默认每 **1 秒**）向 Master 发送心跳包。Master 通过监控这些心跳来判断 Worker 是否存活。心跳相关的核心常量定义在 `locust.runners` 中：

*   **`HEARTBEAT_INTERVAL`**: Worker 发送心跳的间隔，默认 **1 秒**。
*   **`HEARTBEAT_LIVENESS`**: Master 判定 Worker 失联的超时时间，默认 **3 秒**。
*   **`MASTER_HEARTBEAT_TIMEOUT`**: Worker 判定 Master 失联的超时时间，默认 **60 秒**。

> **注意**：这些是源码中的硬编码常量。虽然可通过编程方式调整，但在生产环境中更推荐通过优化脚本和网络环境来避免超时。

### 🚨 异常节点自动隔离机制

当一个 Worker 在 `HEARTBEAT_LIVENESS`（默认3秒）内未发送心跳，Master 会将其状态标记为 **`STATE_MISSING`** (missing)。

*   **负载重分配**：Master 会将该 Worker 上的用户数**重新分配给其他健康的 Worker**。
*   **状态日志**：在 Master 日志中可以看到类似 `"Worker ... failed to send heartbeat, setting state to missing."` 的记录。

> **⚠️ 重要警告**：负载重分配可能导致瞬间 RPS 激增。有案例显示，当一个 Worker 失联后，RPS 可能从 **3,000 瞬间飙升至 10,000**，可能引发被测系统不稳定。

### ✋ 手动隔离 Worker

官方未提供直接“踢出” Worker 的 API，但可通过以下方式实现“软隔离”：

1.  **标记为缺失 (Missing)**：利用 `MasterRunner` 的 `set_state` 方法，将指定 Worker 状态设为 `STATE_MISSING`，使其不再接收新任务。
2.  **通过事件监听实现**：在 `worker_report` 事件中，根据特定逻辑（如失败率过高）手动将 Worker 标记为缺失。

```python
from locust import events
from locust.runners import MasterRunner, STATE_MISSING

@events.worker_report.add_listener
def on_worker_report(environment, client_id, data):
    if isinstance(environment.runner, MasterRunner):
        # 假设根据 worker 上报的数据决定是否隔离
        if data.get("error_rate", 0) > 0.5:  # 错误率超过50%
            worker = environment.runner.clients.get(client_id)
            if worker:
                worker.state = STATE_MISSING
                print(f"手动将 Worker {client_id} 标记为缺失")
```
# 📊 状态监控与告警

#### 1. 内置监控方式
*   **Master 日志**：最直接的方式，会记录 Worker 连接、失联、重分配等事件。
*   **CPU/内存监控**：Master 默认会监控自身 CPU 使用率，超过 90% 时会发出警告。

#### 2. 扩展监控方案
*   **自定义事件监听**：通过 `worker_connect`、`worker_report` 等事件，将 Worker 状态发送到外部监控系统。
*   **Prometheus + Grafana**：使用 Locust 的 `/export/prometheus` 端点暴露指标，在 Grafana 中创建仪表盘进行可视化监控。

### 🛠️ 最佳实践与优化

1.  **提前规划容量**：预留足够的 Worker 冗余（如 N+1），确保单个 Worker 失联不会导致其他 Worker 过载。
2.  **优化压测机性能**：确保 Worker 的 CPU 和内存充足。优先使用性能更高的 **`FastHttpUser`**。
3.  **精细化超时配置**：在 `@events.init` 中调整心跳超时阈值，以适应网络环境。
4.  **使用固定 Worker ID**：在 Kubernetes 等动态环境中，通过 `LOCUST_WORKER_ID_OVERRIDE` 环境变量固定 Worker ID，结合 StatefulSet 确保重启后能被正确识别。
5.  **保持版本一致**：确保 Master 和所有 Worker 的 Locust 版本一致，避免心跳协议不兼容。

### 🔍 常见问题排查

| 问题现象 | 可能原因 | 排查方向 |
| :--- | :--- | :--- |
| **Worker 频繁被标记为 missing** | 网络抖动、Worker 负载过高、自定义消息处理耗时过长 | 检查网络、Worker 资源使用情况，优化脚本 |
| **Worker 无法连接 Master** | 网络不通、防火墙限制、Master 地址错误 | 检查网络连通性、防火墙规则、`--master-host` 参数 |
| **Master 显示 Worker 数不符** | 部分 Worker 启动失败、版本不一致、配置错误 | 检查所有 Worker 启动日志，确保版本和配置一致 |

总的来说，Locust 的自动隔离机制能保障分布式测试的进行，但需关注其可能带来的 RPS 突刺。结合主动监控、合理规划和应急预案，可以构建一个更健壮的压测集群。

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[Prometheus指标导出与Grafana监控大盘构建]] | [[Kubernetes部署资源配置]]
