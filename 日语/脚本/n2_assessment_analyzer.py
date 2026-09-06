#!/usr/bin/env python3
"""
N2 自测结果自动分析器
用途：读取 DeepTutor 对话记录，提取得分和薄弱点，更新知识库
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

def parse_assessment_result(content: str) -> dict:
    """解析自测结果"""
    result = {
        'grammar_score': None,
        'vocabulary_score': None,
        'kanji_score': None,
        'total_score': None,
        'weak_points': [],
        'phase1_suggestions': [],
        'notes_to_add': []
    }
    
    # 提取得分
    grammar_match = re.search(r'文法[：:]\s*(\d+)/30', content)
    if grammar_match:
        result['grammar_score'] = int(grammar_match.group(1))
    
    vocabulary_match = re.search(r'词汇[：:]\s*(\d+)/30', content)
    if vocabulary_match:
        result['vocabulary_score'] = int(vocabulary_match.group(1))
    
    kanji_match = re.search(r'汉字[：:]\s*(\d+)/20', content)
    if kanji_match:
        result['kanji_score'] = int(kanji_match.group(1))
    
    total_match = re.search(r'总分[：:]\s*(\d+)/80', content)
    if total_match:
        result['total_score'] = int(total_match.group(1))
    
    # 提取薄弱点
    weak_section = re.search(r'薄弱点分析[：:]\s*\n((?:- .+\n?)*)', content)
    if weak_section:
        result['weak_points'] = [line.strip('- ').strip() for line in weak_section.group(1).split('\n') if line.strip()]
    
    return result

def update_knowledge_gap(result: dict, vault_dir: Path):
    """更新知识缺口清单"""
    gap_file = vault_dir / '计划' / '知识缺口清单.md'
    
    if not gap_file.exists():
        print(f"⚠️  知识缺口清单不存在：{gap_file}")
        return
    
    with open(gap_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 添加新的薄弱点
    for point in result['weak_points'][:5]:  # 只添加前5个
        if point not in content:
            # 根据内容判断应该添加到哪个section
            if '文法' in point or '语法' in point:
                section = '## 文法缺口'
            elif '词汇' in point or '惯用语' in point:
                section = '## 词汇缺口'
            elif '汉字' in point:
                section = '## 汉字缺口'
            else:
                section = '## 文法缺口'
            
            # 找到section位置并插入
            if section in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line == section:
                        # 在section后插入
                        insert_pos = i + 1
                        while insert_pos < len(lines) and lines[insert_pos].startswith('-'):
                            insert_pos += 1
                        lines.insert(insert_pos, f'- [ ] {point}')
                        content = '\n'.join(lines)
                        break
    
    with open(gap_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新知识缺口清单")

def update_dashboard(result: dict, vault_dir: Path):
    """更新看板"""
    dashboard = vault_dir / '计划' / '00 看板.md'
    
    if not dashboard.exists():
        print(f"⚠️  看板不存在：{dashboard}")
        return
    
    with open(dashboard, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 添加自测发现到阻塞点
    date = datetime.now().strftime('%Y-%m-%d')
    discovery = f"\n### 自测发现（{date}）\n"
    
    if result['grammar_score'] is not None:
        if result['grammar_score'] < 18:  # <60%
            discovery += f"- 🔴 文法薄弱：得分 {result['grammar_score']}/30\n"
        elif result['grammar_score'] < 24:  # <80%
            discovery += f"- 🟡 文法中等：得分 {result['grammar_score']}/30\n"
        else:
            discovery += f"- 🟢 文法良好：得分 {result['grammar_score']}/30\n"
    
    if result['vocabulary_score'] is not None:
        if result['vocabulary_score'] < 18:
            discovery += f"- 🔴 词汇薄弱：得分 {result['vocabulary_score']}/30\n"
        elif result['vocabulary_score'] < 24:
            discovery += f"- 🟡 词汇中等：得分 {result['vocabulary_score']}/30\n"
        else:
            discovery += f"- 🟢 词汇良好：得分 {result['vocabulary_score']}/30\n"
    
    if result['total_score'] is not None:
        if result['total_score'] < 48:  # <60%
            discovery += f"- 🔴 总分偏低：{result['total_score']}/80，需加强Phase 1学习\n"
        elif result['total_score'] < 64:  # <80%
            discovery += f"- 🟡 总分中等：{result['total_score']}/80\n"
        else:
            discovery += f"- 🟢 总分良好：{result['total_score']}/80\n"
    
    # 在阻塞点section后插入
    if '## 🚨 阻塞点 & 待办' in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '## 🚨 阻塞点 & 待办' in line:
                # 找到Phase 0部分
                for j in range(i, min(i+20, len(lines))):
                    if '### Phase 0' in lines[j]:
                        # 在Phase 0的待办后插入
                        for k in range(j+1, min(j+10, len(lines))):
                            if lines[k].strip().startswith('- [ ]'):
                                insert_pos = k + 1
                                lines.insert(insert_pos, discovery)
                                content = '\n'.join(lines)
                                break
                        break
                break
    
    with open(dashboard, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新看板")

def main():
    if len(sys.argv) < 2:
        print("用法: python3 n2_assessment_analyzer.py <deep_tutor_result.md>")
        print("")
        print("示例:")
        print("  python3 n2_assessment_analyzer.py ~/桌面/TechVault/日语/日志/2026-09-03-N2自测.md")
        sys.exit(1)
    
    result_file = Path(sys.argv[1])
    vault_dir = result_file.parent.parent.parent  # 向上3级到日语目录
    
    if not result_file.exists():
        print(f"❌ 文件不存在：{result_file}")
        sys.exit(1)
    
    with open(result_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"📊 正在分析自测结果：{result_file.name}")
    
    result = parse_assessment_result(content)
    
    print(f"\n【分析结果】")
    print(f"  文法：{result['grammar_score']}/30" if result['grammar_score'] else "  文法：未提取")
    print(f"  词汇：{result['vocabulary_score']}/30" if result['vocabulary_score'] else "  词汇：未提取")
    print(f"  汉字：{result['kanji_score']}/20" if result['kanji_score'] else "  汉字：未提取")
    print(f"  总分：{result['total_score']}/80" if result['total_score'] else "  总分：未提取")
    
    if result['weak_points']:
        print(f"\n【薄弱点】")
        for point in result['weak_points'][:5]:
            print(f"  - {point}")
    
    # 更新知识库
    update_knowledge_gap(result, vault_dir)
    update_dashboard(result, vault_dir)
    
    print(f"\n✅ 分析完成！")

if __name__ == '__main__':
    main()
