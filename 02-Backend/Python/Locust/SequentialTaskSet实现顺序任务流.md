---
tags: [locust, SequentialTaskSet]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: SequentialTaskSet实现顺序任务流.md
---
# SequentialTaskSet实现顺序任务流

`SequentialTaskSet` 是 Locust 专门用于构建**有严格先后顺序要求的工作流**的利器。它与普通 `TaskSet` 最核心的区别在于：**完全忽略 `@task` 的权重参数，严格按照类中方法的定义顺序依次执行**。

它是模拟“登录 -> 加购 -> 结算 -> 支付”这类**有状态、强依赖**业务场景的必选方案。

---

### 1. 核心执行模型：线性执行与自动循环

- **执行顺序**：按 `@task` 方法在类体内的**书写顺序**，从上到下依次执行。
- **自动循环**：当执行完最后一个 `@task` 方法后，若**未调用 `self.interrupt()`**，则任务集**不会退出**，而是会**跳回第一个 `@task` 方法**，形成无限循环。
- **权重忽略**：`@task(100)` 和 `@task(1)` 在 `SequentialTaskSet` 中效果完全一样，顺序决定一切。

```python
from locust import SequentialTaskSet, task, HttpUser

class OrderWorkflow(SequentialTaskSet):
    # ⚠️ 注意：方法定义顺序即执行顺序
    @task
    def step_1_login(self):
        print("1. 执行登录")
        resp = self.client.post("/login", json={"user": "test"})
        self.user.token = resp.json()["token"]  # 存储供后续步骤使用

    @task
    def step_2_add_cart(self):
        print("2. 加入购物车")
        self.client.post("/cart", json={"id": 123}, 
                         headers={"Authorization": f"Bearer {self.user.token}"})

    @task
    def step_3_checkout(self):
        print("3. 下单结算")
        self.client.post("/order", headers={"Authorization": f"Bearer {self.user.token}"})
        # 工作流完成，退出任务集，避免重复循环
        self.interrupt()

class WebUser(HttpUser):
    tasks = [OrderWorkflow]  # 每个用户启动后，固定执行一遍工作流
```
**运行效果**：每个用户会依次执行 `step_1` -> `step_2` -> `step_3`，然后因为调用了 `interrupt()` 而退出任务集（如果父级没有其他任务，该用户即终止）。

---

### 2. 关键转折：`self.interrupt()` 的精准控制

`interrupt()` 是 `SequentialTaskSet` 的“出口”。它的行为取决于调用时的上下文：

| 调用上下文 | 行为效果 |
| :--- | :--- |
| **在顶级 `HttpUser` 的 `tasks` 中** | 退出当前 `SequentialTaskSet`。若 `HttpUser` 中没有其他任务集，该 `User` 实例（协程）将**直接终止**（不会重新执行）。 |
| **在父级 `TaskSet` 内部嵌套调用时** | 退出当前 `SequentialTaskSet`，**返回到父级 `TaskSet`** 继续执行其后续任务或等待调度。 |

**实战建议**：一般情况下，在 `SequentialTaskSet` 的**最后一步**明确调用 `self.interrupt()`，是避免用户“死循环”空转的标准做法。如果你希望用户反复执行该工作流（例如反复下单），则**不调用** `interrupt()`，让它自动循环即可。

```python
class PaymentFlow(SequentialTaskSet):
    @task
    def pay(self):
        self.client.post("/pay")
        # 不调用 interrupt，则支付完成后会跳回第一个 @task，形成“反复支付”循环
```

---

### 3. 中途失败处理与优雅降级

工作流中某一步失败，后续步骤通常没有执行的意义。此时需要结合 **`catch_response`** 和 **`StopUser`** 或 **`self.interrupt()`** 进行中断。

#### A. 业务失败 -> 终止整个用户（推荐）
当遇到致命错误（如登录失败、库存为 0）时，`raise StopUser()` 直接销毁当前用户协程，避免浪费资源继续执行无效操作。

```python
class CheckoutFlow(SequentialTaskSet):
    @task
    def add_cart(self):
        with self.client.post("/cart", json={"id": 1}, catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("stock") <= 0:
                    resp.failure("库存不足")
                    # 库存不足，直接终止当前用户，不再继续执行后续步骤
                    raise StopUser()
                resp.success()
            else:
                resp.failure("加购失败")
                raise StopUser()

    @task
    def pay(self):
        # 只有加购成功才会执行到这里
        self.client.post("/pay")
        self.interrupt()  # 成功结束
```

#### B. 非致命失败 -> 提前结束工作流（返回父级）
如果某一步失败，但你希望用户**退出该工作流**，转而执行父级 `TaskSet` 中的其他任务，可以使用 `self.interrupt()`。

