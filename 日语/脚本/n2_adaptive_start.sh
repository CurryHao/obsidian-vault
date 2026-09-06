#!/bin/bash
# N2 自适应自测启动器
# 用途：根据上次测试结果，推荐本次测试策略

set -e

VAULT_DIR="$HOME/桌面/TechVault/日语"
HISTORY_FILE="$VAULT_DIR/计划/自测历史记录.json"
DATE=$(date +%Y-%m-%d)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== N2 自适应自测启动器 ===${NC}"
echo ""

# 检查历史记录
if [ ! -f "$HISTORY_FILE" ]; then
    echo -e "${YELLOW}📊 首次自测${NC}"
    echo "没有找到历史记录，建议从基础难度开始。"
    echo ""
    RECOMMENDED_MODE="baseline"
else
    # 读取最近一次测试的三个模块水平,取最低水平作为推荐依据
    LEVEL_INFO=$(python3 -c "
import json, sys
try:
    with open('$HISTORY_FILE') as f:
        data = json.load(f)
    a = data.get('assessments', [])
    if not a:
        print('N? N? N?')
        sys.exit()
    last = a[-1]
    g = last.get('grammar') or {}
    v = last.get('vocabulary') or {}
    k = last.get('kanji') or {}
    print(g.get('final_level', 'N?'), v.get('final_level', 'N?'), k.get('final_level', 'N?'))
except Exception as e:
    print('N? N? N?', file=sys.stderr)
" 2>/dev/null)
    LEVEL_INFO="${LEVEL_INFO:-N? N? N?}"
    read -r LAST_GRAMMAR LAST_VOCAB LAST_KANJI <<< "$LEVEL_INFO"

    echo -e "${BLUE}📊 最近自测结果（${DATE}）${NC}"
    echo "  文法：$LAST_GRAMMAR"
    echo "  词汇：$LAST_VOCAB"
    echo "  汉字：$LAST_KANJI"
    echo ""

    # 按最低模块水平推荐模式(防止"只有 vocab 测到 N3 就推 adaptive"的陷阱)
    # N5=1 N4=2 N3=3 N2=4
    MIN_LEVEL=$(python3 -c "
levels = {'$LAST_GRAMMAR': 1, '$LAST_VOCAB': 1, '$LAST_KANJI': 1}
# 用上面映射算最低分,默认按 N5=1 起步
mapping = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4}
scores = [mapping.get(l, 1) for l in ['$LAST_GRAMMAR', '$LAST_VOCAB', '$LAST_KANJI']]
print(min(scores))
" 2>/dev/null)

    if [ "$MIN_LEVEL" -ge 4 ]; then
        RECOMMENDED_MODE="sprint"
        echo -e "${GREEN}✓ 推荐模式：考前冲刺${NC}"
        echo "  三项均达 N2,进行真题模拟测试"
    elif [ "$MIN_LEVEL" -ge 3 ]; then
        RECOMMENDED_MODE="adaptive"
        echo -e "${YELLOW}→ 推荐模式：自适应测试${NC}"
        echo "  最低模块已达 N3,通过自适应精准定位"
    else
        RECOMMENDED_MODE="baseline"
        echo -e "${BLUE}☆ 推荐模式：基础摸底${NC}"
        echo "  从 N4/N5 基础开始,逐步提升"
    fi
fi

echo ""
echo -e "${GREEN}════════════════════════════════${NC}"
echo -e "${GREEN}开始自测${NC}"
echo -e "${GREEN}════════════════════════════════${NC}"
echo ""

# 生成对应的 Prompt
case $RECOMMENDED_MODE in
    "sprint")
        PROMPT=$(cat << 'EOF'
你是一位专业的 JLPT N2 考试教练。我需要进行考前冲刺模拟测试。

## 测试要求
1. 文法 30 题（N2 真题难度，混合所有语法点）
2. 词汇 30 题（N2 高频词，含惯用语）
3. 汉字 20 题（N2 音读/训读/用法）

## 测试规则
- 每 10 题暂停一次，让我提交答案
- 暂停时显示当前正确率
- 全部完成后，生成详细分析报告
- 报告包括：得分、薄弱点、冲刺建议

## 开始
请先出第 1 道文法题。
EOF
)
        ;;
    "adaptive")
        PROMPT=$(cat << 'EOF'
你是一位专业的 JLPT N2 考试教练，采用自适应测试方法。

## 测试规则
1. 从 N4 基础语法开始，逐步提升到 N2 难度
2. 每 5 题暂停一次，询问我是否继续或调整难度
3. 如果我连续答对 3 题，下一轮提高难度
4. 如果我连续答错 2 题，下一轮降低难度或回到基础
5. 每个模块先做 15 题摸底，表现好再加量到 30 题

## 测试模块
1. 文法（从 N4 开始）
2. 词汇（从常见词开始）
3. 汉字（从基础读音开始）

## 开始
请先出第 1 道文法题（N4 难度）。
EOF
)
        ;;
    "baseline")
        PROMPT=$(cat << 'EOF'
你是一位专业的 JLPT N2 考试教练。我需要做一次基础摸底测试。

## 测试要求
1. 文法 15 题（从 N5 基础开始，逐步到 N4）
2. 词汇 15 题（从常见词开始）
3. 汉字 10 题（从基础音读开始）

## 测试规则
- 每 5 题后暂停，告诉我当前正确率
- 如果正确率 >80%，可以提升难度
- 如果正确率 <50%，可以降回基础
- 测试结束后，告诉我你的判断：我的水平大概在什么等级？

## 开始
请先出第 1 道文法题（N5 难度）。
EOF
)
        ;;
