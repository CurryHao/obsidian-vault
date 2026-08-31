---
tags: [cloudflare, ssl, 525-error, sni-filtering, tunnel, frp, nginx, certificate, troubleshooting]
category: 02-Backend/Network
created: 2026-08-12
updated: 2026-08-12
status: ✅ 已解决
source: 本地排查记录 + AI 协助
---

# Cloudflare 全历程总结（2026-08-04 → 08-12）

## 📌 一句话总结
> **阿里云 ECS + 非备案域名 + Cloudflare 代理 = 入站 TLS 按 SNI 拦截 → 525 错误。根治方案：Cloudflare Tunnel（出站连接），彻底绕过入站过滤。**

## ⏱️ 时间线

### 08-04 dh.cloveh.online 无法访问
→ 排查出阿里云安全组没放行 80/443，补了规则

### 08-12 上午 搭 Actual Budget 记账
- frp 穿透 24800 端口 → finance.cloveh.online
- 尝试 acme.sh + ZeroSSL 申请 SSL 证书，失败
- certbot HTTP-01 被拦（返回 403，Server 头是 Beaver=阿里云 WAF）
- DNS-01 也失败

### 08-12 13:43 服务器 FRP 架构全面体检
- frps 配置正确
- 发现 3 个隐患（见遗留事项）

### 08-12 14:15 Cloudflare Token 验证
- cfat_ User Token 有效但 acme.sh 用不了
- certbot DNS-01 因 TXT 记录/DNS 缓存反复失败
- **认知**：acme.sh 的 dns_cf 插件只认 Global API Key（32位hex），不认 cfut_/cfat_ 开头的 User Token
- **陷阱**：cfat_ Token 有 account 级权限但路由不到 zone 级 DNS API

### 08-12 15:17 放弃 ACME 路线
→ 直接在 Cloudflare 控制台生成 **Origin Certificate**（通配 *.cloveh.online，有效期到 2041）
→ 部署到 nginx
→ 但站点仍然报 **525**

### 08-12 16:00+（本会话）525 彻底破案 + 根治

## 🐛 遇到的问题与解决思路

### 问题 1：SSL 证书申请全面失败

**现象**：
- certbot HTTP-01 被拦（返回 403，Server 头是 Beaver=阿里云 WAF）
- DNS-01 也失败

**根因**：
1. 域名走 Cloudflare 代理后，外部 HTTP 请求被阿里云 WAF/ICP 备案页拦截
2. acme.sh 的 dns_cf 插件只认 Global API Key（32位hex），不认 cfut_/cfat_ 开头的 User Token
3. cfat_ Token 有 account 级权限但路由不到 zone 级 DNS API（权限陷阱）

**解决**：绕开 ACME，直接在 Cloudflare 控制台生成 **Origin Certificate**（15年有效，免续期，专门给 CF 后面的源站用）→ 部署到 `/etc/nginx/ssl/`

### 问题 2：证书装好了，还是 525

**现象**：Cloudflare 边缘→源站 SSL 握手失败

**排查过程**：
1. 发现 nginx 被停 → 拉起（这是第一层问题）
2. DNS 其实是对的（finance/dh → 120.79.178.199）
3. **外部 SNI 对比测试是关键突破**：
   - SNI=`finance`/`dh`/`www.cloveh.online` → 握手被掐（无证书）
   - SNI=`example.com` → 正常
   - 无 SNI（纯 IP）→ 正常

**结论**：入站 TLS 只拦 `*.cloveh.online` 的 SNI——阿里云 WAF/DPI 按域名（非 ICP 备案）做 SNI 级过滤，Cloudflare 边缘连源站必死 → 525

**解决（根治）**：**Cloudflare Tunnel（出站连接）**
- 隧道 `cloveh` 已建，DNS 改 CNAME
- 流量从本机主动连出去，根本不经过入站 SNI 过滤，证书、WAF 全部无关
- finance → 24800 (Actual Budget)
- dh → 8081 (nginx 中继：/i/和/api/upload→Picsur, /→闲鱼 65535)
- nginx 的 443 配置已退役（外网走隧道，不走 443 了）

## 💡 沉淀下来的认知（以后都用得上）

### Cloudflare 凭证三兄弟

| Token 类型 | 前缀 | 用途 | 认证头 |
|-----------|------|------|--------|
| Global API Key | 37位hex | acme.sh、完整 API 操作 | X-Auth-Key + X-Auth-Email |
| User Token (Account) | cfat_ | Account 级操作 | Authorization: Bearer |
| User Token (User) | cfut_ | User 级操作 | Authorization: Bearer |

**关键差异**：acme.sh 只吃 Global Key；certbot 都支持；User Token 常带权限陷阱

### 525 ≠ 服务器挂
是 CF 边缘 ↔ 源站的 TLS 问题，源站可能活着（本机自测全通）

### 大陆 ECS + 非备案域名 + Cloudflare = 入站 TLS 按 SNI 被拦
- 出站隧道是正解

### Cloudflare Origin Certificate 只能在 CF 后面用
直连源站会报证书错误（正常行为，不是 bug）

## 🏗️ 当前最终架构

```
用户 → Cloudflare 边缘 (终结 TLS) → 出站隧道 QUIC → 本机 cloudflared
                                      → 按域名分流：
                                          finance.cloveh.online → 24800 → frp → Actual Budget
                                          dh.cloveh.online → 8081 → nginx → /i/、/api/upload→Picsur
                                                                          → / → 65535 → frp → 闲鱼
```

nginx 的 443 配置已退役（外网走隧道，不走 443 了）

## ⚠️ 遗留事项（之前体检记的，还没处理）

1. frps 后台密码 `admin/admin123` 太弱，建议改
2. 7000/7500/24800 端口没做 iptables 回环锁定（不过现在走隧道，24800 只被本机访问，风险已大减；7000 是 frpc 连接口需保持开放）
3. Picsur 容器 docker 显示 unhealthy（实际能用，可看下健康检查）
4. 之前留下的 sites-available 残留配置（dh.cloveh.online-frp 等）可清理

## 🔗 关联笔记
- [[FRP-Nginx内网穿透与HTTPS配置]]
- [[Cloudflare Tunnel 配置指南]]
- [[阿里云 WAF SNI 拦截排查]]

---
> 📋 **转换日志**：
> - [+] 新增从对话记录提取的结构化复盘
> - [+] 补充 Cloudflare 凭证三兄弟认知表
> - [+] 补充 SNI 拦截原理说明
> - [+] 更新最终架构图
> - [~] 结构化重组到标准区块（时间线→问题→认知→架构→遗留）
