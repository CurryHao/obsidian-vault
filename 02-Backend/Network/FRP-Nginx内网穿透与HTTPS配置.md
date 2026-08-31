---
tags: [frp, nginx, tunneling, ssl, https, reverse-proxy, firewall, linux]
category: 02-Backend/Network
created: 2026-08-12
updated: 2026-08-12
status: 🟡 学习中
source: FRP-Nginx内网穿透完整部署文档
---

# FRP + Nginx 内网穿透与 HTTPS 配置

## 📌 一句话总结
> **Nginx 做域名路由和 SSL 终结，FRP 只负责穿透隧道，防火墙把 FRP 映射的端口锁死在本地回环。** 所有公网流量只走 Nginx 的 80/443 入口，FRP 映射端口完全封闭在本机回环。

## 🎯 核心概念

### 流量路径
```
外网用户
→ https://app.example.com
→ VPS Nginx (监听 80/443)
→ proxy_pass http://127.0.0.1:18080 （走本地回环，0 公网出向流量）
→ FRP 隧道
→ 内网机器 127.0.0.1:8080
```

### 三个核心原则
1. **Nginx 的 `proxy_pass` 永远只写 `127.0.0.1:端口`**，绝不写公网 IP
2. **防火墙必须禁止外网访问所有 `remote_port`**，仅允许本机 127.0.0.1 访问
3. **每个二级域名对应一个内网服务**，通过 Nginx 的 `server_name` 分流

## ⚙️ 配置详解

### frps 服务端配置
**文件位置**：`/etc/frp/frps.ini`
```ini
[common]
bind_port = 7000          # frpc 连接端口
bind_addr = 0.0.0.0      # 允许 frpc 从公网连入
dashboard_port = 7500     # 可选：管理面板
dashboard_user = admin
dashboard_pwd = <strong-password>
```
**启动命令**：`./frps -c frps.ini` 或使用 systemd 托管

### frpc 客户端配置
**文件位置**：内网机器的 `frpc.ini`
```ini
[common]
server_addr = <你的VPS公网IP>
server_port = 7000

[service_a]
type = tcp
local_ip = 127.0.0.1
local_port = 8080
remote_port = 18080

[service_b]
type = tcp
local_ip = 192.168.1.10   # 可指向内网其他机器
local_port = 8081
remote_port = 18081
```

### 防火墙锁死回环（关键安全步骤）
**目的**：禁止外网直接访问 `remote_port`，仅允许本机（127.0.0.1）访问

#### iptables 方式（通用 Linux）
```bash
# 允许本机回环网卡访问 18080-18081
iptables -A INPUT -p tcp --dport 18080:18081 -s 127.0.0.1 -j ACCEPT
# 拒绝其他任何来源访问这些端口
iptables -A INPUT -p tcp --dport 18080:18081 -j DROP
# 保存规则
netfilter-persistent save    # Debian/Ubuntu
# 或
service iptables save        # CentOS/RHEL
```

#### UFW 方式（Ubuntu/Debian）
```bash
ufw deny 18080/tcp
ufw deny 18081/tcp
# UFW 默认放行本地回环，只需显式拒绝外部
```

### Nginx 反向代理配置
**文件位置**：`/etc/nginx/sites-available/default` 或 `conf.d/frp-proxy.conf`
```nginx
# 服务 A
server {
    listen 80;
    server_name app1.example.com;
    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
# 服务 B
server {
    listen 80;
    server_name app2.example.com;
    location / {
        proxy_pass http://127.0.0.1:18081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
**重载**：`nginx -t && systemctl reload nginx`

## 🔐 HTTPS 证书配置

### 推荐方案：通配符证书
- 一张证书保护 `*.example.com` 下所有子域名
- 新增二级域名无需再申请证书
- 配合 DNS-01 验证，绕过 WAF 拦截

### acme.sh 申请通配符证书
```bash
# 安装
curl https://get.acme.sh | sh

# 配置阿里云 DNS API
export Ali_Key="你的AccessKey ID"
export Ali_Secret="你的AccessKey Secret"

