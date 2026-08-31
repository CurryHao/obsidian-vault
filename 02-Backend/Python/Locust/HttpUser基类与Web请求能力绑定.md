---
tags: [locust, HttpUser, HTTP]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: HttpUser基类与Web请求能力绑定.md
---
# HttpUser基类与Web请求能力绑定

`HttpUser` 是 Locust 中最核心、最常用的基类，它本质上是将 **HTTP 请求能力** 与 **用户行为模拟** 深度绑定在一起的实现。理解它的设计思路和能力边界，是编写高效、健壮压测脚本的基础。

### 🎯 `HttpUser` 的本质：一个“会发 HTTP 请求的用户”

`HttpUser` 继承自 `User` 基类，并在其基础上做了两件关键的事情：

1.  **注入 HTTP 客户端**：为每个 `HttpUser` 实例绑定了一个 `self.client` 对象，它是一个经过专门优化的 `HttpSession` 实例。**所有的 HTTP 请求方法（GET、POST、PUT、DELETE 等）都通过这个 `client` 发出**。
2.  **集成统计与监控**：每次通过 `self.client` 发起的请求，其耗时、状态码、成功/失败结果都会被自动捕获，并上报给 Locust 的核心统计引擎，呈现在 Web UI 的图表和报告中。

因此，`HttpUser` 是你压测所有基于 HTTP/HTTPS 协议服务（REST API、网页、微服务网关）的**绝对主力**。

### 🚀 核心能力详解：`self.client` 的“超能力”

`self.client` 是 `HttpUser` 的灵魂，它的能力远超一个普通的 `requests` 库。

#### 1. 自动会话保持与状态管理
`self.client` 基于 `requests.Session` 构建，因此默认支持：
-   **Cookie 持久化**：登录后服务器返回的 Cookie 会自动保存，并在后续请求中自动携带。
-   **默认 Headers**：你可以设置一次通用的请求头（如 `Authorization` 或 `Content-Type`），所有后续请求都会自动包含。

```python
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    # 每个用户启动时执行
    def on_start(self):
        # 登录并设置全局 Token
        resp = self.client.post("/login", json={"user": "test", "pass": "123"})
        token = resp.json()["token"]
        # 此 Headers 将应用于该用户后续所有请求
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task
    def view_profile(self):
        # 自动携带 Authorization Header
        self.client.get("/profile")
```
## 2. 智能命名与统计聚合
`self.client` 发出的每个请求，其 `name` 参数（**必须加，尤其当URL包含动态参数时**）是统计报表中的关键聚合键。

```python
# 正确：所有订单详情请求会被聚合为 "/order/{id}"
self.client.get(f"/order/{order_id}", name="/order/{id}")

# 错误：每单都会生成独立的统计条目，仪表盘将被淹没
self.client.get(f"/order/{order_id}") 
```

#### 3. 精细的响应校验（`catch_response=True`）
对于需要根据**业务返回码**而非 HTTP 状态码来判断成功或失败的场景，必须使用 `catch_response=True`。这允许你手动标记请求结果为成功或失败，并记录自定义失败原因。

```python
@task
def create_order(self):
    with self.client.post("/order", json={"product": "apple"}, catch_response=True) as resp:
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                resp.success()
            else:
                # 业务失败（如库存不足），标记为失败并记录原因
                resp.failure(f"业务错误: {data.get('msg')}")
        else:
            resp.failure(f"HTTP错误: {resp.status_code}")
```

#### 4. 强大的性能优化（`FastHttpUser`）
Locust 官方推荐在压测脚本中**直接导入并使用 `FastHttpUser`**，它是 `HttpUser` 的高性能替代品。

```python
# 只需更改导入，性能即可提升 5-10 倍
from locust import FastHttpUser, task

class MyUser(FastHttpUser):
    @task
    def get_index(self):
        self.client.get("/")
```

`FastHttpUser` 使用 `geventhttpclient` 库，专为高并发场景设计，在连接复用和请求解析上做了深度优化。

### 🔗 与其他高级能力的绑定

-   **负载形状 (LoadTestShape)**：与 `HttpUser` 解耦，通过独立的 `LoadTestShape` 类控制并发曲线，`HttpUser` 只负责响应这些指令。
-   **WebSocket/gRPC**：`HttpUser` 本身不支持，但 Locust 的扩展机制允许你创建 `WebSocketUser` 或 `GrpcUser`，只需保持与 `HttpUser` 相似的 API 设计即可（如自定义 `self.client`）。
-   **事件钩子 (`events`)**：`HttpUser` 发出的每个请求都会触发 `events.request` 事件，你可以挂载监听器来记录日志、发送自定义指标等。

### ⚠️ 注意事项与最佳实践

1.  **不要混用 `requests` 库**：请始终使用 `self.client`，否则 Locust 将**无法统计**那些请求的性能数据。
2.  **利用 `name` 参数聚合动态 URL**：这是保证仪表盘清晰的关键。
3.  **考虑使用 `FastHttpUser`**：对于大多数场景，它都是比 `HttpUser` 更好的起点。
4.  **处理连接超时**：`self.client` 支持 `timeout` 参数，务必为慢接口（如下单、支付）设置合理的超时时间，避免单用户卡死导致整体并发数下降。
    ```python
    self.client.post("/slow-api", timeout=30)
    ```

总而言之，`HttpUser` 通过 `self.client` 将 HTTP 请求能力无缝集成到用户行为中，并提供了完善的统计、校验和性能优化支持。它是你开启 HTTP 压测之旅的起点。

关于 `FastHttpUser` 的底层优化细节，或者如何自定义 `HttpUser` 的 `client` 来支持 HTTP/2 协议，有你想深入了解的方向吗？如果有，我可以继续为你展开。

## 🔗 关联笔记

[[_MOC-locust]] | [[LoadTestShape基类与核心tick方法重写]] | [[继承BaseClient实现WebSocket协议压测]] | [[test_start与test_stop全局事件监听]]
