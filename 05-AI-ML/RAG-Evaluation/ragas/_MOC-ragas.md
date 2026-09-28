---
tags: [MOC, ragas, RAG-evaluation]
created: 2026-09-07
updated: 2026-09-07
---

# 🗺️ Ragas 知识地图

> 共 3 篇笔记 · 🟢 起步阶段

Ragas = RAG 评估框架。当前笔记围绕**测试集生成与质量评估**展开，按 RAG 评测的**生命周期**组织：输入准备 → 测试集生成 → 质量评估。

## 🔄 完整生命周期

```
[源文档] → 1.输入准备 → 2.测试集生成 → 3.质量评估 → [可用测试集]
                                       ↓
                              用于评估 RAG 系统
```

## 📑 笔记索引

### 1️⃣ 输入准备（前置）

| 笔记 | 一句话概括 |
|------|-----------|
| [[01-输入准备-文档格式与Markdown优势]] | Markdown 格式在 HeadlineSplitter / 特征提取 / 关系构建三环节的天然优势，及 PDF/DOCX 的预处理最佳实践 |

### 2️⃣ 测试集生成（核心）

| 笔记 | 一句话概括 |
|------|-----------|
| [[02-测试集生成-多跳查询与知识图谱构建]] | 跨文档关系链构建 → 节点对检索 → LLM 跨文档推理合成 Q&A 的完整链路 |

### 3️⃣ 质量评估（后置）

| 笔记 | 一句话概括 |
|------|-----------|
| [[03-质量评估-多跳测试集元评估与清洗]] | 自检清洗（Faithfulness/Relevancy）+ 多跳逻辑退化过滤 + 多样性审计 + 人工抽样四大黄金方法 |

## 🔗 笔记交叉引用

```
01-输入准备 ──→ 02-测试集生成 ──→ 03-质量评估
   (源)            (生成)            (清洗)
```

- 01 → 02：Markdown 切片质量决定知识图谱构建质量
- 02 → 03：多跳生成产出后必须经过元评估清洗才能用于评测
- 03 → 02：评估指标（Faithfulness / Answer Relevancy）是 ragas 自检工具

## 🧩 待补充方向（占位）

- [ ] 单跳查询生成（与多跳并列）
- [ ] Persona-based 测试集生成
- [ ] Evolution-based 测试集生成
- [ ] Ragas 评估指标体系（横向支撑：Faithfulness / Answer Relevancy / Context Precision 等详解）
- [ ] 自定义指标开发
- [ ] 实际 RAG 系统评估流程（与测试集生成的衔接）

## 📌 速查：Ragas 核心对象

| 对象 | 作用 |
|------|------|
| `KnowledgeGraph` | 知识图谱，承载文档-块-关系三层结构 |
| `NodeType.DOCUMENT` | 源文档节点 |
| `NodeType.CHUNK` | 切分后的文本块节点 |
| `Relationship` | 节点间关系边 |
| `Scenario` | 节点对对应的生成场景 |
| `user_input` | 生成的问题 |
| `reference_contexts` | 参考上下文 |
| `reference` | 黄金标准答案 |

## 🛠️ 速查：核心组件

| 组件 | 作用 |
|------|------|
| `HeadlineSplitter` | 基于标题的切分器（默认推荐） |
| `NERExtractor` | 命名实体识别提取器 |
| `KeyphrasesExtractor` | 关键短语提取器 |
| `OverlapScoreBuilder` | 重叠度关系构建器 |
| `JaccardSimilarityBuilder` | Jaccard 相似度关系构建器 |
| `MultiHopQuerySynthesizer` | 多跳查询合成器 |
| `pandoc` / `markitdown` | 文档转 Markdown 工具 |
