---
tags: [locust, 分布式, ZeroMQ]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: Master-Worker架构通信机制与零MQ基础.md
---
# Master-Worker架构通信机制与零MQ基础

Locust 的分布式架构是其能够模拟海量并发用户的核心能力所在。这一架构的精髓在于一个清晰的 **“大脑”（Master）与“肌肉”（Worker）** 分离模型，而它们之间的高效沟通，则依赖于一个轻量级、高性能的消息库——**ZeroMQ**。

### 🧠 架构概览：Master 与 Worker 的职责分工

在分布式模式下，Locust 节点分为两种角色：

*   **Master（主节点）**：是**“指挥官”与“数据汇总中心”**。它负责启动 Web 界面、接收并下发测试指令（如启动/停止用户）、聚合所有 Worker 上报的测试结果。Master **不执行任何压测任务**，以确保其资源专注于调度和统计。
*   **Worker（工作节点）**：是**“执行者”**。它们接收 Master 的指令，实际运行你编写的 `User` 类，执行压测任务，并定期将统计数据（如请求响应时间、成功率）发送回 Master。

它们之间的关系，就像一位导演（Master）指挥多个剧组（Worker）同时拍戏，而导演本人并不参与表演。

### 🔌 通信基石：ZeroMQ 的妙用

Master 与 Worker 之间的所有沟通都建立在 **ZeroMQ（简称 ZMQ，也写作 ØMQ）** 之上。

*   **ZeroMQ 是什么？** 它不是一个独立的服务器或消息代理（Broker），而是一个**轻量级的、可嵌入的并发消息库**。你可以把它理解为“增强版的 Socket”，它封装了复杂的网络细节，让节点之间的通信变得像收发消息一样简单。

*   **为什么是 ZeroMQ？**
    *   **高性能与低延迟**：专为高吞吐量的分布式场景设计。
    *   **多种通信模式**：原生支持“请求-应答”、“发布-订阅”等模式，非常适合 Master 广播指令、Worker 上报数据的场景。
    *   **语言无关**：Worker 节点**不一定非要用 Python 实现**。任何支持 ZeroMQ 和 `msgpack` 的语言（如 Go、Java、Node.js）都可以编写 Worker，这为性能优化（如使用 Go 编写的 `boomer`）提供了可能。

### 🔄 消息协议：节点间的“通用语言”

为了让 Master 和 Worker 准确理解对方，它们通过 ZeroMQ 交换 **`msgpack`** 格式的消息。
*   `msgpack` 是一种高效的二进制序列化格式，比 JSON 更小、更快。

常见的消息类型包括：
*   **控制指令**：Master 向 Worker 发送，如 `spawn`（启动用户）、`stop`（停止用户）。
*   **统计数据**：Worker 向 Master 发送，包含 `stats`（请求统计）、`errors`（错误信息）等。
*   **心跳包**：Worker 定期发送给 Master，报告自己“还活着”。

### 🔌 关键端口：分清“指挥”与“观战”

启动分布式压测时，必须区分两个不同的端口，避免混淆：

*   **Web UI 端口（默认 8089）**：这是 Master 用来**向人类展示**测试结果的网页端口。你在浏览器中访问的就是它。
*   **ZeroMQ 通信端口（默认 5557 和 5558）**：
    *   `5557`：用于 Master 向 Worker **下发命令**。
    *   `5558`：用于 Worker 向 Master **上报数据**。

**千万注意**：Worker 通过 `--master-port` 指定的是 **ZeroMQ 的通信端口**（默认 5557），而非 Web UI 的 8089 端口。

### 📜 工作流程：一次完整的分布式压测

1.  **启动 Master**：运行 `locust -f myfile.py --master`，Master 进入监听状态。
2.  **启动 Worker**：在多台机器上运行 `locust -f myfile.py --worker --master-host=<MASTER_IP>`。Worker 启动后，会通过 ZeroMQ 向 Master 进行**注册**。
3.  **下发任务**：你在 Master 的 Web UI 上设置用户数并点击“开始压测”。Master 将指令通过 `5557` 端口广播给所有已注册的 Worker。
4.  **执行与上报**：每个 Worker 根据指令孵化 `User` 协程，开始执行压测任务。同时，Worker 会每隔几秒将本地的统计数据通过 `5558` 端口上报给 Master。
5.  **数据聚合与展示**：Master 汇总所有 Worker 的数据，进行聚合计算，最终在 Web UI 上展示全局的统计结果。

### 💎 总结

理解 Master-Worker 架构和 ZeroMQ 通信机制，是管理和调优大规模分布式压测的基础。这套机制让 Locust 能够协调成百上千个 Worker 节点，共同模拟百万级别的并发用户，是进行大规模容量验证的利器。

如果想深入探索，可以查阅 [Locust 官方文档关于分布式运行的章节](https://docs.locust.io/en/stable/running-distributed.html)。在实际部署中，你可能还会遇到网络配置、文件同步等问题，如果需要了解这些实战细节，可以随时提出。

## 🔗 关联笔记

[[_MOC-locust]] | [[on_start与on_stop生命周期钩子方法]] | [[test_start与test_stop全局事件监听]] | [[Locust分布式架构概览与核心组件]]
