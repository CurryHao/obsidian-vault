---
tags: [MOC, locust, performance-testing]
created: 2026-07-30
---

# 🗺️ Locust 知识地图

> 共 71 篇笔记 | 🟡 持续完善中

## 🌱 入门基础

| 笔记 | 一句话概括 |
|------|-----------|
| [[Locust分布式架构概览与核心组件]] | Master-Worker 星型拓扑，ZeroMQ 协调-执行分离设计 |
| [[与JMeter、Gatling等主流工具的核心差异]] | Locust vs JMeter vs Gatling：协程模型、Python脚本化、分布式轻量 |
| [[gevent协程模型与异步并发优势]] | gevent 绿色线程，单机万级并发，同步写法异步执行 |
| [[命令行基础启动参数与常用选项]] | CLI 参数速查：-f/-H/-u/-r/--headless/--master/--worker 全选项 |

## 👤 用户与任务模型

| 笔记 | 一句话概括 |
|------|-----------|
| [[HttpUser基类与Web请求能力绑定]] | 注入HttpSession，自动统计，Cookie/Headers持久化 |
| [[User类属性定义与作用域]] | host/tasks/wait_time 配置与实例级隔离 |
| [[负载权重（weight）与多用户类型混合策略]] | 多 User 类混合运行，weight 权重分配模拟用户比例 |
| [[on_start与on_stop生命周期钩子方法]] | 用户生命周期控制：on_start 初始化，on_stop 清理 |
| [[用户退出条件与测试运行时长控制]] | stop() 控制退出条件，与 run_time 协同机制 |
| [[task装饰器定义与任务权重分配]] | @task(weight)定义行为频率，优先级调度 |
| [[任务集嵌套与模块化行为拆分]] | TaskSet 嵌套实现登录→浏览→下单等模块化流程 |
| [[SequentialTaskSet实现顺序任务流]] | SequentialTaskSet 强制顺序执行，适配严格后端流程 |
| [[动态任务选择与任务跳过机制]] | 基于状态条件动态选择/跳过 task |

## 🔗  HTTP 请求与客户端

| 笔记 | 一句话概括 |
|------|-----------|
| [[请求头与会话状态持久化]] | Headers 全局设置，Cookie/Token 自动保持 |
| [[连接超时与全局超时设定]] | connect_timeout / network_timeout / request_timeout 三级超时 |
| [[文件上传与二进制流处理]] | multipart/form-data 文件上传 + 二进制 body 处理 |
| [[连接池复用与Keep-Alive长连接管理]] | requests.session 中连接池参数调优 |
| [[继承BaseClient实现WebSocket协议压测]] | 专长 BaseClient + ws4py 实现 WebSocket 压力 |
| [[请求拦截器与预处理钩子]] | request event hook 实现签名/鉴权等预处理 |

## ⏱️ 等待策略与节奏控制

| 笔记 | 一句话概括 |
|------|-----------|
| [[内置等待策略]] | between / constant / constant_pacing 三大策略对比 |
| [[等待时间与并发用户数的协同关系]] | wait_time × users 与吞吐量的数学关系 |
| [[指数分布与均匀分布对压力曲线的影响]] | wait_time 选择对负载平滑度的直接影响 |
| [[自定义等待时间函数实现复杂业务节拍]] | 自定义 wait_time 函数模拟非均匀用户行为 |
| [[固定步长与吞吐量精准限制]] | constant_pacing 以固定频率发请求，精确 RPS 控制 |
| [[用户思维与任务执行间隔关联]] | 真实用户的思考时间建模与任务间隔设计 |

## 🌐 分布式集群

| 笔记 | 一句话概括 |
|------|-----------|
| [[Master-Worker架构通信机制与零MQ基础]] | ZeroMQ 双端口 5557/5558 协议与心跳机制 |
| [[分布式启动命令]] | Master/Worker 启动参数、指定主机 IP 与预计 worker 数 |
| [[工作节点数量规划与哈希任务分片策略]] | Worker 数规划论按 CPU 核数，Round-Robin/hash 任务分片 |
| [[分布式场景下的统计归并与数据一致性保证]] | 增量定时上报，错峰同步，统计归并策略 |
| [[主节点容灾与工作节点心跳保活机制]] | 心跳超时断口重连 + Master 失效应急 |
| [[多Worker节点状态监控与异常节点隔离]] | CPU/内存实时监控，假死/无效 Worker 自动隔离 |
| [[分布式通信故障与主从同步延迟诊断]] | ZeroMQ 大包丢弃、延迟异常、版本兼经诊断 |
| [[工作节点注册与注销事件处理]] | worker_register / worker_unregister 运行时回调处理 |

## 📈 负载形状与运行时控制

