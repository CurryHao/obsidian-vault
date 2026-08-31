---
tags: [locust, 运维, ulimit]
category: 02-Backend/Python/Locust
created: 2026-07-30
updated: 2026-07-30
status: 🟡 学习中
source: 系统ulimit与文件描述符上限调优.md
---
# 系统ulimit与文件描述符上限调优

## 系统 ulimit 与文件描述符上限调优

在 Locust 等性能测试工具模拟大规模并发时，每个用户/线程/协程都可能占用文件描述符（网络连接、套接字、日志文件等）。Linux 系统默认的 **软限制（soft limit）通常为 1024**，远不能满足数千甚至上万并发用户的需求。若不调整，会触发 `OSError: [Errno 24] Too many open files`，导致测试中断。

---

### 一、理解文件描述符与限制类型

- **文件描述符（FD）**：内核为每个打开的文件、网络连接、管道等分配的非负整数索引。
- **软限制（Soft limit）**：当前生效的限制，可由用户进程主动修改（不能超过硬限制）。
- **硬限制（Hard limit）**：系统允许的最大值，由 root 用户设定，普通用户可降低但不可提高。

查看当前限制：
```bash
ulimit -n            # 查看软限制
ulimit -n -H         # 查看硬限制
```

---

### 二、临时修改（会话级）

```bash
# 设置为 65535（软限制）
ulimit -n 65535

# 同时修改软硬限制（需 root 或具有权限）
ulimit -n 65535 -n 65535   # 部分 shell 不支持同时设置，可分别执行
```

> ⚠️ 此方法仅对当前 shell 及其启动的子进程生效，退出会话即失效。

---

### 三、永久修改（系统级）

#### 3.1 通过 `/etc/security/limits.conf`（对所有 PAM 登录会话生效）

编辑文件：
```bash
sudo vi /etc/security/limits.conf
```

添加如下行（`soft` 为软限制，`hard` 为硬限制）：
```
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
```
- `*` 表示所有用户，`root` 需单独指定（有些系统默认只限制普通用户）。
- 修改后需**重新登录**才能生效（或重启 `sshd` / 图形界面）。

#### 3.2 针对 Systemd 服务（如使用 `locust` 作为系统服务）

如果 Locust 由 systemd 启动，需要在 service 文件中添加：
```ini
[Service]
LimitNOFILE=65535
```
然后执行：
```bash
sudo systemctl daemon-reload
sudo systemctl restart locust.service
```

#### 3.3 针对 Docker 容器

Docker 容器默认继承宿主机的 ulimit，但可以通过 `--ulimit` 参数覆盖：

```bash
docker run --ulimit nofile=65535:65535 ... locustio/locust
```

在 Docker Compose 中：
```yaml
services:
  locust:
    image: locustio/locust
    ulimits:
      nofile:
        soft: 65535
        hard: 65535
```

在 Kubernetes 中，可通过 Pod 的 `securityContext` 设置（需容器运行时支持）：
```yaml
securityContext:
  sysctls:
  - name: fs.file-max
    value: "2097152"   # 系统级
```

#### 3.4 内核参数 `fs.file-max`（系统总限制）

`fs.file-max` 规定了整个系统允许打开的最大文件句柄数，`ulimit` 不能超过此值。

查看当前值：
```bash
cat /proc/sys/fs/file-max
```

