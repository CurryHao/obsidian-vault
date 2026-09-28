---
tags: [ragas, document-format, markdown, preprocessing, input-prep]
created: 2026-09-07
updated: 2026-09-07
---

# ragas 输入文档格式：Markdown 为何显著优于 PDF/TXT

## 一、核心论点
测试集质量**极其依赖**底层知识图谱构建（KG Building）与转换流水线（Transforms Pipeline）。相比 PDF / TXT，Markdown 在三个环节具备**决定性优势**。

## 二、优势 1：完美契合 HeadlineSplitter
- Ragas 默认推荐 **`HeadlineSplitter`**（基于标题的切分器）
- 切分流程：源文档（`NodeType.DOCUMENT`）→ 文本块节点（`NodeType.CHUNK`）→ 层级节点树
- Markdown 优势：
  - 天然、极度规范的标题层级标记（`#` / `##` / `###`）
  - `HeadlineSplitter` 精准识别章节边界
  - 语义紧密相关的段落完整切到同一 Chunk
- 其他格式劣势：
  - TXT / Word / 复杂 PDF 缺乏统一结构化标题标记
  - 易造成上下文信息割裂与碎片化

## 三、优势 2：显著提升 Extractor Accuracy
Ragas 提取器在切分节点上抽取核心特征并写入 `properties`：
- `NERExtractor` —— 命名实体识别
- `KeyphrasesExtractor` —— 关键短语

Markdown 排版帮助 LLM 理解上下文关联：
- 列表（`-` / `*`）
- 加粗（`**`）
- 表格

→ 提取出**更有价值、更具代表性的关键短语和实体组合**

## 四、优势 3：直接决定多跳关系链构建质量
- 关系构建器（`OverlapScoreBuilder` / `JaccardSimilarityBuilder`）基于提取的特征计算节点相似度并连线
- Markdown 输入下：
  - 切片语义完整（前两步产出质量高）
  - 特征精准
  - 关系构建器能建立**逻辑强、噪音极低的关系链**
- 直接确保 `MultiHopQuerySynthesizer` 遍历图谱时：
  - 组合出**极具逻辑推理深度**的多跳样本
  - 提问风格**自然**（接近人类习惯）

## 五、最佳实践：源文档预处理
PDF / DOCX / HTML → 统一转换为**干净的 Markdown** → 输入 Ragas

推荐工具：
- `pandoc`
- `markitdown`

目标：从源头避免文本切分混乱，让生成测试集在**合理性、逻辑性、多样性**上都达到最优。

## 六、关键概念速查
| 概念 | 说明 |
|------|------|
| KG Building | 知识图谱构建 |
| Transforms Pipeline | 转换流水线 |
| HeadlineSplitter | 基于标题的切分器（默认推荐） |
| NERExtractor | 命名实体识别提取器 |
| KeyphrasesExtractor | 关键短语提取器 |
| properties | 节点特征属性（提取结果写入处） |
| pandoc | 通用文档格式转换工具 |
| markitdown | 微软出品的文档转 Markdown 工具 |

## 七、相关笔记

- 前置：本文是 RAG 评测生命周期的**第一步**
- 后续：[[02-测试集生成-多跳查询与知识图谱构建]] — 接收本文输出的 Markdown 文档进行知识图谱构建与多跳 Q&A 合成
- 索引：[[_MOC-ragas|🗺️ Ragas 知识地图]]

> **为什么独立成篇**：本文解决「输入端」文档准备问题，与「生成端」「评估端」在生命周期中位置不同，混在一起会让读者难以按需定位。
