---
tags: [locust, LoadShape]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: LoadTestShape基类与核心tick方法重写.md
---
# LoadTestShape基类与核心tick方法重写

## LoadTestShape 基类与 `tick()` 方法深度解析

在 Locust 中，**负载形状（Load Shape）** 是模拟真实生产流量时间模式的关键机制。通过继承 `LoadTestShape` 并重写 `tick()` 方法，你可以**动态控制并发用户数（user count）和启动速率（spawn rate）**，实现阶梯加压、脉冲流量、日周期曲线、秒杀突发等复杂场景。

---

### 1. 核心概念

- **`LoadTestShape`** 位于 `locust` 模块，是一个抽象基类。
- **`tick()`** 是唯一需要重写的方法，**每秒被 Locust 调用一次**（在 headless 模式下更精确）。
- **返回值**：`tuple[int, int] | None`  
  - `(user_count, spawn_rate)`：期望的目标用户数和每秒启动速率。  
  - `None`：表示停止测试（相当于 `--run-time` 结束）。
- **调用时机**：仅在 **`--headless`** 模式下生效（Web UI 模式下形状控制无效，因为用户数由手动输入控制）。
- **与分布式兼容**：Master 节点运行形状逻辑，Worker 节点被动执行。

---

### 2. `tick()` 方法签名与上下文

```python
from locust import LoadTestShape

class MyShape(LoadTestShape):
    def tick(self) -> tuple[int, int] | None:
        """
        :return: (user_count, spawn_rate)
                 user_count: 期望达到的并发用户总数
                 spawn_rate: 每秒启动的用户数（达到目标后自动降为维持）
                 返回 None 则优雅停止测试
        """
        # 获取当前运行时间（秒）
        run_time = self.get_run_time()
        # 可访问 self.runner 获取当前状态（仅在非分布式模式或 Master 上有效）
        # current_users = self.runner.user_count if self.runner else 0

        # 自定义逻辑 ...
        return 100, 10
```
**关键属性**：
- `self.get_run_time()` → 从测试开始到现在的秒数（浮点数）。
- `self.runner` → 指向 `LocalRunner` 或 `MasterRunner`，可获取 `user_count`、`stats` 等信息（但在分布式 Worker 上为 `None`，建议仅在 Master 上使用）。

---

### 3. 经典负载形状实现

#### 3.1 阶梯式加压（Step Load）

```python
class StepLoadShape(LoadTestShape):
    step_time = 60          # 每阶段持续60秒
    step_users = 50         # 每阶段增加50用户
    max_users = 500         # 最大用户数
    spawn_rate = 10         # 启动速率

    def tick(self):
        run_time = self.get_run_time()
        # 计算当前阶段序号
        current_step = int(run_time // self.step_time) + 1
        user_count = min(current_step * self.step_users, self.max_users)
        if user_count >= self.max_users and run_time > self.step_time * (self.max_users // self.step_users + 1):
            # 达到最大后维持一段时间，然后停止
            return None
        return user_count, self.spawn_rate
```

#### 3.2 正弦波浪（模拟周期性波动）

```python
import math

class WaveShape(LoadTestShape):
    base_users = 100
    amplitude = 200
    period = 300           # 周期秒数（5分钟）

    def tick(self):
        run_time = self.get_run_time()
        # 正弦波：base + amplitude * sin(2π * t / period)
        user_count = self.base_users + self.amplitude * math.sin(2 * math.pi * run_time / self.period)
        user_count = max(10, int(user_count))
        spawn_rate = 20
        return user_count, spawn_rate
```

#### 3.3 日周期（24小时真实流量模式）

参考前面例子中的 `DiurnalLoadShape`，使用时间戳插值，支持任意分段线性曲线。

#### 3.4 突发秒杀（瞬时峰值）

```python
class SpikeShape(LoadTestShape):
    def tick(self):
        t = self.get_run_time()
        if t < 60:               # 前60秒预热，100用户
            return 100, 10
        elif t < 120:            # 60~120秒爬升到10000
            progress = (t - 60) / 60
            return int(100 + 9900 * progress), 500
        elif t < 180:            # 120~180秒维持10000
            return 10000, 0
        elif t < 240:            # 180~240秒快速下降
            progress = (t - 180) / 60
            return int(10000 - 9900 * progress), 500
        else:
            return None          # 结束
```

---

### 4. 高级技巧与注意事项

#### 4.1 平滑过渡与防止抖动
- 返回的 `spawn_rate` 应当与当前用户数和目标数的差距相匹配，避免启动速率过高导致系统瞬间过载。
- 可以使用 **PID 控制** 或 **指数平滑** 来动态调整速率，例如：
```python
  diff = target_users - current_users
  spawn_rate = min(abs(diff) / 10, 100) if diff > 0 else 0
```

