---
tags: [MOC, pytest, testing]
created: 2026-07-29
---

# 🗺️ Pytest 知识地图

> 共 38 篇笔记 | 🟡 持续完善中

## 🌱 入门基础

| 笔记                      | 一句话概括                    |
| ----------------------- | ------------------------ |
| [[pytest设计哲学内核]]        | pytest 优于 unittest 的设计理念 |
| [[pytest自动发现机制]]        | 文件/函数/类的命名约定与收集规则        |
| [[Python测试框架谱系对比]]      | 各测试框架对比与选型               |
| [[unittest迁移到pytest实战]] | 从 unittest 平滑迁移的策略与工具    |
| [[pytest命令行参数详解]]       | 常用参数速查：选择器/执行控制/输出/调试    |

## 🔧 Fixture 体系

| 笔记 | 一句话概括 |
|------|-----------|
| [[Fixture定义语法与自动使用]] | `@pytest.fixture` 声明、`autouse` 与 `yield` 清理 |
| [[Fixture相互依赖与工厂模式实现]] | Fixture 之间如何嵌套组合 |
| [[内置作用域层级]] | session/package/module/class/function 五级作用域 |
| [[内置实用Fixture]] | `tmp_path`、`capsys`、`request` 等内置 Fixture 详解 |
| [[conftest.py的共享机制与作用域隔离]] | 多层级 conftest 的全局/局部 Fixture 共享 |
| [[conftest黑魔法核心]] | conftest 的插件化能力与内部机制 |

## ⚡ 参数化

| 笔记 | 一句话概括 |
|------|-----------|
| [[单参数与多参数笛卡尔积组合]] | `@pytest.mark.parametrize` 单层与堆叠用法 |
| [[参数化堆叠与动态参数值生成]] | 多个 parametrize 叠加的笛卡尔积组合策略 |
| [[间接参数化（indirect）与Fixture联动]] | `indirect=True` 将参数注入 Fixture |
| [[自定义参数化ID与测试可读性优化]] | 通过 `ids` 参数让测试报告更清晰 |
| [[数据驱动测试与测试工厂（Factory）模式]] | 大规模数据驱动的架构设计 |

## 🏷️ 标记系统

| 笔记 | 一句话概括 |
|------|-----------|
| [[内置标记]] | skip/skipif/xfail/usefixtures 四大行为标记 |
| [[基于标记的条件执行与过滤筛选]] | 用 `-m` 参数灵活筛选标记组合 |
| [[自定义标记注册与业务语义映射]] | `pytest.ini` 注册标记及 CI 分层策略 |
| [[标记继承与类模块级别批量应用]] | 标记在类/模块级的继承与应用范围 |

## 🎯 断言与异常

| 笔记                             | 一句话概括                                    |
| ------------------------------ | ---------------------------------------- |
| [[assert语句的增强输出与重写原理]]         | assert 重写的 AST 级 Hook 机制                 |
| [[异常断言（pytest.raises）与异常文本匹配]] | `pytest.raises` 配合 `match` 正则精准捕获        |
| [[警告捕获与断言pytest.warns]]        | 用 `pytest.warns` 验证 DeprecationWarning 等 |
| [[自定义断言辅助函数与断言插件扩展]]           | 断言辅助与插件式断言扩展                             |

## 🎭 Mock 与 Monkeypatch

| 笔记 | 一句话概括 |
|------|-----------|
| [[pytest-mock插件与unittest.mock无缝集成]] | `mocker` Fixture 的便捷 Mock 方式 |
| [[monkeypatch动态替换运行时对象与属性]] | 运行时替换环境变量、系统时间等 |
| [[模拟环境变量、系统时间与随机数种子]] | 环境隔离测试的三大场景 |
| [[模拟外部依赖]] | HTTP API、数据库等外部服务的 Mock 策略 |

## 📊 覆盖率

| 笔记 | 一句话概括 |
|------|-----------|
| [[pytest-cov配置与多模式报告生成]] | coverage 的 XML/HTML/终端报告 |
| [[排除代码（exclude）与覆盖率阈值设定]] | 排除非业务代码与设置最低覆盖率门禁 |
| [[增量覆盖率与质量门禁（Quality Gate）策略]] | 只统计新增代码覆盖率的 CI 实践 |

## 🚀 执行策略

| 笔记 | 一句话概括 |
|------|-----------|
| [[测试执行顺序与默认收集钩子]] | 默认排序规则与 `pytest_collection_modifyitems` |
| [[测试用例的Arrange-Act-Assert结构规范]] | AAA 模式的规范化实践 |
| [[分布式执行与测试分片（Sharding）策略]] | `pytest-xdist` 的并行与分片方案 |
| [[测试套件动态拆分与并行Pipeline设计]] | 按标记/目录智能拆分的 CI Pipeline |

## 🔌 CI & 插件

| 笔记 | 一句话概括 |
|------|-----------|
| [[主流CI平台配置模板]] | GitHub Actions / Jenkins / GitLab CI 模板 |
| [[插件发现机制与安装管理]] | 安装/激活/排查第三方插件 |
| [[Hook函数类型与自定义插件开发入门]] | `pytest_configure` 等核心 Hook 点 |

---

## 📌 学习路径建议

```
新手入门 →
  pytest设计哲学内核 → pytest自动发现机制 → pytest命令行参数详解
  → Fixture定义语法与自动使用 → 内置标记
  → 单参数与多参数笛卡尔积组合 → assert语句的增强输出与重写原理

进阶提升 →
  conftest.py的共享机制与作用域隔离 → 内置作用域层级
  → 间接参数化（indirect）与Fixture联动 → 异常断言
  → monkeypatch动态替换 → pytest-mock插件

高级实战 →
  自定义标记注册与业务语义映射 → 数据驱动测试与测试工厂模式
  → 分布式执行与测试分片 → 测试套件动态拆分与并行Pipeline设计
  → 增量覆盖率与质量门禁 → Hook函数类型与自定义插件开发入门

面试突击 →
  [待补充：面试热点提炼]
```

## ⚔️ 对比选型

| 对比主题 | 相关笔记 |
|----------|----------|
| pytest vs unittest | [[Python测试框架谱系对比]]、[[unittest迁移到pytest实战]] |
| Fixture 参数注入 vs usefixtures | [[Fixture定义语法与自动使用]] |
| skip vs xfail | [[内置标记]] |
| monkeypatch vs pytest-mock | [[monkeypatch动态替换运行时对象与属性]]、[[pytest-mock插件与unittest.mock无缝集成]] |
| pytest.raises vs xfail(raises=...) | [[异常断言（pytest.raises）与异常文本匹配]] |

## 🔮 待补充（知识缺口）

- [ ] Pytest 插件生态推荐（pytest-sugar, pytest-html, pytest-timeout 等）
- [ ] 测试分层策略（单元/集成/E2E 在 pytest 中的组织）
- [ ] 异步测试（pytest-asyncio）
- [ ] 性能测试与基准测试（pytest-benchmark）
- [ ] Django/Flask/FastAPI 应用的测试实践