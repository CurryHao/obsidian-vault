#!/bin/bash
# N2 自测流程 - DeepTutor 自动化脚本
# 用途：自动生成自测题目并保存到知识库

set -e

VAULT_DIR="$HOME/桌面/TechVault/日语"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$VAULT_DIR/日志/${DATE}-N2自测-DeepTutor.md"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== N2 诊断性自测 (DeepTutor 版) ===${NC}"
echo ""
echo -e "${YELLOW}步骤 1: 创建自测会话${NC}"
echo "请打开 DeepTutor: http://localhost:3782"
echo "创建一个新对话，标题: N2诊断自测-${DATE}"
echo ""

# 生成 Prompt 模板
PROMPT_TEMPLATE=$(cat << 'EOF'
你是一位专业的 JLPT N2 考试教练。现在我要做诊断性自测，请帮我完成以下步骤：

## 自测要求
1. 文法 30 题（从 N2 核心语法中随机抽）
2. 词汇 30 题（从 N2 高频词中随机抽）
3. 汉字 20 题（音读/训读/用法）

## 考试规则
- 每次只出一题，等我回答后再出下一题
- 不要提前给出答案或解析
- 所有题目出完后，统一批改并统计得分
- 对错题进行深度解析，指出常见混淆点
- 最后输出薄弱点分析报告

## 开始
请先出第 1 道文法题。
EOF
)

echo -e "${YELLOW}步骤 2: 复制以下 Prompt 到 DeepTutor${NC}"
echo ""
echo "─────────────────────────────────────"
echo "$PROMPT_TEMPLATE"
echo "─────────────────────────────────────"
echo ""

# 创建日志文件模板
cat > "$LOG_FILE" << EOF
---
date: ${DATE}
type: self-assessment
tool: deeptutor
status: in_progress
grammar_score: null
vocabulary_score: null
kanji_score: null
total: null
priority_high: []
priority_medium: []
priority_low: []
---

# N2 诊断自测报告（DeepTutor 版）

## 得分汇总
_（自测完成后填写）_

## 薄弱点分析
_（从 DeepTutor 分析复制）_

## Phase 1 调整建议
_（从 DeepTutor 建议复制）_

## 待补充笔记
_（从 DeepTutor 清单复制）_
EOF

echo -e "${GREEN}✓ 日志文件已创建：${LOG_FILE}${NC}"
echo ""
echo -e "${YELLOW}步骤 3: 完成自测后${NC}"
echo "1. 将 DeepTutor 的批改结果复制到日志文件"
echo "2. 更新 [[计划/知识缺口清单]]"
echo "3. 更新 [[计划/00 看板]] 的阻塞点"
echo ""
echo -e "${GREEN}开始吧！祝你测试顺利！${NC}"
