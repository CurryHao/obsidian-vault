---
tags: [locust, 报告, CSV]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: SV统计报告生成.md
---
# SV统计报告生成

## Locust 统计报告生成完整指南

Locust 提供了多层次的统计报告能力，从**实时 Web UI** 到**结构化 CSV 导出**，再到**可分享的 HTML 报告**。本章系统讲解如何生成、定制和自动化这三种报告形态，满足从临时调试到 CI/CD 集成的全场景需求。

---

### 一、报告体系总览

| 报告形态 | 生成方式 | 适用场景 | 数据粒度 |
|---------|---------|---------|---------|
| **Web UI 实时仪表板** | 启动时默认开启 | 实时监控、调试 | 秒级聚合 |
| **CSV 文件导出** | `--csv` 命令行参数 | 离线分析、Pandas/Excel 处理 | 端点级聚合 + 历史快照 |
| **HTML 报告** | Web UI 下载 / `--html` 参数 | 分享给团队、归档 | 端点级聚合 + 图表 |
| **逐请求明细 CSV** | `CsvRequestLogger` | 深度归因分析 | 每笔请求 |
| **编程式统计访问** | `environment.stats` API | 自定义报告、自动化断言 | 编程可控 |

---

### 二、核心统计数据结构

在深入报告生成之前，先理解 Locust 统计数据的底层结构：

```python
# 统计核心类层次
# Environment.stats -> RequestStats -> StatsEntry (每个端点一条)
# StatsEntry 包含:
#   - num_requests / num_failures: 成功/失败计数
#   - total_response_time / avg_response_time: 响应时间
#   - min_response_time / max_response_time: 极值
#   - response_times: 响应时间分布字典 {毫秒: 计数}
#   - num_reqs_per_sec / num_fail_per_sec: 每秒计数历史
#   - get_response_time_percentile(p): 计算任意百分位
```
### 三、CSV 报告生成（最通用方式）

#### 3.1 基础用法：`--csv` 参数

```bash
# 生成四份 CSV 文件（前缀为 results/load_test）
locust -f locustfile.py --headless -u 1000 -r 100 -t 10m \
    --csv=results/load_test \
    --csv-full-history   # 包含完整历史快照
```

生成的文件：

| 文件名 | 内容 |
|-------|------|
| `{prefix}_stats.csv` | 每个端点的聚合统计（含聚合行） |
| `{prefix}_stats_history.csv` | **历史快照**：每 5 秒记录一次全局统计 |
| `{prefix}_failures.csv` | **失败明细**：按错误类型聚合 |
| `{prefix}_exceptions.csv` | Python 异常栈追踪 |

#### 3.2 `_stats.csv` 字段详解

```csv
Type,Name,Requests,Fails,Median,90%ile,Average,Min,Max,Avg Size,Current RPS,Current Failures/s
GET,/api/users,15234,12,45,78,52,12,342,512,25.3,0.02
POST,/api/orders,8934,45,120,230,156,34,1245,890,14.2,0.08
Aggregated,Total,24168,57,78,156,89,12,1245,678,39.5,0.10
```

**关键字段解读**：
- **Requests/Fails**：总请求数和失败数
- **Median / 90%ile**：中位数和 90 百分位响应时间（ms）
- **Average**：算术平均值（易受极端值影响）
- **Min/Max**：最小/最大响应时间
- **Current RPS**：当前每秒请求数
- **Current Failures/s**：当前每秒失败数

#### 3.3 `_stats_history.csv` 历史快照

每 5 秒记录一行的全局统计快照，包含字段：
- `timestamp`：Unix 时间戳
- `user_count`：当前并发用户数
- `requests`：累计请求数
- `failures`：累计失败数
- `avg_response_time` / `min_response_time` / `max_response_time`
- `current_rps` / `current_failures_per_sec`

**用途**：绘制随时间变化的 RPS/响应时间趋势图，识别性能衰减拐点。

#### 3.4 `_failures.csv` 失败明细

