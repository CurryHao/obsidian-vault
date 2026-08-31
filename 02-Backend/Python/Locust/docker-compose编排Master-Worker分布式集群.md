---
tags: [locust, Docker, 分布式]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: docker-compose编排Master-Worker分布式集群.md
---
# docker-compose编排Master-Worker分布式集群

## 使用 Docker Compose 编排 Locust Master-Worker 分布式集群

Docker Compose 是本地开发和测试环境中搭建分布式压测集群最便捷的工具。以下提供一套完整的配置方案，涵盖从基础部署到动态扩展的各个方面。

---

### 一、基础集群配置

创建 `docker-compose.yml` 文件，定义 Master 和 Worker 服务。

```yaml
version: '3.8'

services:
  # -------------------- Master 节点 --------------------
  master:
    image: locustio/locust:latest
    container_name: locust-master
    ports:
      - "8089:8089"      # Web UI 端口（对外暴露）
      - "5557:5557"      # Worker 通信端口（内部使用，无需对外暴露）
    volumes:
      - ./locustfile.py:/mnt/locust/locustfile.py  # 挂载测试脚本
      - ./reports:/mnt/locust/reports              # 挂载报告输出目录（可选）
    environment:
      - LOCUST_MODE=master
      - LOCUST_OPTS=--host=https://api.example.com  # 目标主机（可按需修改）
    command: -f /mnt/locust/locustfile.py --master
    networks:
      - locust-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8089"]
      interval: 10s
      timeout: 5s
      retries: 3

  # -------------------- Worker 节点（基础模板） --------------------
  worker:
    image: locustio/locust:latest
    container_name: locust-worker
    volumes:
      - ./locustfile.py:/mnt/locust/locustfile.py  # 所有 Worker 共享同一脚本
    environment:
      - LOCUST_MODE=worker
      - LOCUST_MASTER_HOST=master                   # 通过服务名访问 Master
      - LOCUST_MASTER_PORT=5557
    command: -f /mnt/locust/locustfile.py --worker --master-host master
    depends_on:
      - master
    networks:
      - locust-network
    # 资源限制（根据机器配置调整）
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

networks:
  locust-network:
    driver: bridge
```


### 二、启动与扩展 Worker

#### 2.1 启动基础集群

```bash
# 启动 Master 和 1 个 Worker
docker-compose up -d

# 查看日志
docker-compose logs -f
```

访问 `http://localhost:8089` 即可看到 Locust Web UI。

#### 2.2 动态扩展 Worker 数量

使用 `--scale` 参数快速增加 Worker 实例：

```bash
# 启动 4 个 Worker
docker-compose up -d --scale worker=4

# 调整到 8 个 Worker（运行时动态扩容）
docker-compose up -d --scale worker=8 --no-recreate
```

> **注意**：`--no-recreate` 避免重建已存在的容器，仅新增或移除。若需完全重新创建，可先 `docker-compose down` 再 `up`。

#### 2.3 指定不同 Worker 标签或参数

如果某些 Worker 需要执行不同任务，可以通过环境变量或命令行参数区分。一种常见做法是使用 `profiles` 或额外定义多个 Worker 服务。

```yaml
# 在 docker-compose.yml 中定义不同 Worker 组
worker-group-a:
  extends: worker  # 继承基础配置
  environment:
    - LOCUST_OPTS=--tags api

worker-group-b:
  extends: worker
  environment:
    - LOCUST_OPTS=--tags ui
```

启动时分别指定数量：
```bash
docker-compose up -d --scale worker-group-a=2 --scale worker-group-b=3
```

---

### 三、共享脚本与数据文件的最佳实践

为了确保所有容器使用相同的测试脚本，推荐以下两种方式：

| 方式 | 适用场景 | 操作 |
|------|---------|------|
| **挂载卷** | 开发调试，脚本频繁修改 | `volumes: - ./locustfile.py:/mnt/locust/locustfile.py` |
| **构建自定义镜像** | 生产环境，固化脚本和依赖 | 将脚本 `COPY` 进镜像，并使用该镜像替代官方镜像 |

