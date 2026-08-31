---
tags: [locust, 数据驱动, 参数化, CSV]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
---

# 测试数据参数化与CSV驱动真实负载

在真实压测场景中，每个虚拟用户通常需要**唯一的数据**——不同的用户名/密码、不同的商品 ID、不同的搜索关键词。将测试数据从脚本中抽离，用 CSV/JSON 驱动，是构建可靠压测套装的必要条件。

---

## 📌 一句话总结

用 Python 的 `csv` 或 `json` 模块在 `on_start` 中加载数据，利用 `queue.Queue` 在多用户间循环分发，避免数据冲突。

---

## 🎯 核心模式：Queue 数据分发

```python
import csv
import queue
from locust import HttpUser, task, between

# 在模块级别加载数据（只执行一次）
USER_CREDENTIALS = []

with open("users.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        USER_CREDENTIALS.append((row["username"], row["password"]))

class LoginUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # 每个用户启动时从队列中取值
        username, password = self.environment.runner.user_data_queue.get()
        self.username = username
        self.password = password

    @task
    def do_login(self):
        self.client.post("/login", json={
            "user": self.username,
            "pass": self.password
        })

# 在 locustfile 中配置队列（通过 init 事件）
from locust import events

@events.init.add_listener
def on_init(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        return  # 只在 Worker 上加载
    # 预创建队列
    q = queue.Queue()
    for cred in USER_CREDENTIALS:
        q.put(cred)
    environment.USER_DATA_QUEUE = q
```

---

## 💡 更简单的方法：自定义 `__init__`

```python
import csv
import itertools

users_data = list(csv.DictReader(open("users.csv")))
# 循环迭代器
USER_CYCLE = itertools.cycle(users_data)

class MyUser(HttpUser):
    def on_start(self):
        self.user_data = next(USER_CYCLE)
        resp = self.client.post("/login", json={
            "user": self.user_data["username"],
            "pass": self.user_data["password"]
        })
```

---

## 🚀 JSON 驱动的场景化参数化

```python
import json

def load_scenarios():
    with open("scenarios.json") as f:
        return json.load(f)

SCENARIOS = load_scenarios()
# scenarios.json:
# {
#   "search": ["keyword1", "keyword2", "keyword3"],
#   "product_ids": [101, 102, 103, 104]
# }
SCENARIO_CYCLE = itertools.cycle(SCENARIOS["search"])

class SearchUser(HttpUser):
    @task
    def search(self):
        keyword = next(SCENARIO_CYCLE)
        self.client.get(f"/api/search?q={keyword}")
```

---

## ⚠️ 常见坑点

1. **数据竞争**：不要在多 Worker 间使用同内存队列（每个 Worker 是独立进程，各自加载数据）
2. **数据用尽**：使用 `itertools.cycle` 循环复用数据，避免测试中途队列耗尽
3. **大文件加载**：`on_start` 中加载大数据影响启动作战，所有数据应在模块级别加载一次
4. **密码安全**：CSV 中保存明文密码仅限内测环境，生产需加密或远程读取

---

## 🔗 关联笔记

[[_MOC-locust]] | [[HttpUser基类与Web请求能力绑定]] | [[on_start与on_stop生命周期钩子方法]] | [[动态任务选择与任务跳过机制]]