```python
class VipOnlyFlow(SequentialTaskSet):
    @task
    def check_vip(self):
        resp = self.client.get("/user/level")
        if resp.json().get("level") != "VIP":
            print("非VIP用户，跳过该工作流")
            self.interrupt()  # 立即退出当前任务集，返回父级任务集
            return
        print("VIP用户，继续执行")

    @task
    def vip_exclusive_offer(self):
        self.client.post("/vip/deal")
        self.interrupt()
```

---

### 4. 嵌套组合：顺序流在随机场景中的权重

`SequentialTaskSet` 也可以作为普通 `TaskSet` 的一个成员，放入 `HttpUser` 的 `tasks` 字典中，通过权重控制其被选中的概率。

```python
class BrowseTasks(TaskSet):
    @task
    def home(self): self.client.get("/")

class OrderFlow(SequentialTaskSet):
    @task
    def step1(self): self.client.post("/cart")
    @task
    def step2(self): 
        self.client.post("/pay")
        self.interrupt()  # 流程结束

class MixedUser(HttpUser):
    # 权重分配：浏览任务被选中的概率为 5，完整下单流程被选中的概率为 1
    tasks = {
        BrowseTasks: 5,   # 普通随机任务集
        OrderFlow: 1,     # 顺序任务集
    }
```

**执行机制**：当调度器随机选中 `OrderFlow` 时，该用户会**暂停其他所有任务**，进入顺序流执行。直到流内调用 `self.interrupt()` 返回后，才恢复正常的随机调度。

---

### 5. 数据上下文传递（跨步骤共享）

`SequentialTaskSet` 中的步骤共享数据，推荐存储在 **父级 `User` 实例**（`self.user`）中，而不是类变量，以确保协程级别的数据隔离。

```python
class DataDrivenFlow(SequentialTaskSet):
    @task
    def fetch_resource(self):
        resp = self.client.get("/resource/id")
        # 存储到父级 User 实例中
        self.user.resource_id = resp.json()["id"]

    @task
    def operate_resource(self):
        resource_id = self.user.resource_id  # 取回数据
        self.client.delete(f"/resource/{resource_id}")
        self.interrupt()
```

---

### 6. 常见误区与避坑指南

| 误区 | 现象 | 正确做法 |
| :--- | :--- | :--- |
| **以为权重能控制顺序流概率** | 在 `SequentialTaskSet` 内设置了 `@task(10)` 和 `@task(1)`，但发现执行次数一样多。 | 只在 `HttpUser` 的 `tasks` 字典中控制 `SequentialTaskSet` 的权重。内部的 `@task` 权重完全无效。 |
| **忘记调用 `interrupt()`** | 用户执行完流程后，又从第一步开始反复循环，导致统计数据的“失败率”随着无效重复请求飙升。 | 在流程最后一步明确调用 `self.interrupt()`。 |
| **在 `on_start` 中执行顺序流程** | 将全部工作流写在 `on_start` 中，导致统计无法区分各步骤，且无法利用 `wait_time`。 | `on_start` 只做登录等极简前置动作，核心工作流放在 `SequentialTaskSet` 的 `@task` 中。 |
| **中途报错未中断** | 加购失败后，后续的下单步骤依然执行，导致大量“空请求”拉低业务成功率。 | 结合 `raise StopUser()` 或 `self.interrupt()` 立即终止。 |

---

### 7. 调试技巧：查看执行轨迹

在本地调试时，可以在 `SequentialTaskSet` 中添加 `print` 或使用 `--loglevel DEBUG` 查看调度日志。

```python
class DebugFlow(SequentialTaskSet):
    @task
    def step_a(self):
        print(f"User {self.user.user_id} 正在执行 Step A")
        self.client.get("/a")

    @task
    def step_b(self):
        print(f"User {self.user.user_id} 正在执行 Step B")
        self.client.get("/b")
        self.interrupt()
```

---

### 💎 总结

-   **`SequentialTaskSet` 是工作流的骨架**：它保证了**确定性执行顺序**，是模拟真实业务强依赖链条的最佳实践。
-   **核心守则**：**必须**在逻辑终点调用 `self.interrupt()`（或 `raise StopUser()`），否则会无限循环。
-   **组合策略**：将其视为一个“原子化”的流程模块，通过 `HttpUser` 的 `tasks` 字典权重，与其他随机任务集混合，构建“大部分时间在浏览、偶尔走完整下单流程”的真实流量模型。

如果你已经熟练掌握了顺序流，下一步可以考虑将其与 **`LoadTestShape`** 结合，实现“上班高峰期流量涌入，自动触发大量下单工作流”的动态负载仿真。需要我展开这块内容吗？

## 🔗 关联笔记

[[_MOC-locust]] | [[LoadTestShape基类与核心tick方法重写]] | [[on_start与on_stop生命周期钩子方法]] | [[test_start与test_stop全局事件监听]]
