---
tags: [locust, 生命周期]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: on_start与on_stop生命周期钩子方法.md
---
# on_start与on_stop生命周期钩子方法

`on_start` 和 `on_stop` 是 Locust 赋予每个用户（`User` 实例）的**生命周期钩子方法**。它们让你能在用户开始执行任务之前进行初始化，以及在用户退出（或被终止）时进行收尾工作，是构建**有状态、高仿真**压测脚本的基石。

---

### 1. 执行时机与核心特性

*   **`on_start`**：
    *   **执行时机**：在 `User` 实例（协程）被孵化出来后，**执行任何 `@task` 之前**调用。
    *   **关键特性**：该方法**不受 `wait_time` 影响**，执行完毕后立即开始任务循环。若该方法抛出异常或调用了 `StopUser`，该用户实例将**直接终止**，不会执行任何 `@task`。
    *   **典型用途**：登录获取 Token、加载用户专属配置、从数据池获取唯一账号。

*   **`on_stop`**：
    *   **执行时机**：在 `User` 实例**即将被销毁**时调用（测试结束、用户被手动停止、或 `on_start`/任务中抛出了 `StopUser`）。
    *   **关键特性**：**不保证一定执行**（如进程被 SIGKILL 强制杀死、网络断开时）。执行期间同样**不受 `wait_time` 影响**。
    *   **典型用途**：主动登出（释放服务端 Session）、归还数据池的账号、上报最终自定义指标。

---

### 2. 基础实践：登录与登出

最经典的用法是在 `on_start` 中完成认证，在 `on_stop` 中清理会话。

```python
from locust import HttpUser, task, between
from locust.exception import StopUser

class AuthenticatedUser(HttpUser):
    wait_time = between(1, 3)
    token: str | None = None

    def on_start(self):
        """每个用户启动时：模拟登录并获取JWT"""
        # 注意：这里不遵循 wait_time，直接发起请求
        resp = self.client.post(
            "/auth/login",
            json={"username": f"perf_user_{self.user_id}", "password": "Pass@2024"}
        )
        
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            # 设置全局请求头，后续所有 @task 自动携带
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"User {self.user_id} logged in successfully.")
        else:
            # 登录失败则终止该用户，不执行任何测试任务
            print(f"User {self.user_id} login failed! Stopping.")
            raise StopUser()

    def on_stop(self):
        """用户退出时：调用登出接口释放服务端资源"""
        if self.token:
            # 即使请求失败，也不影响用户终止流程（可try包裹）
            try:
                self.client.post("/auth/logout", json={"token": self.token})
                print(f"User {self.user_id} logged out.")
            except Exception:
                pass  # 保证清理逻辑不影响进程退出

    @task
    def view_dashboard(self):
        self.client.get("/dashboard", name="01_查看仪表盘")
```

### 3. 关键陷阱：`on_start` 与 `on_stop` 在继承中的行为

*   **覆盖而非重载**：如果子类定义了 `on_start`，**父类的 `on_start` 不会自动执行**。需要显式调用 `super().on_start()`。
*   **`TaskSet` 中的钩子**：除了 `HttpUser`，`TaskSet` 和 `SequentialTaskSet` 也支持 `on_start`/`on_stop`，作用域缩小到该任务集内部。

```python
from locust import SequentialTaskSet, task

class BaseUser(HttpUser):
    def on_start(self):
        print("父类登录...")
        self.client.post("/base_login")

class RealUser(BaseUser):
    def on_start(self):
        # 若不调用 super，父类登录逻辑不会执行
        super().on_start()  
        print("子类专属初始化...")
        self.client.post("/vip_init")

    @task
    class OrderFlow(SequentialTaskSet):
        # 此 TaskSet 的 on_start 在进入该任务集时执行
        def on_start(self):
            print("进入下单流程，加载购物车...")
        
        @task
        def step1(self): ...

        @task
        def step2(self): ...
```

---

### 4. 高级用法：数据池申请与归还（分布式友好）

在分布式压测中，`on_start` 和 `on_stop` 是管理**共享测试资源**（如账号池、优惠券码）的黄金搭档。