# 申请通配符证书
acme.sh --issue --dns dns_ali -d cloveh.online -d '*.cloveh.online'

# 安装证书到 Nginx
acme.sh --install-cert -d cloveh.online \
    --key-file /etc/nginx/ssl/cloveh.online.key \
    --fullchain-file /etc/nginx/ssl/cloveh.online.crt \
    --reloadcmd "systemctl reload nginx"
```

### Nginx HTTPS 配置
```nginx
server {
    listen 443 ssl http2;
    server_name app1.example.com;
    ssl_certificate /etc/nginx/ssl/cloveh.online.crt;
    ssl_certificate_key /etc/nginx/ssl/cloveh.online.key;
    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP 自动跳转 HTTPS
server {
    listen 80;
    server_name app1.example.com app2.example.com;
    return 301 https://$server_name$request_uri;
}
```

## 📊 ACME 验证方式对比

| 验证方式 | 原理 | 优点 | 缺点 | 适用场景 |
|---------|------|------|------|----------|
| **HTTP-01** | CA 访问 `/.well-known/acme-challenge/` | 配置简单 | 需要 80 端口；可能被 WAF 拦截 | 无 WAF、能开 80 端口 |
| **DNS-01** | 添加 DNS TXT 记录 | **绕过 WAF；支持通配符**；无需开放端口 | 需配置 DNS API 或手动添加记录 | **有 WAF；需要通配符证书**（推荐） |
| **TLS-ALPN-01** | 在 443 端口完成特殊 TLS 握手 | 不需要 80 端口 | 需要 443 端口；配置略复杂 | 纯 HTTPS 环境 |

## 🔄 后续新增服务流程
需要新增内网服务时，只需三步：
1. **修改 frpc.ini**：新增 `[proxy_new]` 段，分配新的 `remote_port`
2. **修改防火墙**：用同样规则把新 `remote_port` 锁进 127.0.0.1
3. **修改 Nginx**：新增 `server` 块，`server_name` 为新二级域名，`proxy_pass` 指向新的 `127.0.0.1:remote_port`

> **注意**：使用通配符证书时，新增二级域名**无需重新申请证书**，只需在 Nginx 中复用证书路径。

## ✅ 验证与测试
```bash
# 验证防火墙：本机应成功
curl http://127.0.0.1:18080

# 验证防火墙：外网应超时或被拒绝
telnet <VPS公网IP> 18080

# 验证 FRP 隧道
netstat -tunlp | grep frp

# 验证全链路：浏览器访问 https://app1.example.com → 应显示安全锁
```

## ⚠️ 常见坑点

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 502 Bad Gateway | Nginx 无法连到 127.0.0.1:remote_port | 检查 frps 是否运行、防火墙是否误杀 127.0.0.1 |
| 证书申请被 403 | WAF 拦截 Let's Encrypt | 改用 DNS-01 验证，或在 WAF 中放行 `/.well-known/acme-challenge/` 路径 |
| 外网能访问 remote_port | 防火墙规则未生效 | 检查 iptables/ufw 规则，确保 DROP 规则在 ACCEPT 之后 |
| 域名解析不生效 | DNS 记录未添加或 TTL 未刷新 | 检查 DNS 解析记录，等待几分钟或用 `dig` 确认 |

## 🔗 关联笔记
- [[FRP内网穿透基础配置]]
- [[Nginx反向代理最佳实践]]
- [[Let's Encrypt证书自动化]]
- [[iptables防火墙规则管理]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: frp, nginx, tunneling, ssl, https, reverse-proxy, firewall, linux）
> - [+] 新增 H1「FRP + Nginx 内网穿透与 HTTPS 配置」
> - [+] 新增「一句话总结」和「常见坑点」区块
> - [+] 新增「关联笔记」
> - [~] 结构化重组到标准区块（核心概念→配置详解→HTTPS→验证→坑点）
> - [~] 代码块补语言标识（ini, bash, nginx）