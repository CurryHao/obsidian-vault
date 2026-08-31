---
tags: [locust, User, 配置]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: User类属性定义与作用域.md
---
# User类属性定义与作用域

在 Locust 中，`User` 类（及其子类 `HttpUser`）的属性定义不仅是**配置参数**，更是**用户行为模型的蓝图**。理解 `host`、`min_wait`/`max_wait`（以及现代版本的 `wait_time`）的定义和作用域，是设计逼真、可控压测场景的基础。

**请注意一个重要的版本变更**：在 Locust 1.x 版本之后，`min_wait` 和 `max_wait` 已被**弃用**，取而代之的是更灵活的 `wait_time` 属性。不过，为了让你理解历史代码和现代最佳实践，我会把两者都讲清楚。

---

### 1. `host` 属性：目标服务的“根地址”

-   **定义**：指定压测请求发送的目标基础 URL（协议 + 域名/IP + 端口）。
-   **作用域**：**类级别（Class-level）**。它属于该 `User` 类本身，该类的所有实例（协程）都会使用这个基础地址。

```python
from locust import HttpUser, task

class MyUser(HttpUser):
    # 类属性：硬编码的根地址
    host = "https://api.staging.example.com"

    @task
    def get_data(self):
        # 实际请求 URL 为：https://api.staging.example.com/data
        self.client.get("/data")
```
## 🔄 `host` 的优先级与覆写规则（重要）
`host` 的实际生效顺序遵循 **“宽泛配置，精确覆写”** 原则，从低到高为：
1.  **`User` 类中定义的 `host`**（最低优先级）。
2.  **命令行参数 `--host`**（中间优先级，会覆盖类属性）。
3.  **`self.client.get(url)` 中的绝对 URL**（最高优先级，若写了完整路径，则忽略上述所有）。

```python
# 命令行启动：locust -f demo.py --host=https://prod.example.com
# 此时，虽然类里写的是 staging，但实际访问的是 prod
```

> **实战建议**：**永远不要**在代码中硬编码 `host`。将其放在命令行参数 `--host` 或 `locust.conf` 配置文件中，这样你的脚本可以在开发、预发布、生产环境间无缝切换。

---

### 2. `wait_time` 属性（现代标准）：思考时间的“调度器”

`wait_time` 控制每个用户在执行完一个 `@task` 任务后，**等待多久**再执行下一个任务。这模拟了真实用户在页面间的浏览停顿。

-   **定义**：可以是一个固定的数值（秒），也可以是一个可调用对象（函数/方法）。
-   **作用域**：**实例级别（Instance-level）**，但定义在类体中。每个用户实例在执行完任务后，会独立调用 `wait_time` 来决定自己的下一次等待时长。

#### 常用的 `wait_time` 内置函数：

| 函数 | 行为 | 使用场景 |
| :--- | :--- | :--- |
| `between(min, max)` | 在 `min` 和 `max` 秒之间**随机均匀**等待。 | 模拟普通用户无规律的浏览节奏（最常用）。 |
| `constant(seconds)` | 固定等待 `seconds` 秒。 | 模拟机器定时轮询或稳定后台任务。 |
| `constant_pacing(seconds)` | 确保**两次任务开始的时间间隔**至少为 `seconds` 秒（若任务执行耗时过长，则不等待）。 | 模拟固定的业务吞吐量（如每分钟固定处理 10 单）。 |
| `constant_throughput(rate)` | 控制每秒执行的任务数（吞吐量）。 | 精确控制 RPS，避免压垮脆弱的下游。 |

```python
from locust import HttpUser, task, between, constant, constant_pacing

class NormalUser(HttpUser):
    # 等待 1~3 秒，模拟真人浏览
    wait_time = between(1, 3)

class APIGatewayUser(HttpUser):
    # 固定等待 0.5 秒，模拟高频自动调用
    wait_time = constant(0.5)

class OrderUser(HttpUser):
    # 保证每秒最多发起 2 笔订单
    wait_time = constant_throughput(2)
```

