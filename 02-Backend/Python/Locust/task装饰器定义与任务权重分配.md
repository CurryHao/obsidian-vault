---
tags: [locust, task, 权重]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: @task装饰器定义与任务权重分配.md
---
# @task装饰器定义与任务权重分配

`@task` 装饰器是 Locust 中定义用户行为的**核心入口**。它标记了 `User` 类中哪些方法属于“待执行的任务”，并通过可选的权重参数，控制这些任务在单个用户内部被执行的**概率分布**。

---

### 1. 基础语法与默认行为

-   **无参数**：`@task` 表示该方法为任务，默认权重为 `1`。
-   **带参数**：`@task(weight)` 为该方法设置权重，权重值可以是任意正整数。

```python
from locust import HttpUser, task, between

class MyUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def index(self):
        """默认权重为 1"""
        self.client.get("/")

    @task(3)
    def about(self):
        """权重为 3，被执行的概率是 index 的 3 倍"""
        self.client.get("/about")

    @task(6)
    def contact(self):
        """权重为 6，被执行概率最高"""
        self.client.get("/contact")
```
**调度逻辑**：总权重 = 1 + 3 + 6 = 10。每次任务循环时，系统会按概率选择：
-   `index`: 10% 概率
-   `about`: 30% 概率
-   `contact`: 60% 概率

---

### 2. 底层权重分配机制（重要）

`@task` 的权重分配遵循 **“按比例随机抽样”** 原则，而非精确轮询。

-   当用户执行完一个任务并等待 `wait_time` 结束后，调度器会根据所有 `@task` 方法的权重，**构建一个加权随机池**，然后从中随机抽取一个任务作为下一个执行目标。
-   **关键特性**：这种分配是**概率性**的，而非严格交替。在短时间窗口内（如连续 10 次执行），实际分布可能偏离理论比例（例如 `@task(1)` 的接口可能会连续被执行 3 次）。只有在足够长的运行时间和大并发下，才会趋近于设定比例。

**如果希望任务严格交替执行或按特定顺序执行**，应使用 `SequentialTaskSet`（按代码顺序执行，忽略权重），或在 `@task` 方法内部手动控制流程。

---

### 3. 在 `TaskSet` 中使用 `@task`

`@task` 不仅可以在 `HttpUser` 子类中使用，也可以在 `TaskSet` 或 `SequentialTaskSet` 中使用，作用域仅限于该任务集内部。

```python
from locust import HttpUser, SequentialTaskSet, task

class CheckoutFlow(SequentialTaskSet):
    # SequentialTaskSet 会按声明顺序执行，@task 中的权重在这里无意义，但为了统一语法仍可保留
    @task
    def add_cart(self):
        self.client.post("/cart")

    @task
    def apply_coupon(self):
        self.client.post("/coupon")

    @task
    def pay(self):
        self.client.post("/pay")
        self.interrupt()  # 执行完支付后，退出该任务集

class WebsiteUser(HttpUser):
    # 在顶级用户中定义权重，控制访问不同 TaskSet 的概率
    @task(5)
    def browse(self):
        self.client.get("/")

    @task(1)
    def start_checkout(self):
        # 进入下单任务集
        self.execute(CheckoutFlow)
```

---

### 4. 动态生成任务（代码即配置）

利用 Python 的闭包和动态属性，可以在 `__init__` 方法中动态生成 `@task` 方法，非常适合压测大量相似接口。

```python
class DynamicUser(HttpUser):
    # 接口列表
    endpoints = ["/api/v1/user", "/api/v1/order", "/api/v1/product"]

    def __init__(self, environment):
        super().__init__(environment)
        # 循环动态创建 task 方法并绑定到实例
        for ep in self.endpoints:
            # 关键：使用闭包捕获 ep 变量，并设置不同的权重
            @task(weight=2)
            def dynamic_task(self, endpoint=ep):
                self.client.get(endpoint, name=endpoint)  # name 用于统计聚合
            # 将动态方法挂载到实例上（需要确保方法名唯一）
            setattr(self, f"task_{ep.replace('/','_')}", dynamic_task)
```

> **注意**：动态生成的 `@task` 方法名不能重复，否则后定义的方法会覆盖前者。

---