#### 4.2 结合外部数据源（如配置文件、时间表）
```python
import json

class ConfigDrivenShape(LoadTestShape):
    def __init__(self):
        super().__init__()
        with open("load_profile.json") as f:
            self.schedule = json.load(f)   # [{"time": 0, "users": 100}, ...]

    def tick(self):
        t = self.get_run_time()
        # 线性插值遍历 self.schedule
        # ...
```

#### 4.3 分布式模式注意事项
- **只有 Master 运行 `tick()`**，Worker 接收来自 Master 的启动/停止指令。
- 在 `tick()` 中访问 `self.runner.user_count` 在分布式模式下**会得到 Master 上的当前总用户数**，但需注意轮询延迟（约 1 秒）。
- 如需在 Worker 上执行自定义逻辑（如基于本地负载调整），建议通过 `@events.init.add_listener` 注册事件，但形状控制仍应由 Master 统一调度。
#### 4.4 测试停止条件
- 返回 `None` 时，Locust 会**优雅停止**（等待所有请求完成），触发 `test_stop` 事件。
- 也可以结合 `--run-time` 同时使用，但 `tick()` 返回 `None` 的优先级更高。
#### 4.5 与 Web UI 的兼容性
- 在 Web UI 模式下，`LoadTestShape` 会被**忽略**，用户数由界面滑块控制。
- 若希望保留形状控制但提供 UI 查看实时指标，可启动 `--web` 但用户数仍由形状决定（需使用 `--headless` 配合 `--web-port`，但官方不推荐，建议仅在 CI/CD 中使用 headless）。
---
### 5. 执行与调试
```bash
# 基本执行（使用默认形状类，需在文件中定义）
locust -f my_shape_file.py --headless

# 指定某个形状类（文件中有多个）
locust -f my_shape_file.py --headless -S WaveShape

# 查看日志输出（建议设置 --loglevel DEBUG 观察 tick 调用）
locust -f my_shape_file.py --headless --loglevel DEBUG

# 结合 CSV 输出记录用户数变化
locust -f my_shape_file.py --headless --csv=shape_result
```
---
### 6. 常见问题与调优

| 问题                     | 原因                                  | 解决方案                                           |
| ---------------------- | ----------------------------------- | ---------------------------------------------- |
| 实际用户数与 `tick()` 返回值差距大 | `spawn_rate` 太大或太小，且网络/服务器响应慢导致启动延迟 | 减小 `spawn_rate`，增加预热阶段，允许系统逐步达到目标              |
| `tick()` 不执行           | 未使用 `--headless` 模式                 | 必须添加 `--headless` 参数                           |
| 分布式 Worker 数量不足        | 单个 Worker 受 GIL 限制，无法支撑高并发          | 增加 Worker 节点，或使用 `--processes` 多进程（仅限本地）       |
| 形状曲线突变导致大量错误           | 陡峭上升触发目标系统限流或熔断                     | 改用更平滑的曲线，增加 `spawn_rate` 的 PID 调节              |
| 测试提前退出                 | `tick()` 返回 `None` 条件过早满足           | 检查时间计算逻辑，增加日志打印调试                              |
| `self.runner` 为 `None` | 在 Worker 节点或非 Runner 上下文中访问         | 仅在 Master 或单机模式下使用，或通过 `environment.runner` 访问 |

---
### 7. 进阶：结合 Prometheus 实时观测形状

可以将 `tick()` 中计算的目标用户数作为自定义指标暴露：

```python
from prometheus_client import Gauge

target_users_gauge = Gauge('locust_shape_target_users', 'Target users from shape')

class MyShape(LoadTestShape):
    def tick(self):
        target, rate = self._calculate()
        target_users_gauge.set(target)   # 推送到 Prometheus
        return target, rate
```

这样在 Grafana 中可以叠加显示**预期负载**与**实际负载**的对比，方便验证形状是否正确执行。

---

### 8. 总结

- `LoadTestShape` 是 Locust 实现**复杂负载模型**的核心工具，适合模拟真实生产流量时间模式。
- 重写 `tick()` 时需注意**返回值的合理性**、**平滑过渡**以及**分布式环境下的行为差异**。
- 结合外部数据源或算法（如 PID、机器学习预测）可以实现**自适应负载**，是容量规划的高级实践。

如果你有特定的业务流量模式（如电商大促、直播互动、物联网设备上报）或需要更复杂的形状控制（如基于实时响应时间调整并发），欢迎进一步讨论，我可以提供针对性的设计示例。

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[on_start与on_stop生命周期钩子方法]] | [[test_start与test_stop全局事件监听]]
