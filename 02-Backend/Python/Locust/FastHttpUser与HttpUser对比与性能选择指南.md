---
tags: [locust, FastHttpUser, 性能, HTTP]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
---

# FastHttpUser与HttpUser对比与选择指南

选择 `HttpUser` 还是 `FastHttpUser` 是 Locust 压测脚本中的第一个性能分水岭。同一台机器上，`FastHttpUser` 吞吐量可达 `HttpUser` 的**数十倍**，且 CPU 占用更低——这是生产级压测必须掌握的关键抉择。

---

## 📌 一句话总结

`HttpUser` 用 Python 的 `requests.Session`，适合调试和低负载；`FastHttpUser` 用 C 编写的 `geventhttpclient`，适合任何真实负载压测。

---

## 🎯 核心差异对比

| 维度 | `HttpUser` | `FastHttpUser` |
|------|-----------|----------------|
| 底层库 | `requests`（纯 Python） | `geventhttpclient`（C 编写 + gevent 协程） |
| 单 Worker RPS 上限 | ~1,000–2,000 | ~5,000–15,000+ |
| Cookie 处理 | 自动继承 Session.cookies | 默认自动处理 |
| 连接池 | `requests` 适配器管理 | 高性能连接池，复用更高效 |
| CPU 占用 | 较高（Python 对象开销） | 较低（C 高效解析 HTTP） |
| 与 `requests` API 兼容性 | 完全兼容 | 大体兼容，少数差异 |

---

## 🚀 迁移：一行代码

```python
# 原来
from locust import HttpUser

class MyUser(HttpUser):
    @task
    def my_task(self):
        self.client.get("/api/test")

# 改为
from locust import FastHttpUser

class MyUser(FastHttpUser):
    @task
    def my_task(self):
        self.client.get("/api/test")
```

`self.client` 的 API 调用完全一样：`.get()`、`.post()`、`.put()`、`.delete()` 都可用。

---

## ⚠️ 常见坑点

1. **错误类型差异**：`FastHttpUser` 抛出 `geventhttpclient` 异常，不是 `requests.ConnectionError`。如果你在 `catch_response=True` 中做异常分类，需要适配。
2. **SSL 证书差异**：`FastHttpUser` 默认不信任自签名证书，需显式设置 `ssl=False` 参数。
3. **依赖冲突**：不能同时 `from locust import HttpUser, FastHttpUser` 在同一文件中混用。
4. **连接数限制**：HttpUser 默认连接池很小，高并发下容易耗尽；FastHttpUser 连接池默认更大。
5. **Cookie 手动管理**：虽然自动处理，但跨 User 实例间不共享——需要手动在 `on_start` 中传递 Token。

---

## 💡 选择建议

- **开发/调试/demo** → `HttpUser`（便于加断点、日志、与 IDE 联动）
- **CI 轻量测试** → `HttpUser`
- **生产级负载压测** → **`FastHttpUser`（无一例外）**
- **需要第三方库（如 `requests-oauthlib`）** → `HttpUser`（除非你愿意手写 OAuth 逻辑）

---

## 🔗 关联笔记

[[_MOC-locust]] | [[HttpUser基类与Web请求能力绑定]] | [[连接池复用与Keep-Alive长连接管理]] | [[gevent协程模型与异步并发优势]]