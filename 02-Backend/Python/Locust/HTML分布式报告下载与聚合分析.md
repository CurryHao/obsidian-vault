---
tags: [locust]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: HTML分布式报告下载与聚合分析.md
---
# HTML分布式报告下载与聚合分析

## 分布式压测报告生成机制

在 Locust 分布式压测中，**Master 节点汇总所有 Worker 的统计数据，并生成统一的报告**。

### 统计聚合原理

Worker 节点定期将各自采集的统计数据发送给 Master。Master 通过 `StatsEntry.extend()` 方法完成聚合：

| 聚合操作 | 处理方式 |
|---------|---------|
| 请求计数/失败计数 | 各 Worker 求和 |
| 总响应时间 | 各 Worker 求和 |
| 响应时间分布 (`response_times`) | 合并字典，相同毫秒值的计数相加 |
| 每秒请求/失败历史 (`num_reqs_per_sec`) | 合并字典 |
| 最小响应时间 | 取所有 Worker 的最小值 |
| 最大响应时间 | 取所有 Worker 的最大值 |

因此，**Master 上看到的统计本身就是所有 Worker 的聚合结果**，生成 HTML 报告时直接使用这些已聚合的数据即可。

---

## HTML 报告下载方式

### 方式一：Web UI 手动下载（交互式）

在 Locust Web 界面中：

1. 点击顶部导航栏的 **Download Data** 选项卡
2. 点击 **Download Report** 按钮
3. 浏览器自动下载 `report.html` 文件

对应的后端 API 端点为 `/stats/report`。

### 方式二：命令行自动生成（Headless 模式）

```bash
locust -f locustfile.py \
    --headless \
    -u 1000 -r 100 -t 10m \
    --html=reports/report.html \
    --host=https://api.example.com
```
结束后自动在指定路径生成 HTML 报告。

### 方式三：通过 API 编程获取

```python
import requests

# 从 Master 的 Web 服务获取报告
response = requests.get("http://<master_ip>:8089/stats/report")
with open("report.html", "w") as f:
    f.write(response.text)
```

---

## 多进程/多 Worker 报告生成问题与解决方案

### 已知问题：`--processes` 多进程模式

使用 `--processes` 参数启动多进程模式时（如 `--processes 4`），**每个工作进程会独立生成一份 HTML 报告**，导致产生多个报告文件而非一个。

**根本原因**：进程隔离 + 缺乏主进程统一协调。

**解决方案**：

| 方案 | 适用场景 | 操作 |
|-----|---------|-----|
| **改用分布式模式** | 生产环境/大规模压测 | 使用 `--master` + `--worker` 部署，Master 统一生成报告 |
| **后处理合并** | 临时应急 | 编写脚本解析多个 HTML 文件，合并为统一报告 |
| **单进程模式** | 简单测试场景 | 去掉 `--processes` 参数 |

### 分布式模式（`--master` + `--worker`）正常工作

```bash
# Master 节点
locust -f locustfile.py --master --web-port=8089

# 各 Worker 节点
locust -f locustfile.py --worker --master-host=<master_ip>

# 测试结束后，从 Master Web UI 下载报告，或使用 --html 参数
locust -f locustfile.py --master --html=report.html --headless -u 1000 -r 100 -t 10m
```

分布式模式下，所有 Worker 的统计汇总到 Master，**报告生成逻辑只在 Master 执行**，不会出现多文件问题。

---

## 聚合分析方法

### 1. CSV 导出 + 外部聚合

```bash
locust -f locustfile.py --headless \
    --csv=results/test \
    --csv-full-history \
    -u 1000 -r 100 -t 10m
```

生成文件：
- `results/test_stats.csv` — 各端点聚合统计
- `results/test_stats_history.csv` — 历史快照（每 5 秒）
- `results/test_failures.csv` — 失败明细
- `results/test_exceptions.csv` — 异常栈

使用 Pandas 进行深度分析：

```python
import pandas as pd

stats = pd.read_csv("results/test_stats.csv")
history = pd.read_csv("results/test_stats_history.csv")

# 计算整体失败率
failure_rate = stats[stats['Name'] == 'Aggregated']['Fails'].iloc[0] / \
               stats[stats['Name'] == 'Aggregated']['Requests'].iloc[0]

# 绘制 RPS 趋势
history.plot(x='Timestamp', y='Current RPS')
```

### 2. 编程式获取聚合统计（`events.test_stop`）

```python
from locust import events
import json

@events.test_stop.add_listener
def aggregate_report(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    
    report = {
        "total_requests": total.num_requests,
        "total_failures": total.num_failures,
        "failure_rate": total.num_failures / total.num_requests if total.num_requests > 0 else 0,
        "avg_rt": total.avg_response_time,
        "p95": total.get_response_time_percentile(0.95),
        "p99": total.get_response_time_percentile(0.99),
        "endpoints": [
            {
                "name": name,
                "method": method,
                "requests": entry.num_requests,
                "failures": entry.num_failures,
                "avg_rt": entry.avg_response_time,
                "p95": entry.get_response_time_percentile(0.95)
            }
            for (name, method), entry in stats.entries.items()
        ]
    }
    
    with open("aggregated_report.json", "w") as f:
        json.dump(report, f, indent=2)
```

### 3. 使用第三方工具增强分析

- **JtlReporter**：存储和比较历史性能报告
- **Locust Cloud**：托管版分布式压测，提供更详细的报告和长期趋势分析
- **Grafana + InfluxDB**：将 Locust 指标导入时序数据库，构建自定义仪表板

---

## 最佳实践总结

| 场景 | 推荐方案 |
|-----|---------|
| **交互式调试** | Web UI → Download Data → Download Report |
| **CI/CD 自动化** | `--html` 参数 + `--csv` 双输出 |
| **大规模分布式压测** | `--master` + `--worker` 模式，Master 统一生成报告 |
| **多进程模式** | 避免使用 `--processes`，改用分布式架构 |
| **深度数据分析** | CSV 导出 + Pandas/Jupyter |
| **长期趋势对比** | 编程式导出 JSON + 时序数据库 |

**关键原则**：在分布式模式下，**始终从 Master 节点获取报告**，因为只有 Master 拥有完整的聚合统计数据。

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[on_start与on_stop生命周期钩子方法]] | [[test_start与test_stop全局事件监听]]
