---
tags: [locust]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: InfluxDB持久化存储与历史趋势对比.md
---
# InfluxDB持久化存储与历史趋势对比

将 Locust 的压测数据持久化到 InfluxDB，是构建企业级性能监控体系的关键一步。这不仅能解决 Locust 原生数据易失的问题，更重要的是，它能将每次压测的数据沉淀为宝贵的历史资产，为长期的**历史趋势分析**和**版本间性能对比**提供数据基础。

下面是一套完整的落地方案，包含持久化存储与历史趋势对比的实现。

---

### 核心架构：数据流（Data Flow）

整个方案的数据流向如下：
1.  **Locust Master**：作为压测控制中心，运行测试脚本。
2.  **数据采集器（Listener）**：通过监听 Locust 的事件钩子（Event Hooks），在测试运行时实时捕获性能数据。
3.  **InfluxDB**：作为时序数据库，接收并持久化存储所有性能数据点。
4.  **Grafana**：作为可视化平台，从 InfluxDB 中查询数据，构建监控仪表盘（Dashboard）。

---

### 方案一：使用 `locust-influxdb-listener`（推荐）

这是社区最流行、配置最简洁的方案，通过一个监听器（Listener）即可完成数据上报。

**1. 安装**

```bash
pip install locust-influxdb-listener
```
```code2. 在 Locustfile 中配置监听器**

在你的 `locustfile.py` 中添加以下代码，即可将数据发送到 InfluxDB。

```python
# locustfile.py
from locust import HttpUser, task, between, events
# 导入监听器
from locust_influxdb_listener import InfluxDBListener, InfluxDBSettings

# 配置 InfluxDB 连接信息
influxdb_settings = InfluxDBSettings(
    influxdb_host='localhost',      # InfluxDB 地址
    influxdb_port=8086,             # InfluxDB 端口
    influxdb_database='locust_db',  # 数据库名，需提前创建
    influxdb_user='admin',          # 用户名（可选）
    influxdb_password='admin123'    # 密码（可选）
)

# 初始化监听器，并将其挂载到 Locust 环境上
@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    InfluxDBListener(env=environment, settings=influxdb_settings)

class MyUser(HttpUser):
    host = "https://api.example.com"
    wait_time = between(1, 3)

    @task
    def my_task(self):
        self.client.get("/api/test")
```

**3. 启动压测**

正常启动 Locust 即可，监听器会自动在后台运行并上报数据。

```bash
locust -f locustfile.py --headless -u 100 -r 10 -t 1m
```

> **注意**：该监听器主要支持 InfluxDB 1.x 版本。如果你使用的是 InfluxDB 2.x，可能需要寻找其他方案或自行适配。

---

### 方案二：使用 `locust-plugins`（官方插件）

`locust-plugins` 是 Locust 官方维护的扩展库，功能更强大，支持将数据存入 InfluxDB 等多种后端。

**1. 安装**

```bash
pip install locust-plugins
```

**2. 在 Locustfile 中配置**

```python
# locustfile.py
from locust import HttpUser, task, between
from locust_plugins.listeners import InfluxDBListener

class MyUser(HttpUser):
    host = "https://api.example.com"
    wait_time = between(1, 3)

    @task
    def my_task(self):
        self.client.get("/api/test")

# 在文件末尾直接实例化监听器
# 参数: env, influx_host, influx_port, db_name
InfluxDBListener(env=None, influx_host='localhost', influx_port=8086, db_name='locust_db')
```

**3. 启动压测**

与方案一相同，正常启动即可。

```bash
locust -f locustfile.py --headless -u 100 -r 10 -t 1m
```

---

### 方案三：通过 Stats API 定时采集（通用方案）

这是一个不依赖第三方库的通用方法，通过定时请求 Locust 的 `/stats/requests` API 来获取数据。

**1. 编写数据采集脚本 (`collector.py`)**

```python
# collector.py
import requests
import time
from influxdb import InfluxDBClient

INFLUX_HOST = 'localhost'
INFLUX_PORT = 8086
INFLUX_DB = 'locust_db'
LOCUST_API_URL = 'http://localhost:8089/stats/requests'

client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT)
client.create_database(INFLUX_DB)
client.switch_database(INFLUX_DB)

