---
tags: [locust, WebSocket]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 继承BaseClient实现WebSocket协议压测.md
---
# 继承BaseClient实现WebSocket协议压测

通过继承 `User` 类来实现自定义客户端，是 Locust 支持非 HTTP 协议（如 WebSocket）的官方方式。其核心在于，通过**手动触发 `events.request` 事件**，将 WebSocket 操作的性能数据纳入 Locust 的统计系统。

下面是一个完整、可直接运行的实现方案。

### 1. 核心设计模式：Client-Wrapper + User

为 WebSocket 编写自定义客户端遵循一个标准模式：

1.  **客户端封装类 (`WebSocketClient`)**：负责管理 WebSocket 连接的生命周期，并封装发送/接收消息的逻辑。其关键职责是**在操作前后记录时间，并手动触发 `events.request` 事件**来上报成功或失败。
2.  **用户类 (`WebsocketUser`)**：继承自 `locust.User`，并实例化上面的客户端类，将其赋值给 `self.client` 属性。
3.  **任务集 (`@task`)**：在用户类的任务方法中，通过 `self.client` 调用 WebSocket 操作方法。

### 2. 实现 WebSocket 客户端 (`WebSocketClient`)

这是整个方案的核心。以下代码使用 `websocket` 库中的 `WebSocketApp`，因为它能很好地与 `gevent` 的协作式调度兼容。

```python
# websocket_client.py
import time
import json
import threading
from locust import events
from websocket import WebSocketApp

class WebSocketClient:
    def __init__(self, host, environment):
        self.host = host
        self.environment = environment
        self.ws = None
        self.connected = False
        # 用于在建立连接时同步的锁
        self._connect_event = threading.Event()

    def connect(self, timeout=10):
        """建立 WebSocket 连接并等待连接成功"""
        self._connect_event.clear()
        self.ws = WebSocketApp(
            self.host,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # WebSocketApp.run_forever() 会阻塞，需在独立线程中运行
        thread = threading.Thread(target=self.ws.run_forever)
        thread.daemon = True
        thread.start()

        # 等待连接建立或超时
        if not self._connect_event.wait(timeout):
            raise ConnectionError(f"WebSocket connection to {self.host} timed out after {timeout}s")

    def _on_open(self, ws):
        """连接成功回调：记录成功事件并释放锁"""
        self.connected = True
        events.request.fire(
            request_type="WEBSOCKET",
            name="connect",
            response_time=0,  # 连接耗时在上层记录更准确
            response_length=0,
            exception=None,
            context={}
        )
        self._connect_event.set()

    def _on_message(self, ws, message):
        """收到消息的回调：记录接收事件"""
        # 注意：此处的 response_time 为0，因为消息是异步推送的
        # 如果要测量从发送到接收的往返时间，需要更复杂的请求-响应关联机制
        events.request.fire(
            request_type="WEBSOCKET",
            name="receive",
            response_time=0,
            response_length=len(message),
            exception=None,
            context={}
        )

    def _on_error(self, ws, error):
        """错误回调：记录失败事件"""
        events.request.fire(
            request_type="WEBSOCKET",
            name="error",
            response_time=0,
            response_length=0,
            exception=error,
            context={}
        )

    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        self.connected = False
        events.request.fire(
            request_type="WEBSOCKET",
            name="close",
            response_time=0,
            response_length=0,
            exception=None,
            context={}
        )

    def send(self, message, name="send"):
        """
        发送消息，并上报请求耗时。
        此方法会阻塞，直到消息被发送或超时。
        """
        start_time = time.perf_counter()
        exception = None
        try:
            # 如果 message 是 dict，自动转为 JSON 字符串
            if isinstance(message, dict):
                message = json.dumps(message)
            self.ws.send(message)
        except Exception as e:
            exception = e

        # 计算耗时并触发事件
        response_time = (time.perf_counter() - start_time) * 1000
        events.request.fire(
            request_type="WEBSOCKET",
            name=name,
            response_time=response_time,
            response_length=len(message) if isinstance(message, str) else 0,
            exception=exception,
            context={}
        )

        if exception:
            raise exception

    def close(self):
        """关闭连接"""
        if self.ws:
            self.ws.close()
```
# 3. 创建 WebSocket 用户类 (`WebsocketUser`)

创建一个抽象基类，封装客户端的初始化逻辑。后续具体的测试用户只需继承此类。

```python
# websocket_user.py
from locust import User
from .websocket_client import WebSocketClient

class WebsocketUser(User):
    # 声明为抽象类，防止 Locust 直接实例化它
    abstract = True

    def __init__(self, environment):
        super().__init__(environment)
        # 在 __init__ 中初始化客户端并建立连接
        self.client = WebSocketClient(host=self.host, environment=environment)
        self.client.connect()
```

### 4. 编写测试任务 (`locustfile.py`)

现在，你可以像使用 `HttpUser` 一样，继承 `WebsocketUser` 并编写具体的压测任务。

```python
# locustfile.py
from locust import task, between
from .websocket_user import WebsocketUser

class ChatUser(WebsocketUser):
    # 用户执行完一个任务后的等待时间
    wait_time = between(1, 5)
    # 目标 WebSocket 服务器地址
    host = "ws://localhost:8765"

    def on_start(self):
        """用户启动时执行，例如发送登录消息"""
        self.client.send({"action": "login", "username": f"user_{self.user_id}"}, name="login")

    @task(3)
    def send_message(self):
        """发送聊天消息"""
        self.client.send({
            "action": "message",
            "room": "general",
            "content": f"Hello from {self.user_id}"
        }, name="chat_message")

    @task(1)
    def send_ping(self):
        """发送心跳 Ping"""
        self.client.send({"action": "ping"}, name="ping")

    def on_stop(self):
        """用户停止时执行，例如关闭连接"""
        self.client.close()
```

### 5. 运行测试

和普通的 Locust 测试一样，通过命令行启动即可。

```bash
# 启动 Web UI
locust -f locustfile.py

# 无界面模式运行
locust -f locustfile.py --headless -u 100 -r 10 -t 1m
```

### 6. 关键考量与最佳实践

-   **`gevent` 兼容性**：确保使用的 WebSocket 库（如 `websocket-client`）可以被 `gevent` 猴子补丁（monkey-patch），以避免阻塞整个 Locust 进程。`websocket-client` 库是兼容的。
-   **长连接管理**：WebSocket 是长连接，应在 `WebsocketUser.__init__()` 或 `on_start()` 中建立，在 `on_stop()` 中关闭。本例在 `__init__` 中建立连接，确保每个虚拟用户启动时就完成握手。
-   **事件驱动 vs. 请求-响应**：WebSocket 是全双工通信。对于服务器主动推送的消息（`on_message`），其 `response_time` 通常设为 0，因为它不是由客户端请求触发的。对于“请求-响应”模式，则需要更复杂的机制（如消息ID关联）来准确测量往返时间。
-   **资源占用**：每个 WebSocket 用户都会维持一个长连接，这会消耗服务器和客户端的文件描述符等资源。大规模压测时，需注意操作系统的 `ulimit -n` 限制。
-   **善用现有轮子**：对于复杂的场景（如 Socket.IO），社区已有成熟的插件，例如 `locust-plugins` 中的 `WebsocketUser`。在自行实现前，可以先评估这些现成的解决方案。

## 🔗 关联笔记

[[_MOC-locust]] | [[on_start与on_stop生命周期钩子方法]] | [[LoadTestShape基类与核心tick方法重写]] | [[HttpUser基类与Web请求能力绑定]]