永久修改（`/etc/sysctl.conf`）：
```bash
echo "fs.file-max = 2097152" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

---

### 四、验证调优是否生效

1. **检查当前进程的限制**（以 Locust 进程 PID 为例）：
   ```bash
   cat /proc/<pid>/limits | grep "open files"
   ```
   或使用 `prlimit` 查询：
   ```bash
   prlimit --pid <pid> --nofile
   ```

2. **检查系统当前已用 FD 数量**：
   ```bash
   cat /proc/sys/fs/file-nr
   # 输出格式：已分配 未使用 最大限制
   ```

3. **运行测试时监控 FD 使用情况**：
   ```bash
   watch -n 1 'lsof -u <username> | wc -l'
   ```

---

### 五、常见错误与解决方案

| 错误现象 | 原因 | 修复 |
|---------|------|------|
| `Too many open files` | 进程 FD 数超软限制 | 调大 `ulimit -n` |
| `cannot set limit: Operation not permitted` | 普通用户试图设置超过硬限制 | 以 root 修改硬限制，或使用 `sudo` |
| 修改 `/etc/security/limits.conf` 不生效 | 登录会话非 PAM 会话（如 SSH 未启用 `pam_limits`） | 检查 `/etc/pam.d/common-session` 或重启 `sshd`；某些系统需在 `/etc/ssh/sshd_config` 中启用 `UsePAM yes` |
| Docker 容器内设置无效 | Docker 默认未继承宿主机限制，且 `--ulimit` 需要 `--privileged` 或 `--cap-add` | 使用 `--ulimit` 参数，或在 Dockerfile 中通过 `ulimit -n` 无效，需运行时指定 |
| Kubernetes Pod 中无法修改 | 容器沙箱限制 | 在 Pod 的 `securityContext` 中设置 `sysctl`（需集群允许） |

---

### 六、针对 Locust 的推荐值

- **并发用户数 < 1000**：`nofile=65535` 足够。
- **并发用户数 1000~5000**：建议 `nofile=1048576`，并检查 `fs.file-max` 至少为 `2097152`。
- **并发用户数 > 5000**：除了文件描述符，还需调优内核网络参数（如 `net.ipv4.ip_local_port_range`, `net.ipv4.tcp_tw_reuse` 等）。

实际所需 FD 数约为 **（并发用户数 × 每个用户的连接数 × 2） + 100**，例如 5000 用户每个保持 2 个连接：约 20000+ 个 FD。

---

### 七、其他相关限制（一并关注）

| 限制项 | 命令查看 | 建议值 | 作用 |
|-------|---------|--------|------|
| 最大进程数 | `ulimit -u` | 65535 | 防止创建过多进程/线程 |
| 最大内存映射区域 | `sysctl vm.max_map_count` | 262144 | 影响内存映射文件（如 JVM） |
| 网络端口范围 | `sysctl net.ipv4.ip_local_port_range` | 1024 65000 | 确保有足够端口用于出站连接 |
| 系统最大文件数 | `cat /proc/sys/fs/file-max` | 2097152 | 系统总上限 |

---

### 八、一键脚本（适用 Linux）

```bash
#!/bin/bash
# setup_ulimit.sh - 自动配置 ulimit 和 sysctl

# 1. limits.conf
sudo tee -a /etc/security/limits.conf << EOF
* soft nofile 1048576
* hard nofile 1048576
root soft nofile 1048576
root hard nofile 1048576
EOF

# 2. sysctl
sudo tee -a /etc/sysctl.conf << EOF
fs.file-max = 2097152
net.ipv4.ip_local_port_range = 1024 65000
net.core.somaxconn = 65535
EOF
sudo sysctl -p

# 3. 对当前会话生效
ulimit -n 1048576

echo "Done. Please re-login to fully apply limits."
```

---

### 九、监控与告警

在压测过程中，建议开启 FD 监控，提前预警：
```bash
# Prometheus node_exporter 自带 filefd 指标
# 可用 Grafana 展示 filefd_allocated / filefd_maximum
```

若发现 FD 使用率超过 80%，应提前考虑扩大限制，防止测试中断。

---

### 总结

文件描述符限制是 Locust 压测中最基础的优化之一。正确配置后，可避免因 `Too many open files` 导致的意外终止。建议在压测执行环境（无论是物理机、虚拟机还是容器）的**初始化脚本**中统一设置，并加入日常巡检清单。

## 🔗 关联笔记

[[_MOC-locust]] | [[Kubernetes部署资源配置]] | [[Prometheus指标导出与Grafana监控大盘构建]] | [[docker-compose编排Master-Worker分布式集群]]