while True:
    try:
        resp = requests.get(LOCUST_API_URL, timeout=5)
        data = resp.json()
        
        # 解析并构造 InfluxDB 数据点
        points = []
        for entry in data['stats']:
            point = {
                "measurement": "locust_stats",
                "tags": {
                    "method": entry['method'],
                    "name": entry['name']
                },
                "time": int(time.time() * 1000000000), # 纳秒时间戳
                "fields": {
                    "requests": entry['num_requests'],
                    "fails": entry['num_failures'],
                    "avg_response_time": entry['avg_response_time'],
                    "min_response_time": entry['min_response_time'],
                    "max_response_time": entry['max_response_time'],
                    "current_rps": entry['current_rps'],
                    "fail_ratio": entry['fail_ratio']
                }
            }
            points.append(point)
        
        if points:
            client.write_points(points)
            print(f"Written {len(points)} points")
    
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(5) # 每5秒采集一次
```

**2. 启动采集脚本**

在压测开始前，运行此脚本即可。

```bash
python collector.py
```

> **注意**：此方案需要 Locust 启动 Web UI 或 API 服务（默认端口 8089），否则无法采集数据。

---

### 实现历史趋势与版本对比

数据持久化到 InfluxDB 后，在 Grafana 中构建仪表盘来实现趋势分析是核心目标。核心思路是：**每次压测运行都带有唯一的标识（如 `test_run_id`），方便在查询时进行筛选和对比。**

#### 1. 为每次压测添加唯一标识

在监听器中增加一个 `test_run_id` 标签（Tag），可以将其作为环境变量或启动参数传入。以下是基于 `locust-influxdb-listener` 的扩展示例：

```python
# 在 InfluxDBSettings 或监听器初始化时增加额外标签
# 假设从环境变量获取 RUN_ID
import os
run_id = os.getenv('RUN_ID', 'default-run')

# 在监听器的配置中，将 run_id 作为静态标签附加到所有数据点
# 具体实现需参考各监听器的文档，通常支持 additional_tags 参数
```

#### 2. 在 Grafana 中构建对比视图

*   **数据源**：添加 InfluxDB 作为数据源。
*   **查询语句**：使用 InfluxQL 或 Flux 查询语言，通过 `WHERE` 语句筛选特定的 `test_run_id` 来构建面板。
*   **变量（Variables）**：创建一个名为 `$run_id` 的模板变量，其查询语句为 `SHOW TAG VALUES FROM "locust_stats" WITH KEY = "test_run_id"`。这样，你就可以在仪表盘顶部的下拉菜单中，轻松选择**任意两次**压测运行的 ID 进行对比。

**关键查询示例（InfluxQL）**：

```sql
-- 对比两次压测的 P95 响应时间
SELECT mean("p95_response_time") FROM "locust_stats" 
WHERE "test_run_id" =~ /$run_id/ AND $timeFilter 
GROUP BY time(1m), "test_run_id" fill(null)
```

**Grafana 仪表盘效果**：
*   **趋势面板**：展示选定 `test_run_id` 的 RPS、响应时间、错误率随时间的变化曲线。
*   **对比面板**：在同一个图中叠加显示两个不同 `test_run_id` 的指标曲线，直观对比版本迭代前后的性能差异。
*   **统计表格**：展示每次压测的汇总统计数据，如总请求数、平均响应时间、P95 等。

---

### 最佳实践与调优建议

1.  **数据保留策略（Retention Policy）**：为 InfluxDB 设置合理的数据保留策略，自动清理过期的历史数据，控制存储成本。
2.  **标签基数控制**：避免在 Tags 中使用 `user_id`、`session_id` 等高基数字段，这会导致索引膨胀，严重影响数据库性能。
3.  **降采样（Downsampling）**：对于时间久远的历史数据，可以创建连续查询（Continuous Query），将数据精度从秒级降采样到小时级或天级，长期保存以节省空间。
4.  **批量写入优化**：数据采集器应支持批量写入（Batch Write），以提高写入效率。
5.  **监控数据管道**：务必对数据采集器、InfluxDB 和 Grafana 自身的健康状态进行监控，确保数据链路畅通。

通过以上方案，你可以将 Locust 从一个临时的压测工具，升级为一个具备持续性能分析能力的平台，为系统的容量规划和性能优化提供坚实的数据支撑。

## 🔗 关联笔记

[[_MOC-locust]] | [[test_start与test_stop全局事件监听]] | [[LoadTestShape基类与核心tick方法重写]] | [[Master-Worker架构通信机制与零MQ基础]]
