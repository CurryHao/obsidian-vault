---
tags: [locust, GIL, 性能]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: PythonGIL影响与多进程部署替代方案.md
---
# PythonGIL影响与多进程部署替代方案

Python 的全局解释器锁（GIL）是 CPython 的一个机制，它限制了同一进程中只有一个线程能执行 Python 字节码。这意味着，**即使你的机器有多个 CPU 核心，单个 Locust 进程也只能使用一个核心的计算能力**。

不过，突破这一限制的方法很简单，Locust 官方对此也有清晰的说明。

### 核心影响：RPS 是主要瓶颈

一个常见误区是认为 GIL 会限制并发用户数（Users）。实际上，Locust 基于 gevent 的协程模型非常轻量，**单个进程可以轻松模拟数千甚至数万用户**。

**真正受单核 CPU 限制的是请求吞吐量（RPS，即每秒请求数）**。CPU 需要处理发送请求、解析响应等逻辑。当 RPS 过高时，单核 CPU 会达到瓶颈。

### 量化参考：单进程 RPS 上限

在最佳情况下，单进程（单核）能压出的 RPS 大致如下，实际数值受脚本复杂度、网络延迟等影响：

*   **使用 `HttpUser`（基于 `python-requests`）**：约 **4,000 RPS**。
*   **使用 `FastHttpUser`（基于 `geventhttpclient`）**：约 **16,000 RPS**。`FastHttpUser` API 与 `HttpUser` 几乎一样，但 CPU 效率更高，性能可提升 5-6 倍。

> 建议：若无特殊原因，**应优先使用 `FastHttpUser`**。

---

### 解决方案：多进程部署

为了利用多核 CPU，需要运行多个 Locust 进程（Worker），这是 Locust 官方推荐的方案。

#### 方案一：单机多进程

使用 `--processes` 参数，可以在单台机器上轻松启动一个 Master 和多个 Worker 进程。

*   **指定 Worker 数量**：启动 1 个 Master 和 4 个 Worker。
    ```bash
    locust -f locustfile.py --processes 4
    ```
*   **自动适配 CPU 核心数**：让 Locust 自动为每个 CPU 核心启动一个 Worker。
    ```bash
    locust -f locustfile.py --processes -1
    ```

#### 方案二：多机分布式

当单机资源不足时，可以将 Worker 部署到多台机器上。

1.  **在 Master 机器上**：
    ```bash
    locust -f locustfile.py --master
    ```
2.  **在每个 Worker 机器上**：
    ```bash
    # 每台机器启动 4 个 Worker 进程
    locust -f locustfile.py --worker --master-host=<master_ip> --processes 4
    ```
    在多机模式下，`--processes` 参数仍然有效，可以让每台 Worker 机器也充分利用其多核 CPU。

> **注意**：
> *   `--processes` 参数在 Locust 2.19 版本引入，目前仍处于实验阶段。
> *   该参数使用 `fork()` 创建子进程，**在 Windows 系统上不可用**。
> *   分布式模式下，所有节点（Master 和 Worker）都必须有相同的 `locustfile.py` 文件。

---

### 如何判断是否遭遇 CPU 瓶颈？

当 Locust 进程的 CPU 资源接近耗尽时，**它会在控制台输出一条警告日志**。

如果看到此类警告，说明压测机自身已成为瓶颈，你应该考虑增加 Worker 进程或节点。

### 进阶替代方案：Boomer (Go 语言实现)

对于追求极致性能、希望完全绕过 Python GIL 的场景，可以考虑使用 **Boomer**。

Boomer 是 Locust 的 Go 语言实现，兼容 Locust 的 Master-Worker 通信协议。它没有 GIL 限制，能更充分地利用多核 CPU，在极高并发（如百万级用户）场景下表现更优。

### 总结

| 核心要点 | 说明 |
| :--- | :--- |
| **GIL 限制了单进程的 RPS，而非并发用户数** | 单个进程可模拟海量用户，但 RPS 受限于单核 CPU。 |
| **优选 `FastHttpUser`** | 相比 `HttpUser`，可提升数倍的单进程 RPS 上限。 |
| **使用 `--processes` 实现单机多进程** | 最简单的方式，能让 Locust 利用机器的多核 CPU。 |
| **使用 `--master`/`--worker` 实现多机分布式** | 当单机资源不足时，可水平扩展至多台机器。 |
| **关注 Locust 的 CPU 警告日志** | 这是判断压测机自身是否成为瓶颈的最直接信号。 |

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[docker-compose编排Master-Worker分布式集群]] | [[gevent协程模型与异步并发优势]]
