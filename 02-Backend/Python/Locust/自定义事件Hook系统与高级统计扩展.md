---
tags: [locust, 事件, 钩子, 扩展]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
---

# 自定义事件Hook与高级统计扩展

Locust 提供了完整的事件系统，让你能在 7 个生命周期阶段**插入自定义逻辑**，实现自定义指标上报、异常分类、第三方集成钩子等高级功能。

---

## 📌 一句话总结

通过 `events` 模块监听 Worker/Master 的 7 个关键事件，可以将请求成功/失败零侵入地从标准统计管道拆分到任意自定义管道。

---

## 🎯 7 个核心事件

| 事件 | 触发阶段 | 用途 |
|------|----------|------|
| `events.init` | 启动阶段 | 加载数据、初始化连接池 |
| `events.test_start` | 测试开始 | 输出日志、初始化外部服务的指示 |
| `events.test_stop` | 测试结束 | 发送报告、清理资源 |
| `events.request` | **每次 HTTP 请求** | 自定义统计、按 status 统计计数 |
| `events.spawning_complete` | Worker 孵化完成 | 自动启动、触发跨 Worker 通知 |
| `events.worker_report` | Worker 上报 Master | 在 Master 端接收自定义数据 |
| `events.quitting` | 退出销毁 | 是否优雅退出、日志归并告警 |

---

## 🚀 最常用：自定义统计管道

```python
from locust import HttpUser, task, events
from locust.stats import StatsEntry

# 1. 创建自定义指标
@events.init.add_listener
def setup_custom_metrics(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        return  # 不在 Worker 上创建
    environment.stats.custom_metric = StatsEntry(
        name="custom_success",
        method="custom",
        environment=environment
    )
    tree = environment.stats.total
    tree.reset()  # 即时可用

# 2. 在请求后捕获数据
class MyUser(HttpUser):
    @task
    def endpoint(self):
        with self.client.get("/api/data", catch_response=True) as resp:
            if resp.status_code == 200:
                # 额外上报到自定义管道
                self.environment.stats.custom_metric.log(
                    success=True,
                    request_type="custom",
                    name="data_api",
                    response_time=resp.elapsed.total_seconds(),
                    response_length=len(resp.content)
                )
            else:
                resp.fail("business error")
```

---

## 💡 应用场景：向 Prometheus 推送实时指标

```python
import prometheus_client
from locust import events

# 全局注册：请求计数器
REQUEST_COUNT = prometheus_client.Counter(
    "locust_requests", "total requests", ["status", "name"]
)

@events.request.add_listener
def on_request(request_type, name, response_time,
              response_length, exception, context, **kwargs):
    status = "fail" if exception else "success"
    REQUEST_COUNT.labels(status=status, name=name).inc()
```

这样你不仅能看 Locust 内置的 P50/P95，还能在 Prometheus 中按小时自动聚合。

---

## ⚠️ 常见坑点

1. **事件注册顺序**：必须在 `import` 模块级别注册（不在 `on_start` 中）
2. **Worker 隔离**：每个 Worker 有独立的事件循环，你的监听逻辑必须考虑 Worker 冲突
3. **统计聚合**：自定义指标在分布式模式中**不会自动在整个 Master 上汇总**，需要你手动在 `worker_report` 事件中聚合
4. **请求阻塞风险**：尽量在 `events.handler` 中的回调逻辑精简钟，避免调用阻塞操作
5. **请求失败处理**：`events.request` 在异常时 `exception` 参数非 None，必须检查

---

## 💎 实战场景使用三种模式

1. **声明式过滤**：给自愈接口打标记区分进程（SaaS 补偿策略）
2. **白名单发送远程统计**：将结果推送到 Datadog/Kafka/TCP socket
3. **动态加载 Worker 配置**：通过 `worker_register` 事件下发动态任务集

---

## 🔗 关联笔记

[[_MOC-locust]] | [[自定义统计数据聚合与事件上报扩展]] | [[test_start与test_stop全局事件监听]] | [[请求成功与失败回调]]