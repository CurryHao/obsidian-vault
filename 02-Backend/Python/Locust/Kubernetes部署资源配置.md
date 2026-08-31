---
tags: [locust, Kubernetes, 部署]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: Kubernetes部署资源配置.md
---
# Kubernetes部署资源配置

在 Kubernetes 上部署 Locust 分布式集群，最推荐的方式是使用 **Helm** 或 **Locust Kubernetes Operator**，它们能极大地简化部署和管理工作。不过，为了帮助你更深入地理解其架构，我也会提供一个基于原生 YAML 的部署示例。

下面是三种主流部署方案的详细介绍。

### 方案一：使用原生 YAML 部署（便于理解架构）

这种方式通过编写 YAML 文件来手动创建所有资源，能让你清晰地了解 Locust 集群的各个组件及其关系。

#### 1. 准备测试脚本 (ConfigMap)

首先，将你的 `locustfile.py` 通过 ConfigMap 挂载到容器中，便于后续修改。

```yaml
# locust-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: locust-scripts
data:
  locustfile.py: |
    from locust import HttpUser, task, between
    class MyUser(HttpUser):
        wait_time = between(1, 3)
        @task
        def my_task(self):
            self.client.get("/")
```
```code配置：`kubectl apply -f locust-configmap.yaml`

#### 2. 部署 Master 节点

Master 负责 Web UI 和调度 Worker，通常只需要一个副本。

```yaml
# locust-master.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: locust-master
spec:
  replicas: 1
  selector:
    matchLabels:
      app: locust
      role: master
  template:
    metadata:
      labels:
        app: locust
        role: master
    spec:
      containers:
      - name: master
        image: locustio/locust:latest
        args: ["-f", "/mnt/locust/locustfile.py", "--master"] # 以 Master 模式启动
        ports:
        - containerPort: 8089 # Web UI 端口
        - containerPort: 5557 # Worker 通信端口
        volumeMounts:
        - mountPath: /mnt/locust
          name: locust-scripts
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: locust-scripts
        configMap:
          name: locust-scripts
---
# 为 Master 创建 Service
apiVersion: v1
kind: Service
metadata:
  name: locust-master
spec:
  type: ClusterIP # 内部服务，也可改为 LoadBalancer 或 NodePort 对外暴露
  ports:
  - port: 8089
    targetPort: 8089
    name: web
  - port: 5557
    targetPort: 5557
    name: comm
  selector:
    app: locust
    role: master
```

#### 3. 部署 Worker 节点

Worker 执行具体的测试任务，可以根据需要扩展副本数。

```yaml
# locust-worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: locust-worker
spec:
  replicas: 3 # 初始 Worker 数量
  selector:
    matchLabels:
      app: locust
      role: worker
  template:
    metadata:
      labels:
        app: locust
        role: worker
    spec:
      containers:
      - name: worker
        image: locustio/locust:latest
        args: ["-f", "/mnt/locust/locustfile.py", "--worker", "--master-host", "locust-master"] # 连接到 Master
        volumeMounts:
        - mountPath: /mnt/locust
          name: locust-scripts
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
      volumes:
      - name: locust-scripts
        configMap:
          name: locust-scripts
```

应用配置并扩展 Worker：
```bash
kubectl apply -f locust-master.yaml
kubectl apply -f locust-worker.yaml
# 扩展 Worker 数量
kubectl scale deployment locust-worker --replicas=5
```

#### 4. 配置 Ingress（可选）

如果需要通过域名访问 Locust Web UI，可以创建 Ingress 资源。

```yaml
# locust-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: locust-ingress
  annotations:
    kubernetes.io/ingress.class: "nginx"  # 根据你的 Ingress Controller 修改
    # 如果使用 AWS ALB Ingress Controller，需要配置如下注解
    # alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:..."
spec:
  rules:
  - host: locust.your-domain.com  # 替换为你的域名
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: locust-master
            port:
              number: 8089
```

### 方案二：使用 Helm（官方推荐）

Helm 是 Kubernetes 的包管理器，能让你通过简单的配置部署复杂的应用。社区有成熟的 Locust Helm Chart。

**1. 添加 Helm 仓库**
```bash
helm repo add deliveryhero https://charts.deliveryhero.com/
helm repo update
```

**2. 自定义配置 (`values.yaml`)**
创建一个 `values.yaml` 文件来定制你的部署。

```yaml
# values.yaml
# 指定 Master 和 Worker 使用的镜像
image:
  repository: locustio/locust
  tag: latest

# Master 配置
master:
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1"
  service:
    type: ClusterIP # 或 LoadBalancer, NodePort

# Worker 配置
worker:
  replicas: 3 # Worker 数量
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2"

# 测试脚本配置
locustfile:
  configmap: "locust-scripts" # 如果你已经创建了 ConfigMap
  # 或者直接内联写入
  # inline: |
  #   from locust import HttpUser, task, between
  #   ...

# Ingress 配置（可选）
ingress:
  enabled: true
  className: "nginx"
  annotations:
    # kubernetes.io/ingress.class: nginx
    # alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:..."
  hosts:
    - host: locust.your-domain.com
      paths:
        - path: /
          pathType: Prefix
```

**3. 安装/升级 Release**
```bash
# 安装
helm install my-locust deliveryhero/locust -f values.yaml

# 升级（例如修改了 values.yaml 或调整 Worker 数量后）
helm upgrade my-locust deliveryhero/locust -f values.yaml \
  --set worker.replicas=5
```

### 方案三：使用 Locust Kubernetes Operator（面向云原生）

Operator 是 Kubernetes 的一种扩展，它将运维知识编码到软件中。`locust-k8s-operator` 可以让你通过自定义资源（CR）来声明式地管理 Locust 集群。

安装 Operator 后，你可以通过定义 `LocustTest` 资源来创建和管理一次完整的压测任务。
```yaml
apiVersion: locust.io/v1
kind: LocustTest
metadata:
  name: my-load-test
spec:
  # 定义测试参数，如目标主机、并发用户数、测试脚本等
  image: my-locust-image:latest
  host: https://my-target-api.com
  users: 1000
  hatchRate: 100
  runTime: 10m
  # ...更多配置
```

### 横向Pod自动伸缩 (HPA)

你可以利用 Kubernetes 的 HPA 根据自定义指标（如每秒请求数 RPS）来自动调整 Worker 的数量。这需要部署 Prometheus Adapter 等组件来提供自定义 API。

### 总结与建议

| 部署方式 | 适用场景 | 优点 |
| :--- | :--- | :--- |
| **原生 YAML** | 学习、理解架构 | 清晰展示组件关系，灵活 |
| **Helm** | **生产环境推荐** | 易于管理、升级和配置，社区支持好 |
| **Operator** | 云原生环境、频繁执行压测任务 | 声明式API，与K8s生态集成更深 |

**核心要点**：
*   **生产环境**强烈推荐使用 **Helm** 方案，它隐藏了复杂的细节，并提供了丰富的配置项。
*   如果你对底层原理感兴趣，可以先用 **原生 YAML** 手动部署一次，这能帮你更好地理解 Master-Worker 的通信机制。
*   测试脚本（`locustfile.py`）建议通过 **ConfigMap** 管理，方便后续更新而无需重新构建镜像。
*   如果需要对外暴露 Web UI，可根据你的 Kubernetes 环境配置 **Ingress** 或 **LoadBalancer** 类型的 Service。

## 🔗 关联笔记

[[_MOC-locust]] | [[Master-Worker架构通信机制与零MQ基础]] | [[Prometheus指标导出与Grafana监控大盘构建]] | [[docker-compose编排Master-Worker分布式集群]]