> **推荐生产环境使用自定义镜像**，避免挂载卷带来的不一致性风险。构建方法参见“Docker 官方镜像使用与自定义镜像构建”章节。

---

### 四、网络配置解析

- **自定义网络** `locust-network`：确保容器间通过服务名（如 `master`）互相解析。
- **端口映射**：
  - Master 暴露 `8089` 供外部访问 Web UI。
  - Worker 无需对外暴露端口，仅需能与 Master 的 `5557` 通信。
- **跨主机部署**：若要跨多台物理机，需使用 Swarm 或 Kubernetes，并确保网络互通（可参考 Swarm 模式下的 `--publish` 和 overlay 网络）。

---

### 五、结果持久化与报告收集

将报告输出目录挂载到宿主机，便于收集测试结果：

```yaml
# Master 服务中
volumes:
  - ./reports:/mnt/locust/reports
command: -f /mnt/locust/locustfile.py --master --csv=/mnt/locust/reports/result --html=/mnt/locust/reports/report.html
```

测试结束后，`./reports` 目录下会生成 CSV 和 HTML 文件。

---

### 六、环境变量与参数传递

通过 `environment` 或 `.env` 文件集中管理配置：

```yaml
# docker-compose.yml
services:
  master:
    environment:
      - TARGET_HOST=https://api.example.com
      - RUN_ID=${RUN_ID:-default}
    command: -f /mnt/locust/locustfile.py --master --host=${TARGET_HOST}
```

使用 `.env` 文件：
```bash
# .env
TARGET_HOST=https://staging.example.com
RUN_ID=staging_2026_07_24
```

启动时自动加载。

---

### 七、健康检查与自动重启

在 Master 和 Worker 中添加 `healthcheck`（如 Master 示例所示），结合 `restart: unless-stopped` 可实现故障自动恢复。

```yaml
restart: unless-stopped
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8089"]
  interval: 30s
  timeout: 5s
  retries: 5
```

---

### 八、性能调优建议

1. **资源限制**：为 Worker 设置合理的 CPU/内存限制，避免单个 Worker 耗尽宿主机资源。
2. **Worker 数量**：通常建议每个 Worker 模拟 500~1000 并发用户，具体取决于目标系统响应时间和网络延迟。
3. **网络模式**：在 Linux 主机上可使用 `network_mode: host` 提高网络性能（需权衡安全性）。
4. **日志级别**：生产环境设置 `--loglevel WARNING` 减少日志 I/O。

---

### 九、完整启动流程示例

```bash
# 1. 准备 locustfile.py 和 docker-compose.yml
# 2. 启动集群（4 个 Worker）
docker-compose up -d --scale worker=4

# 3. 查看状态
docker-compose ps
docker-compose logs master

# 4. 访问 Web UI 开始测试

# 5. 测试结束后，停止并清理
docker-compose down
```

---

### 十、进阶：集成 Prometheus 与 Grafana

可将监控组件一并加入 Compose 文件，实现一站式监控：

```yaml
services:
  # ... Locust Master/Worker ...
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

配置 Locust Exporter 或内置 Prometheus 端点即可实现指标采集（参考相关章节）。

---

### 总结

| 关键点 | 说明 |
|--------|------|
| **Master 与 Worker 通信** | 通过服务名 `master` 和端口 `5557` |
| **动态扩容** | 使用 `--scale worker=N` 调整并发能力 |
| **脚本同步** | 推荐自定义镜像，避免挂载卷的不一致问题 |
| **结果收集** | 挂载报告目录，便于提取 CSV/HTML |
| **生产环境** | 考虑 Kubernetes + Helm Chart 实现更强大的编排能力 |

通过上述配置，你可以快速搭建一个弹性、可扩展的 Locust 分布式压测集群，在本地或测试环境中验证系统容量和稳定性。

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[Prometheus指标导出与Grafana监控大盘构建]] | [[on_start与on_stop生命周期钩子方法]]