```csv
Method,Name,Error,Occurrences
POST,/api/orders,HTTP 500 Internal Server Error,23
GET,/api/users,ConnectionError: Connection refused,12
POST,/api/orders,TimeoutError: 30s timeout,10
```

按 **错误类型** 聚合统计，方便快速定位主要故障源。

---

### 四、HTML 报告生成

#### 4.1 Web UI 手动下载

在 Locust Web 界面中，进入 **Download Data** 选项卡，点击 **Download Report** 即可生成包含图表和统计表格的 HTML 报告。

#### 4.2 命令行自动生成（Locust 2.x+）

```bash
locust -f locustfile.py --headless -u 1000 -r 100 -t 10m \
    --html=reports/report.html
```

生成的 HTML 报告包含：
- **Summary statistics**：所有端点的聚合统计表
- **History charts**：用户数/RPS/响应时间随时间变化的趋势图
- **Failures list**：按请求分组的失败明细

#### 4.3 使用第三方工具增强 HTML 报告

**locust-reporter**（Go 工具）：将已有的 CSV 文件转换为更精美的 HTML 报告：

```bash
# 安装
go get github.com/benc-uk/locust-reporter

# 使用
locust-reporter -dir ./results -prefix load_test -outfile report.html -failures
```

参数说明：
- `-dir`：CSV 文件所在目录
- `-prefix`：CSV 文件名前缀（必填）
- `-outfile`：输出 HTML 文件名
- `-failures`：是否包含失败明细（可能使文件很大）

---

### 五、编程式统计访问（最灵活）

通过 `events.test_stop` 事件钩子，在测试结束时编程访问所有统计数据：

```python
from locust import events
import json

@events.test_stop.add_listener
def generate_custom_report(environment, **kwargs):
    """测试结束时生成自定义 JSON 报告"""
    stats = environment.stats
    total = stats.total
    
    report = {
        "summary": {
            "total_requests": total.num_requests,
            "total_failures": total.num_failures,
            "failure_rate": total.num_failures / total.num_requests if total.num_requests > 0 else 0,
            "avg_response_time": total.avg_response_time,
            "min_response_time": total.min_response_time,
            "max_response_time": total.max_response_time,
            "total_rps": total.total_rps,
        },
        "percentiles": {
            f"p{int(p*100)}": total.get_response_time_percentile(p)
            for p in [0.50, 0.90, 0.95, 0.99, 0.999]
        },
        "endpoints": []
    }
    
    # 遍历每个端点的统计
    for (name, method), entry in stats.entries.items():
        report["endpoints"].append({
            "name": name,
            "method": method,
            "requests": entry.num_requests,
            "failures": entry.num_failures,
            "avg_rt": entry.avg_response_time,
            "p95": entry.get_response_time_percentile(0.95),
        })
    
    # 写入 JSON 文件供后续分析
    with open("custom_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # 打印关键指标到控制台
    print(f"\n{'='*50}")
    print(f"测试完成 - 总请求: {total.num_requests}, 失败率: {report['summary']['failure_rate']*100:.2f}%")
    print(f"平均响应时间: {total.avg_response_time:.0f}ms, P95: {total.get_response_time_percentile(0.95):.0f}ms")
    print(f"{'='*50}\n")
```

**关键 API**：
- `environment.stats.total` → 全局聚合 `StatsEntry`
- `environment.stats.entries` → 字典 `{(name, method): StatsEntry}`
- `entry.get_response_time_percentile(0.95)` → 计算任意百分位

---

### 六、逐请求明细日志（`CsvRequestLogger`）

内置的 `--csv` 只提供聚合统计。如果需要**每笔请求的原始明细**（用于深度归因），使用 `CsvRequestLogger`：

```python
# locustfile.py
from locust import HttpUser, task, events
from locust.contrib.csv_request_logger import CsvRequestLogger

# 初始化日志记录器
request_logger = CsvRequestLogger("results/requests.csv", flush_interval=100)

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    request_logger.register(environment)

class MyUser(HttpUser):
    @task
    def my_task(self):
        self.client.get("/api/data")
```

生成的 CSV 包含每笔请求的：