esac

echo -e "${YELLOW}请在 DeepTutor 中复制以下 Prompt:${NC}"
echo ""
echo "─────────────────────────────────────"
echo "$PROMPT"
echo "─────────────────────────────────────"
echo ""

# 创建日志文件
LOG_FILE="$VAULT_DIR/日志/${DATE}-N2自测-${RECOMMENDED_MODE}.md"
cat > "$LOG_FILE" << EOF
---
date: ${DATE}
type: self-assessment
tool: deeptutor
mode: ${RECOMMENDED_MODE}
status: in_progress
grammar:
  final_level: null
  questions: null
  correct: null
vocabulary:
  final_level: null
  questions: null
  correct: null
kanji:
  final_level: null
  questions: null
  correct: null
---

# N2 自测报告（${RECOMMENDED_MODE} 模式）

## 测试设置
- 模式：${RECOMMENDED_MODE}
- 文法：${PROMPT_PREVIEW}
- 预计时长：30-60 分钟

## 测试过程记录

### 文法部分
_（记录每轮难度和正确率）_

### 词汇部分
_（记录每轮难度和正确率）_

### 汉字部分
_（记录每轮难度和正确率）_

## 最终结果
_（从 DeepTutor 分析报告复制）_

## 待补充笔记
_（从 DeepTutor 清单复制）_
EOF

echo -e "${GREEN}✓ 日志文件已创建：${LOG_FILE}${NC}"
echo ""
echo -e "${YELLOW}测试完成后,运行以下命令更新记录:${NC}"
echo "python3 ~/桌面/TechVault/日语/脚本/n2_assessment_tracker.py add \\"
echo "  --date $DATE --mode $RECOMMENDED_MODE \\"
echo "  --grammar-level <N2/N3/N4/N5> --grammar-correct <对> --grammar-total <总数> \\"
echo "  --vocab-level <N2/N3/N4/N5>   --vocab-correct <对>   --vocab-total <总数> \\"
echo "  --kanji-level <N2/N3/N4/N5>   --kanji-correct <对>   --kanji-total <总数>"
echo "  (任一模块若没测,省略对应三件套即可)"
echo ""
echo -e "${GREEN}开始吧！祝你测试顺利！${NC}"