| 笔记 | 一句话概括 |
|------|-----------|
| [[LoadTestShape基类与核心tick方法重写]] | tick() 返回 (user_count, spawn_rate) 控制瞬态负载 |
| [[阶梯式、波浪式、脉冲式负载曲线构建]] | 阶梯式周期递增，罐式正弦波动，脉冲干峰 |
| [[基于时间维度的复杂并发变更策略]] | run_time 内多阶段负载与高级模式组合 |
| [[结合外部数据源动态调整负载形状]] | Live Prometheus 信号驱动动态用户数 |
| [[自定义形状与命令行参数联合控制执行]] | LoadShape + headless/log 命令行传参控制形态 |
| [[自动停止条件设置与退出码]] | shape.is_stop 与 --exit-code-on-error |
| [[运行时动态调整并发与限流]] | WebUI / 环境变量动态调整 users/spawn_rate |
| [[无界面常用参数]] | --headless/-u/-r/-t/--stop-timeout CI 常用参考 |
| [[标签过滤选择性执行]] | --tags / --exclude-tags 组合选择性运行 |
| [[手动启停重置测试与用户数动态调整]] | WebUI Start/Stop/Reset + Hatch 自定义 users |

## 📊 监控与可观测性

| 笔记 | 一句话概括 |
|------|-----------|
| [[Web仪表盘核心指标解读]] | 实时 RPS / 峰值 / 百分位指标及各图详解 |
| [[实时折线图与百分位数分析]] | P50/P95/P99 曲线走势与告警阈值分析 |
| [[异常请求明细查看与快速定位]] | 点击 Transactions → 请求列表 → 展开原始内容 |
| [[test_start与test_stop全局事件监听]] | 主控进程级全局前置/后置事件钩子 |
| [[请求成功与失败回调]] | on_success_callback 与 on_failure_callback 灵活介入 |
| [[初始化与清理阶段控制]] | init 流程 + 周期级初始/清理回环控制 |
| [[自定义统计数据聚合与事件上报扩展]] | Events.request.fire 形成 StatsEntry 自定义插装 |
| [[响应时间阈值断言与SLA合规性校验]] | 阈值拦截 + --fail-ratio 错误比率违规 |
| [[断言失败后的行为控制]] | catch_response=True 配合 success/failure 自定义标记 |
| [[内置状态码校验与异常自动捕获]] | <400 的 success 定义 + 异常自动捕获 |

## 🔌 集成与部署运维

| 笔记 | 一句话概括 |
|------|-----------|
| [[Prometheus指标导出与Grafana监控大盘构建]] | locust_exporter → Prometheus → Grafana 数据持久化 |
| [[InfluxDB持久化存储与历史趋势对比]] | InfluxDB 持久化存储历史数据对比分析 |
| [[HTML分布式报告下载与聚合分析]] | --html + 报告合并与整合分析 |
| [[SV统计报告生成]] | --csv 生成 CSV 统计档与进一步加工 |
| [[docker-compose编排Master-Worker分布式集群]] | docker-compose 编排 runner 容器方案 |
| [[Kubernetes部署资源配置]] | ConfigMap 挂机，HPA 动态扩容，sidecar 监控 |
| [[GitHubActions、GitLabCI、Jenkins流水线模板配置]] | GitHub CI + Jenkins 批量生或配置 |
| [[定时任务与夜间回归压测调度]] | Cron + 一键 locust headless + Web 自动报告通知 |
| [[基准测试结果对比与性能回归阈值设定]] | baseline 定期自动化基线比较与 slack 告警 |
| [[性能测试左移与代码MR质量门禁]] | PR/MR 时自动发送轻量测试，MR 继续 |
| [[CPU内存网络带宽瓶颈识别与扩容策略]] | CPU/Memory 80% 保护 + 弹性扩容 |
| [[Worker数量与目标系统负载能力的平衡计算]] | Worker 量 = (目标 RPS * 平均响应时间) |
| [[PythonGIL影响与多进程部署替代方案]] | CPython GIL 限制，多 Worker 替代 multiprocessing |
| [[内存泄漏定位与长时运行稳定性优化]] | tracemalloc/pympler + gevent 泄漏全面检查与修复 |
| [[系统ulimit与文件描述符上限调优]] | ulimit ./n 端口和维护大 FD 上限 |

## 🆕 新补充

| 笔记 | 一句话概括 |
|------|-----------|
| [[FastHttpUser与HttpUser对比与性能选择指南]] | FastHttpUser(C/gevent) vs HttpUser(requests)：10x 吞吐，API 兼容 |
| [[测试数据参数化与CSV驱动的真实负载建模]] | Queue/cycle 循环分发 CSV/JSON 数据，多用户唯一数据避免冲突 |
| [[自定义事件Hook系统与高级统计扩展]] | events.request/init/test_start 7 大钩点，自定义 StatsEntry 扩展统计