| 字段 | 说明 |
|-----|------|
| `timestamp` | 请求发送时间（Unix 时间戳，浮点） |
| `request_type` | HTTP 方法或协议名 |
| `name` | 请求名称（URL 路径） |
| `response_time_ms` | 响应时间（毫秒，保留 2 位小数） |
| `response_length` | 响应体大小（字节） |
| `status_code` | HTTP 状态码（失败时为 0） |
| `exception` | 异常信息（成功时为空） |

> **性能注意**：`flush_interval=1` 实时写入但性能较低，高 RPS 场景建议设为 100~1000。

---

### 七、自定义百分位与统计配置

#### 7.1 调整报告中的百分位

通过环境变量或代码修改 `PERCENTILES_TO_REPORT`：

```python
# 在 locustfile.py 顶部
from locust.stats import PERCENTILES_TO_REPORT

# 添加 98% 分位（默认已包含）
PERCENTILES_TO_REPORT = [0.50, 0.66, 0.75, 0.80, 0.90, 0.95, 0.98, 0.99, 0.999]

# 或通过命令行（Locust 2.18+）
# --percentiles 50,75,90,95,98,99
```

#### 7.2 自定义统计指标（如 TPS、TTFB）

通过 `events.request` 监听器添加自定义指标：

```python
from locust import events
from prometheus_client import Gauge

custom_tps = Gauge('custom_tps', 'Custom transactions per second')
custom_success_rate = Gauge('custom_success_rate', 'Success rate')

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, 
               response, context, exception, **kwargs):
    # 计算自定义指标并推送到监控系统
    pass
```

> 目前 Locust 不原生支持向 `report.html` 添加自定义指标列，建议通过 `events.test_stop` 生成独立的自定义报告。

---

### 八、CI/CD 集成最佳实践

#### 8.1 完整自动化命令

```bash
#!/bin/bash
# 执行压测并生成所有报告
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="reports/${TIMESTAMP}"

mkdir -p ${OUTPUT_DIR}

locust -f locustfile.py \
    --headless \
    --host=https://api.example.com \
    -u 5000 \
    -r 500 \
    -t 30m \
    --csv=${OUTPUT_DIR}/results \
    --csv-full-history \
    --html=${OUTPUT_DIR}/report.html \
    --loglevel WARNING

# 可选：使用 locust-reporter 生成增强版 HTML
locust-reporter -dir ${OUTPUT_DIR} -prefix results -outfile ${OUTPUT_DIR}/report_enhanced.html

echo "报告已生成: ${OUTPUT_DIR}/"
```

#### 8.2 报告解读检查清单

| 检查项 | 健康阈值 | 数据来源 |
|-------|---------|---------|
| 失败率 | < 0.1% | `_stats.csv` 的 `Fails/Requests` |
| P95 响应时间 | < SLA 约定（如 500ms） | `_stats.csv` 的 `95%ile` |
| RPS 稳定性 | 波动 < 20% | `_stats_history.csv` 的 `current_rps` |
| 用户数达标 | 达到 `-u` 设定值 | `_stats_history.csv` 的 `user_count` |
| 无致命异常 | 空 | `_exceptions.csv` |

---

### 九、总结与选型建议

| 场景 | 推荐方案 |
|-----|---------|
| **实时调试** | Web UI + Statistics 标签页 |
| **CI/CD 自动化归档** | `--csv` + `--html` 双输出 |
| **深度数据分析（Pandas/Excel）** | `--csv-full-history` 完整导出 |
| **逐请求归因分析** | `CsvRequestLogger` |
| **团队分享/管理层汇报** | HTML 报告（`--html` 或 locust-reporter） |
| **自定义监控集成** | `events.test_stop` 编程导出 JSON |
| **长期趋势分析** | `_stats_history.csv` 导入时序数据库 |

## 🔗 关联笔记

[[_MOC-locust]] | [[test_start与test_stop全局事件监听]] | [[on_start与on_stop生命周期钩子方法]] | [[LoadTestShape基类与核心tick方法重写]]