```python
import redis
from locust import HttpUser, task
from locust.exception import StopUser

class PoolUser(HttpUser):
    # 假设使用 Redis List 存储账号，LPOP 取，RPUSH 还
    redis_client = redis.Redis(host='cache.shared', decode_responses=True)
    my_account: str | None = None

    def on_start(self):
        """从Redis池中抢占一个账号（阻塞直到有账号可用）"""
        # 注意：长时间阻塞会拖慢孵化速度，建议设置超时或快速失败
        account = self.redis_client.blpop("account_pool", timeout=5)
        if not account:
            print("账号池已空，无法启动用户")
            raise StopUser()
        self.my_account = account[1]
        print(f"User {self.user_id} 领取账号: {self.my_account}")

    def on_stop(self):
        """归还账号，供其他Worker或后续用户使用"""
        if self.my_account:
            self.redis_client.rpush("account_pool", self.my_account)
            print(f"User {self.user_id} 归还账号: {self.my_account}")

    @task
    def use_account(self):
        self.client.post("/action", json={"account": self.my_account})
```

---

### 5. `on_start` 失败时的优雅降级策略

当 `on_start` 失败时，除了 `raise StopUser()`，你还可以结合 `catch_response` 将失败计入统计，但**不建议**在 `on_start` 中直接调用 `self.client.get(..., catch_response=True)` 来标记成功/失败，因为钩子方法本身不参与 `@task` 的统计循环。

若希望记录初始化失败率，推荐通过 `events.request` 手动触发统计：

```python
from locust import events
import time

def on_start(self):
    start_time = time.time()
    try:
        resp = self.client.post("/login", json={...})
        if resp.status_code != 200:
            raise Exception("Login failed")
        # 手动记录成功
        events.request.fire(
            request_type="INIT",
            name="login",
            response_time=(time.time() - start_time) * 1000,
            response_length=0,
            exception=None,
        )
    except Exception as e:
        # 手动记录失败
        events.request.fire(
            request_type="INIT",
            name="login",
            response_time=(time.time() - start_time) * 1000,
            response_length=0,
            exception=e,
        )
        raise StopUser()  # 依然终止用户
```

---

### 6. `on_stop` 的可靠性陷阱

| 陷阱 | 现象 | 解决方案 |
| :--- | :--- | :--- |
| **进程暴力退出** | `on_stop` 未执行，导致账号未归还 | 账号池可设置超时自动过期（如 Redis TTL），或在测试脚本中捕获信号量（`signal`）。 |
| **`on_stop` 自身异常** | 清理逻辑报错，导致进程退出卡顿 | 务必用 `try...except` 包裹所有清理代码，确保 `on_stop` 执行完毕。 |
| **Master 主动停止测试** | Worker 收到 `quit` 指令，会尝试执行 `on_stop` | 正常停止流程下会执行；若使用 `--stop-timeout`，会给用户充足时间完成清理。 |

---

### 7. 生命周期时序图

为了帮你直观理解，这是单个 User 实例从生到死的完整流程：

```text
[ Master下发spawn指令 ]
         |
    [Worker孵化Greenlet]
         |
   调用 on_start()  ----- (若报错/StopUser) -----> [用户终止，释放资源]
         | (成功)
         |
   进入 @task 循环  <-----> (执行任务，遵循 wait_time)
         |
    [测试结束 / 用户被停止]
         |
   调用 on_stop()   ----- (尽量执行，但不保证)
         |
    [Greenlet销毁]
```

### 💎 总结

-   **`on_start`** 是**准入卡**，失败即终止；用于初始化不能省略的上下文（如 Token）。
-   **`on_stop`** 是**善后者**，执行不保证；用于释放非核心资源（如归还账号）。
-   **不要**在钩子中编写重计算或长耗时逻辑（如等待 5 秒），它们会阻塞调度器，拖慢整个并发池的孵化速度。
-   在 `SequentialTaskSet` 中，`on_start` 非常适合用于**流程前置校验**（如检查购物车是否为空），`on_stop` 适合**流程中断上报**。

如果你需要我为你设计一个包含“失败重试机制”的 `on_start`（例如登录失败后间隔 1 秒重试 3 次），或者想探讨如何在分布式环境下保证 `on_stop` 的账号归还不丢失，告诉我具体场景，我继续为你写代码。

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[SequentialTaskSet实现顺序任务流]] | [[LoadTestShape基类与核心tick方法重写]]