---

### 3. 历史遗留：`min_wait` 与 `max_wait`（已弃用，但需了解）

在 Locust 0.x 及 1.x 早期版本中，使用 `min_wait` 和 `max_wait` 定义等待区间，其效果等同于 `between(min_wait, max_wait)`。

-   **定义**：类属性，单位为**毫秒**（注意不是秒）。
-   **作用域**：类级别，所有实例共享这个区间定义。

```python
# ⚠️ 旧版写法（不推荐，仅在维护老旧脚本时识别）
class OldUser(HttpUser):
    min_wait = 1000  # 最小等待 1 秒（1000毫秒）
    max_wait = 5000  # 最大等待 5 秒（5000毫秒）
```

**现代替代方案**：
```python
# ✅ 新版推荐写法（语义更清晰，单位统一为秒）
class NewUser(HttpUser):
    wait_time = between(1, 5)
```

---

### 4. 作用域与继承深度解析（核心）

理解属性如何被子类继承和覆写，是构建复杂压测基类的关键。

#### A. 类级别覆盖（子类独立）
如果父类定义了 `wait_time`，子类可以**完全覆盖**它，互不影响。

```python
class BaseUser(HttpUser):
    wait_time = between(5, 10)  # 父类等待 5~10 秒

class FastUser(BaseUser):
    wait_time = constant(0.5)   # 子类只等 0.5 秒，完全覆盖父类
```

#### B. 动态 `wait_time`（高级用法）
`wait_time` 可以是一个函数，接收 `self` 参数，实现根据当前用户状态动态调整等待时间。

```python
import random

class SmartUser(HttpUser):
    def dynamic_wait(self):
        # 如果用户是 VIP，等待时间缩短
        if getattr(self, 'is_vip', False):
            return random.uniform(0.5, 1.0)
        else:
            return random.uniform(3, 8)

    wait_time = dynamic_wait  # 绑定动态方法
```

#### C. 嵌套 TaskSet 的作用域继承
当使用 `SequentialTaskSet` 或嵌套任务时，子任务集**默认继承**父 `User` 类的 `wait_time`。但你也可以在 `TaskSet` 内部重新定义 `wait_time`，覆盖父级的节奏。

```python
from locust import SequentialTaskSet, task

class OrderFlow(SequentialTaskSet):
    # 重写等待时间：在下单流程中，操作间隔缩短
    wait_time = constant(0.2)

    @task
    def add_cart(self):
        self.client.post("/cart")

    @task
    def pay(self):
        self.client.post("/pay")
```

---

### 💎 核心总结与最佳实践

1.  **`host` 留空，由外部注入**：脚本中**永远不要**硬编码 `host`，依赖命令行 `--host` 或配置文件。
2.  **淘汰 `min_wait`/`max_wait`**：新代码一律使用 `wait_time = between(...)`，单位秒，更直观且功能更强。
3.  **区分并发与吞吐量**：
    -   提高 `users`（并发数）不代表提高 RPS，`wait_time` 才是限制单用户请求频率的关键。
    -   若需要恒定 RPS，使用 `constant_pacing` 或 `constant_throughput`。
4.  **利用作用域隔离场景**：为“浏览用户”、“下单用户”、“后台管理员”分别定义不同的 `wait_time`，模拟真实业务比例。

如果你想让 `wait_time` 根据服务器的响应时间**自适应调整**（例如响应慢了就多等一会），或者想探索 `constant_throughput` 与 `between` 结合使用的陷阱，我们可以继续深入这些高级用法。你有具体想模拟的业务流量模型吗？

## 🔗 关联笔记

[[_MOC-locust]] | [[SequentialTaskSet实现顺序任务流]] | [[继承BaseClient实现WebSocket协议压测]] | [[HttpUser基类与Web请求能力绑定]]
