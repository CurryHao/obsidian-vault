---
tags: [locust, weight, 混合压测]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 负载权重（weight）与多用户类型混合策略.md
---
# 负载权重（weight）与多用户类型混合策略

在 Locust 中，**`weight`（类权重）** 与 **`@task` 装饰器里的权重**共同构成了一个**双层概率调度模型**。理解二者的区别与协作机制，是模拟真实世界复杂流量比例（如 80% 浏览用户 + 15% 加购用户 + 5% 支付用户）的关键。

---

### 1. 核心概念：`weight` 是“用户类型”的权重

-   **定义**：`weight` 是 `User` 类（如 `HttpUser`）的**类属性**，用于控制**不同用户类型之间**的并发数量比例。
-   **作用域**：它决定了在总的并发用户池中，各类用户被创建的数量占比。
-   **默认值**：若未指定，所有 `User` 类的 `weight` 默认为 `1`。

```python
from locust import HttpUser, task, between

class BrowsingUser(HttpUser):
    # 权重 8：代表每孵化 10 个用户，大约 8 个会是浏览用户
    weight = 8
    wait_time = between(1, 5)

    @task
    def view_product(self):
        self.client.get("/product")

class CartUser(HttpUser):
    # 权重 1.5：支持浮点数，Locust 会按比例处理
    weight = 1.5
    wait_time = between(2, 4)

    @task
    def add_to_cart(self):
        self.client.post("/cart", json={"id": 1})

class PaymentUser(HttpUser):
    # 权重 0.5：占比 5%
    weight = 0.5
    wait_time = constant(3)

    @task
    def checkout(self):
        self.client.post("/order")
```
**实际孵化比例**：总权重 = 8 + 1.5 + 0.5 = 10。因此，最终的并发比例约为 **BrowsingUser : CartUser : PaymentUser = 80% : 15% : 5%**。

---

### 2. 关键区别：类权重 (`weight`) vs. 任务权重 (`@task`)

这是 Locust 新手最容易混淆的地方，请务必分清：

| 维度 | **类权重 (`weight`)** | **任务权重 (`@task(weight)`)** |
| :--- | :--- | :--- |
| **控制对象** | 控制 **“创建多少个用户实例”** | 控制 **“一个用户实例内部，各任务的执行次数比例”** |
| **作用层级** | **类与类之间**（横向分配） | **方法与方法之间**（纵向分配） |
| **典型场景** | 模拟不同角色（游客、会员、管理员）的混合访问 | 模拟同一角色下的不同操作（浏览、搜索、下单） |
| **数学逻辑** | 孵化时按权重随机选择要实例化的 `User` 类 | 任务循环时按权重随机选择要执行的 `@task` 方法 |

**示例**：即使 `PaymentUser` 的类权重只有 0.5（数量少），但该类内部的 `@task(10)` 任务依然会高频执行，导致其单用户 RPS 极高。类权重管**“人数”**，任务权重管**“频次”**，二者相乘才决定某个接口的总流量。

---

### 3. 底层调度机制（重要）

Locust 的孵化器（`Runner`）在启动或动态增加用户时，会执行以下逻辑：

1.  收集所有非抽象（`abstract=False`）的 `User` 子类。
2.  读取各自的 `weight` 值，构建一个**加权随机池**。
3.  每创建一个新用户（Greenlet），就从该池中按权重**随机抽取**一个类进行实例化。

**注意：概率性，非精确配额**。权重分配的是**概率**而非精确数量。例如，`weight=8` 和 `weight=2`，并发数为 100 时，结果大概率接近 80:20，但**不保证绝对精确**，尤其在小并发数（如 10 个用户）下，可能出现 9:1 或 7:3 的偏差。这是由随机抽样算法决定的。

---

### 4. 混合策略的高级实战

#### A. 用户类型差异化（不同 `wait_time`）
不同类型的用户应有不同的操作节奏。结合 `weight` 和 `wait_time`，可以模拟出极具真实感的流量：

```python
class BotUser(HttpUser):
    """模拟高频API爬虫"""
    weight = 2
    wait_time = constant(0.1)  # 100ms间隔，极其高频

class HumanUser(HttpUser):
    """模拟真人网页浏览"""
    weight = 8
    wait_time = between(3, 8)  # 3~8秒思考，低频
```

此时，虽然 `HumanUser` 人数多，但由于 `wait_time` 长，`BotUser` 可能贡献了系统 60% 以上的 RPS。

#### B. 动态调整权重（通过环境变量）
在 CI/CD 中，你可能想动态调整场景比例，无需修改代码：

```python
import os

class ScenarioA(HttpUser):
    # 通过环境变量注入权重，默认 1
    weight = int(os.getenv("WEIGHT_A", 1))
    
class ScenarioB(HttpUser):
    weight = int(os.getenv("WEIGHT_B", 1))
```

启动时：`WEIGHT_A=10 WEIGHT_B=1 locust -f ...`

#### C. 抽象基类（`abstract = True`）
如果你的 `User` 类仅用于被继承，不希望它被实际孵化，请设置 `abstract = True`：

```python
class BaseUser(HttpUser):
    abstract = True  # 此类不会被分配权重，也不会被创建实例
    # 公共方法...

class RealUser1(BaseUser):
    weight = 5
    # ...
```

#### D. 运行时选择器（`--class-picker`）
当脚本中包含多个 `User` 类时，可以使用 `--class-picker` 参数。启动 Web 界面后，你可以手动勾选要运行哪些类，甚至动态调整它们的权重，无需重启进程。

```bash
locust -f my_file.py --class-picker
```

---

### 5. 分布式下的权重行为

在 Master-Worker 模式下，权重逻辑由 **Master 计算，Worker 执行**：

1.  Master 根据总目标用户数（`-u`）和各类 `weight`，计算出每个 Worker 应孵化的各类用户数量（`spawn_count`）。
2.  Master 将“用户类清单及配额”下发给各个 Worker。
3.  每个 Worker 独立在其本地进行加权随机孵化。

**因此，权重逻辑在分布式下依然精确有效，总用户数的分配是全局协调的。**

---

### 6. 性能陷阱与纠正建议

| 陷阱 | 现象 | 正确策略 |
| :--- | :--- | :--- |
| **轻量类权重过高** | `wait_time=0` 的用户类权重占 1%，却打死了服务器 | 权重仅控制人数，不控制 QPS。务必结合 `constant_throughput` 或 `wait_time` 限制单用户频率。 |
| **希望精确比例** | 多次运行结果波动较大 | 若需精确数量，在 `on_start` 中按 `self.user_id` 取模决定行为，而非依赖 `weight`。 |
| **继承覆写混乱** | 子类未定义 `weight`，意外继承了父类的 `weight` | 若父类有 `weight`，子类默认继承。若希望子类独立，必须显式 `weight = xxx`。 |

---

### 💎 总结

-   **`weight` 解决“有多少人”**，是类之间的概率分配器。
-   **`@task` 解决“每个人做什么”**，是方法内部的执行调度器。
-   二者结合，配合 `wait_time`，就能构建出 **“不同角色、不同频率、不同操作路径”** 的立体压测模型。

如果你需要我帮你设计一个包含“未登录游客”、“登录会员”、“后台管理员”三种角色的混合场景，并精确控制它们的 RPS 比例，可以告诉我具体业务比例，我直接给你生成可运行的代码模板。

## 🔗 关联笔记

[[_MOC-locust]] | [[task装饰器定义与任务权重分配]] | [[Master-Worker架构通信机制与零MQ基础]] | [[HttpUser基类与Web请求能力绑定]]
