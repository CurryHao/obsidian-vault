---
tags: [locust, Prometheus, Grafana]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: Prometheus指标导出与Grafana监控大盘构建.md
---
# Prometheus指标导出与Grafana监控大盘构建

将 Locust 与 Prometheus 和 Grafana 集成，是实现**数据持久化**、**历史对比**和**团队协作**的企业级性能监控方案。这套方案能解决 Locust 原生 Web UI 数据易失、分析维度单一等问题。

下面提供两种主流的集成路径，以及详细的配置指南。

### 方案一：使用独立 Exporter（推荐，适用于 Locust < 2.19）

这是最经典的方案，通过一个独立的服务 (`locust_exporter`) 从 Locust 的 Master 节点抓取数据，再暴露给 Prometheus 进行采集。

**1. 架构组件**

*   **Locust Master**: 压测控制端，暴露统计数据的 HTTP API。
*   **Locust Exporter**: 独立服务，从 Master API 获取数据，转换为 Prometheus 格式。
*   **Prometheus**: 时序数据库，定期从 Exporter 拉取（Pull）并存储指标。
*   **Grafana**: 可视化平台，从 Prometheus 查询数据并展示。

**2. 快速部署（Docker Compose）**

使用 `docker-compose.yml` 可以一键启动整套环境。

```yaml
# docker-compose.yml
version: "3.8"

services:
  # 1. Locust Master 节点
  locust-master:
    image: locustio/locust:latest
    ports:
      - "8089:8089"   # Web UI 端口
      - "5557:5557"   # Worker 通信端口
    volumes:
      - ./:/mnt/locust
    command: -f /mnt/locust/locustfile.py --master -H http://target-service.com
    networks:
      - monitoring

  # 2. Locust Exporter
  locust-exporter:
    image: containersol/locust_exporter:latest 
    # 使用 host 网络模式以便访问 Master 节点
    network_mode: "host" 
    environment:
      - LOCUST_EXPORTER_URI=http://localhost:8089 
      - LOCUST_EXPORTER_WEB_LISTEN_ADDRESS=:9646 
    depends_on:
      - locust-master

  # 3. Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
    networks:
      - monitoring

  # 4. Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-storage:/var/lib/grafana
    networks:
      - monitoring

networks:
  monitoring:
    driver: bridge

volumes:
  grafana-storage:
```
3. 配置 Prometheus**

创建 `prometheus.yml` 文件，配置抓取任务：

```yaml
# prometheus.yml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'locust'
    static_configs:
      - targets: ['locust-exporter:9646'] # exporter 的地址和端口
```

**4. 导入 Grafana 仪表盘**

启动所有服务后，访问 `http://localhost:3000`（默认账号 `admin/admin`）。
*   **方式一（推荐）**：在 Grafana 中导入仪表盘 **ID `11985`**。
*   **方式二**：从 `locust_exporter` 项目的 GitHub 仓库下载 `locust_dashboard.json` 文件进行导入。

---

### 方案二：使用内置 Prometheus Exporter（适用于 Locust >= 2.19）

从 Locust 2.19 版本开始，官方提供了内置的 Prometheus 导出功能，无需额外运行独立 Exporter。

**1. 启用 Exporter**

在启动 Locust Master 时，通过环境变量启用内置的 Prometheus 指标端点：

```bash
# 启动 Master，并启用 Prometheus Exporter 在 9646 端口
LOCUST_PROMETHEUS_PORT=9646 locust -f locustfile.py --master --web-port=8089
```

**2. 修改 Prometheus 配置**

将 Prometheus 的抓取目标指向 Locust Master 的 `/metrics` 端点：

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'locust'
    static_configs:
      - targets: ['<locust_master_ip>:9646'] # 指向 Master 的 IP 和端口
```

**3. 指标说明**

此方式导出的指标以 `locust_` 为前缀，主要包括：

| 指标名称 | 类型 | 说明 |
| :--- | :--- | :--- |
| `locust_users` | Gauge | 当前模拟的用户总数 |
| `locust_requests_total` | Counter | 总请求数（按 `name`, `method` 区分） |
| `locust_failures_total` | Counter | 总失败请求数 |
| `locust_response_time_p50_milliseconds` | Gauge | 50百分位响应时间 (ms) |
| `locust_response_time_p95_milliseconds` | Gauge | 95百分位响应时间 (ms) |
| `locust_current_rps` | Gauge | 当前每秒请求数 (RPS) |

---

### 方案三：使用 OpenTelemetry（OTel）导出

Locust 也支持 OpenTelemetry 协议，可以将指标和追踪数据发送到兼容 OTel 的后端。

**1. 安装依赖**

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-prometheus
```

**2. 配置 OTel 导出器**

在 `locustfile.py` 中配置 OTel，将指标导出到 Prometheus：

```python
# locustfile.py
from locust import events
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

# 创建 Prometheus 指标读取器
reader = PrometheusMetricReader()
resource = Resource(attributes={SERVICE_NAME: "locust-service"})
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    # 将 OTel 的指标端点暴露给 Prometheus 抓取
    # 此处的实现依赖于具体的 OTel 和 Web 框架集成
    print("OTel Prometheus exporter configured.")
```

---

### Grafana 仪表盘构建建议

无论选择哪种方案，导入预置仪表盘都是最快的方式。此外，你也可以构建自定义仪表盘：

1.  **添加 Prometheus 数据源**：在 Grafana 中配置 URL 为 `http://prometheus:9090`。
2.  **创建关键面板**：
    *   **活跃用户数**：使用 `locust_users` 指标。
    *   **总请求速率 (RPS)**：使用 `rate(locust_requests_total[1m])` 查询。
    *   **请求失败率**：使用 `rate(locust_failures_total[1m]) / rate(locust_requests_total[1m])`。
    *   **响应时间百分位**：使用 `locust_response_time_p50_milliseconds` 和 `p95_milliseconds`。
    *   **关联分析**：将 Locust 指标与目标服务器的 **CPU/内存** 等系统指标放在同一时间轴进行关联分析。

### 总结与建议

| 特性 | 方案一：独立 Exporter | 方案二：内置 Exporter |
| :--- | :--- | :--- |
| **适用版本** | 所有 Locust 版本 | Locust >= 2.19 |
| **部署复杂度** | 稍高，需额外运行一个服务 | 低，无需额外组件 |
| **功能完整性** | 成熟稳定，社区支持广泛 | 较新，指标可能不如 Exporter 丰富 |
| **推荐场景** | 生产环境、复杂部署 | 快速验证、新项目 |

**一般建议**：
*   如果你是**新建项目**或使用 **Locust 2.19+**，可以优先尝试**方案二（内置 Exporter）**，它更轻量。
*   如果你的环境**无法升级 Locust** 或需要更成熟的方案，**方案一（独立 Exporter）** 是经过长期生产验证的可靠选择。
*   对于 Kubernetes 环境，确保在 Locust Master Pod 的 annotations 中添加 `prometheus.io/scrape: "true"` 和 `prometheus.io/port: "9646"`，以便 Prometheus 自动发现。

## 🔗 关联笔记

[[_MOC-locust]] | [[docker-compose编排Master-Worker分布式集群]] | [[Kubernetes部署资源配置]] | [[Master-Worker架构通信机制与零MQ基础]]