### 5. 结合 `@tag` 进行任务过滤

`@tag` 装饰器可以和 `@task` 组合使用，让你在命令行中按标签**筛选**或**排除**特定任务，无需修改代码。

```python
from locust import HttpUser, task, tag

class FilterableUser(HttpUser):
    @task(10)
    @tag("smoke", "critical")   # 同时标记为烟雾测试和关键路径
    def health(self):
        self.client.get("/health")

    @task(5)
    @tag("smoke")               # 仅标记为烟雾测试
    def ping(self):
        self.client.get("/ping")

    @task(1)
    @tag("slow")                # 标记为慢请求
    def heavy_report(self):
        self.client.get("/report")
```

**命令行过滤规则**：
```bash
# 只运行带有 "smoke" 或 "critical" 标签的任务（交集）
locust -f demo.py --tags smoke critical

# 排除带有 "slow" 标签的任务（其他任务都运行）
locust -f demo.py --exclude-tags slow

# 组合使用：运行带有 smoke 标签但不包含 slow 标签的任务
locust -f demo.py --tags smoke --exclude-tags slow
```

---

### 6. 高级技巧：使用 `tasks` 属性替代 `@task`

除了使用装饰器，你还可以直接赋值一个 `tasks` 列表或字典来定义任务，这在动态构建任务集时非常有用。

```python
class MyUser(HttpUser):
    def browse(self):
        self.client.get("/")

    def search(self):
        self.client.get("/search")

    # 列表：权重均等（权重均为 1）
    tasks = [browse, search]

    # 字典：精确控制权重
    # tasks = {browse: 3, search: 1}
```

> **注意**：`tasks` 属性和 `@task` 装饰器**不能同时使用**。当两者都存在时，`tasks` 属性会覆盖 `@task` 的声明。

---

### 7. 常见陷阱与最佳实践

| 陷阱 | 后果 | 修正方案 |
| :--- | :--- | :--- |
| **所有任务的 `wait_time` 完全一致** | 无法区分高频接口和低频接口，流量模型失真 | 在不同 `User` 类或 `TaskSet` 中设置不同的 `wait_time`。 |
| **权重相差巨大（如 1 vs 1000）** | 低权重任务可能长时间不被执行，导致压测覆盖不完整 | 若低权重任务必须被执行，考虑单独创建一个独立的 `User` 类，并设置低类权重（`weight`），而非在任务权重中极端化。 |
| **在 `@task` 中编写同步阻塞代码**（如 `time.sleep(5)`） | 会阻塞整个 Greenlet 调度，导致其他用户无法切换 | 使用 `wait_time` 管理思考时间，而非在函数内使用 `sleep`。若需在任务内等待，使用 `gevent.sleep()`。 |
| **`@task` 方法中未设置 `name` 参数** | 当 URL 包含动态参数（如 `/order/123`）时，统计图表会被海量独立条目淹没 | 始终使用 `self.client.get(f"/order/{id}", name="/order/[id]")` 进行聚合。 |
| **权重未生效（执行频率异常）** | 可能误用了 `SequentialTaskSet`（忽略权重）或 `tasks` 属性与装饰器冲突 | 确认使用的是普通 `TaskSet`；检查是否混用了 `tasks` 属性和 `@task`。 |

---

### 💎 总结

-   `@task` 控制的是 **“单一用户内部各操作的频次比例”**。
-   `@task(weight)` 通过 **加权随机抽样** 分配执行概率，是概率模型而非精确轮询。
-   配合 `@tag` 可以实现**多场景灵活切换**，无需维护多份脚本。
-   当需要严格顺序时，优先使用 `SequentialTaskSet`；当需要复杂频次控制时，结合类权重（`weight`）与任务权重（`@task`）实现**双层调度模型**。

如果你希望我帮你设计一个具体的混合场景（例如：80% 的请求是浏览，15% 是加入购物车，5% 是支付，且支付必须在加购之后），我们可以基于 `SequentialTaskSet` 和权重分配，写一个完整的可运行示例。

## 🔗 关联笔记

[[_MOC-locust]] | [[SequentialTaskSet实现顺序任务流]] | [[HttpUser基类与Web请求能力绑定]] | [[LoadTestShape基类与核心tick方法重写]]
