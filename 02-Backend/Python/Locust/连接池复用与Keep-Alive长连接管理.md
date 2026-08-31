---
tags: [locust, HTTP, 连接池]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 连接池复用与Keep-Alive长连接管理.md
---
# 连接池复用与Keep-Alive长连接管理

在 Locust 中，连接池复用和 Keep-Alive 长连接管理是决定压测性能的关键因素。核心原则是：**尽可能复用连接，减少 TCP 握手开销**。理解 `HttpUser` 和 `FastHttpUser` 的底层差异，能帮你有效避免压测机自身的性能瓶颈。

### 🚀 核心利器：`FastHttpUser`

对于大多数高并发场景，官方推荐的实践是**直接使用 `FastHttpUser`**。

*   **性能飞跃**：`FastHttpUser` 使用 `geventhttpclient` 替代 `requests`，其内置的连接池和更高效的实现能带来 **5-6 倍**的性能提升。在最佳场景下，单进程（单核）可处理约 **16,000 RPS**，而 `HttpUser` 约为 **4,000 RPS**。
*   **无缝切换**：它的 API 与 `HttpUser` 几乎相同，通常只需将导入的基类从 `HttpUser` 替换为 `FastHttpUser` 即可。

```python
# 只需修改这一行导入
from locust import FastHttpUser, task

class MyUser(FastHttpUser):
    @task
    def my_task(self):
        self.client.get("/")
```
# ⚙️ 两种客户端的连接池机制对比

`HttpUser` 和 `FastHttpUser` 对连接的处理方式不同，理解这一点至关重要。

| 特性 | `HttpUser` (基于 `requests`) | `FastHttpUser` (基于 `geventhttpclient`) |
| :--- | :--- | :--- |
| **连接池模型** | **每个用户独立**。每个虚拟用户（`HttpUser`实例）都有自己的连接池。 | **内置共享池**。所有用户共享同一个高效连接池，连接复用率更高。 |
| **默认行为** | 使用 `requests.Session`，默认支持 Keep-Alive 并复用连接。 | **默认启用 Keep-Alive** 和连接复用，开箱即用。 |
| **性能定位** | 功能全面，但高并发下CPU开销较大。 | 性能优先，资源消耗低，**是高并发压测的首选**。 |

### 🛠️ 高级配置：调优连接池

#### 1. 为 `HttpUser` 配置全局共享连接池（不推荐）

`HttpUser` 默认每个用户独立连接池，可能会导致连接数爆炸。虽然可以通过自定义 `PoolManager` 强制所有用户共享一个连接池，但这**会破坏用户隔离性**，可能引入状态污染，通常**不推荐**。

```python
from locust import HttpUser
from urllib3 import PoolManager

class MyUser(HttpUser):
    # 不推荐：所有用户共享同一个连接池，可能引发意外问题
    pool_manager = PoolManager(maxsize=10, block=True) # 限制全局最大10个连接
```

#### 2. 为 `FastHttpUser` 调优连接池大小

`FastHttpUser` 使用 `geventhttpclient`，可通过类属性调整其并发连接数。

```python
from locust import FastHttpUser

class MyUser(FastHttpUser):
    # 调整并发连接数，允许单个用户（或用户组）建立更多并发连接
    concurrency = 100 
```

### 🧪 验证与排查

确保 Keep-Alive 生效，避免因连接未复用导致的性能问题。

*   **检查日志**：压测时观察 Locust 控制台输出。如果出现大量 `ConnectionResetError` 或 `ReadTimeout`，可能意味着服务端未正确支持 Keep-Alive 或连接超时设置过短。
*   **服务端配置**：确认目标服务器的 Keep-Alive 超时时间（如 `keepalive_timeout`）设置合理，通常建议在 1-5 秒之间，避免空闲连接被过早关闭。

### 💎 总结与最佳实践

1.  **首选 `FastHttpUser`**：这是获得最佳性能的最简单方法。
2.  **避免连接泄漏**：确保请求被正确关闭或复用。使用 `with` 语句管理 `catch_response` 是好的实践。
3.  **监控系统资源**：压测时留意 Locust 进程的 CPU 和内存使用情况。如果 CPU 成为瓶颈，说明需要增加 Worker 节点或优化脚本。
4.  **设置合理超时**：配置 `connection_timeout` 和 `network_timeout` 防止连接池被慢请求耗尽。

总的来说，**`FastHttpUser` 是压测的主力**，其内置的连接池和 Keep-Alive 管理已经足够高效，通常无需额外配置。将脚本从 `HttpUser` 迁移到 `FastHttpUser` 是提升压测机性能最直接有效的手段。

## 🔗 关联笔记

[[_MOC-locust]] | [[LoadTestShape基类与核心tick方法重写]] | [[Master-Worker架构通信机制与零MQ基础]] | [[on_start与on_stop生命周期钩子方法]]
