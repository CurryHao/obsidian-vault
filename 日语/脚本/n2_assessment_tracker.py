#!/usr/bin/env python3
"""
N2 自适应自测记录器
用途：记录每次自测的水平变化，生成对比报告

用法:
  tracker.py add --date 2026-09-03 --mode adaptive \
                 --grammar N3 12 15 \
                 --vocab   N3 10 15 \
                 --kanji   N4  6 10
  tracker.py progress      # 列出所有自测,1 次也显示本次得分明细
  tracker.py report        # 生成首末对比报告(>=2 条)
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


LEVEL_SCORE = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4}
LEVEL_LABEL = {1: 'N5', 2: 'N4', 3: 'N3', 4: 'N2'}


def parse_module_args(args, prefix):
    """解析 --grammar LEVEL CORRECT TOTAL 这种三连位置参数"""
    level = getattr(args, f'{prefix}_level')
    correct = getattr(args, f'{prefix}_correct')
    total = getattr(args, f'{prefix}_total')
    if not level:
        return None
    if level not in LEVEL_SCORE:
        raise SystemExit(f"❌ {prefix} 等级必须是 N5/N4/N3/N2 之一,收到: {level}")
    if correct is None or total is None:
        raise SystemExit(f"❌ --{prefix} {level} 后面必须跟 <correct> <total> 两个数字")
    if correct < 0 or total <= 0:
        raise SystemExit(f"❌ --{prefix} 数值非法: correct={correct}, total={total}")
    if correct > total:
        raise SystemExit(f"❌ --{prefix} 正确数({correct})不能大于总数({total})")
    return {
        'final_level': level,
        'questions': total,
        'correct': correct,
        'accuracy': round(correct / total * 100, 1),
    }


def _fmt(m):
    if not m:
        return '(未测)'
    return f"{m['final_level']} ({m['correct']}/{m['questions']} = {m['accuracy']}%)"


def add_assessment(args, tracker):
    grammar = parse_module_args(args, 'grammar')
    vocab = parse_module_args(args, 'vocab')
    kanji = parse_module_args(args, 'kanji')

    if not any([grammar, vocab, kanji]):
        raise SystemExit("❌ 至少需要 --grammar / --vocab / --kanji 之一")

    assessment = {
        'date': args.date,
        'mode': args.mode,
        'grammar': grammar,
        'vocabulary': vocab,
        'kanji': kanji,
        'timestamp': datetime.now().isoformat(),
    }
    tracker.history['assessments'].append(assessment)
    tracker._update_stats(grammar, vocab, kanji)
    tracker.save_history()

    print(f"✓ 已记录 {args.date} 的自测结果")
    print(f"  文法: {_fmt(grammar)}")
    print(f"  词汇: {_fmt(vocab)}")
    print(f"  汉字: {_fmt(kanji)}")


def progress_view(tracker):
    assessments = tracker.history['assessments']
    if not assessments:
        print("📊 暂无自测记录")
        return

    print('\n' + '=' * 60)
    print('📊 N2 自测进度概览')
    print('=' * 60)

    for i, a in enumerate(assessments, 1):
        print(f"\n第 {i} 次 ({a['date']}) · 模式: {a['mode']}")
        for mod_key, mod_label in [('grammar', '文法'), ('vocabulary', '词汇'), ('kanji', '汉字')]:
            m = a.get(mod_key) or {}
            if not m:
                print(f"  {mod_label}: (未测)")
                continue
            acc = m.get('accuracy')
            acc_str = f" {m['correct']}/{m['questions']} ({acc}%)" if acc is not None else ""
            print(f"  {mod_label}: {m.get('final_level', 'N?')}{acc_str}")

    if len(assessments) >= 2:
        print('\n' + '-' * 60)
        print(tracker.generate_report())


def report_view(tracker):
    if len(tracker.history['assessments']) < 2:
        print("⚠️  需要至少 2 次自测数据才能生成对比报告")
        return
    print(tracker.generate_report())


class N2AssessmentTracker:
    def __init__(self, vault_dir: Path):
        self.vault_dir = vault_dir
        self.history_file = vault_dir / '计划' / '自测历史记录.json'
        self.load_history()

    def load_history(self):
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                try:
                    self.history = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"⚠️  历史文件损坏 ({self.history_file}): {e}", file=sys.stderr)
                    self.history = {'assessments': [], 'stats': {}}
        else:
            self.history = {'assessments': [], 'stats': {}}

    def save_history(self):
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def _update_stats(self, grammar, vocabulary, kanji):
        def get_level_score(level):
            return LEVEL_SCORE.get(level or '', 0)

        if 'trends' not in self.history['stats']:
            self.history['stats']['trends'] = {'grammar': [], 'vocabulary': [], 'kanji': []}

        last_date = self.history['assessments'][-1]['date']
        if grammar:
            self.history['stats']['trends']['grammar'].append({
                'date': last_date,
                'level': grammar['final_level'],
                'score': get_level_score(grammar['final_level']),
                'accuracy': grammar['accuracy'],
            })
        if vocabulary:
            self.history['stats']['trends']['vocabulary'].append({
                'date': last_date,
                'level': vocabulary['final_level'],
                'score': get_level_score(vocabulary['final_level']),
                'accuracy': vocabulary['accuracy'],
            })
        if kanji:
            self.history['stats']['trends']['kanji'].append({
                'date': last_date,
                'level': kanji['final_level'],
                'score': get_level_score(kanji['final_level']),
                'accuracy': kanji['accuracy'],
            })

    def generate_report(self) -> str:
        assessments = self.history['assessments']
        last = assessments[-1]
        first = assessments[0]

        report = f"""# 📊 N2 自测进度报告

## 测试概览
- 首次测试: {first['date']}
- 最近测试: {last['date']}
- 测试次数: {len(assessments)} 次

## 水平变化

| 模块 | 首次 | 最近 | 变化 |
|------|------|------|------|
"""

        for module, label in [('grammar', '文法'), ('vocabulary', '词汇'), ('kanji', '汉字')]:
            first_level = first[module].get('final_level', 'N?') if first.get(module) else 'N?'
            last_level = last[module].get('final_level', 'N?') if last.get(module) else 'N?'
            first_score = LEVEL_SCORE.get(first_level, 0)
            last_score = LEVEL_SCORE.get(last_level, 0)
            if first_level == last_level:
                change = '➡️  持平'
            elif last_score > first_score:
                change = '⬆️  进步'
            else:
                change = '⬇️  需巩固'
            report += f"| {label} | {first_level} | {last_level} | {change} |\n"

        report += "\n## 详细记录\n\n"
        for i, a in enumerate(assessments, 1):
            report += f"### 第 {i} 次 ({a['date']})\n"
            report += f"- 模式: {a['mode']}\n"
            for mod_key, label in [('grammar', '文法'), ('vocabulary', '词汇'), ('kanji', '汉字')]:
                m = a.get(mod_key) or {}
                if not m:
                    report += f"- {label}: (未测)\n"
                    continue
                acc = m.get('accuracy')
                acc_str = f", 正确率 {acc}%" if acc is not None else ""
                report += f"- {label}: {m.get('final_level', 'N?')} ({m.get('questions', 0)} 题, {m.get('correct', 0)} 对{acc_str})\n"
            report += "\n"

        return report


def main():
    parser = argparse.ArgumentParser(
        description='N2 自适应自测记录器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # add
    p_add = sub.add_parser('add', help='记录一次自测结果')
    p_add.add_argument('--date', required=True, help='测试日期 YYYY-MM-DD')
    p_add.add_argument('--mode', required=True, choices=['baseline', 'adaptive', 'sprint'],
                       help='测试模式: baseline=摸底, adaptive=自适应, sprint=冲刺')
    for mod, label in [('grammar', '文法'), ('vocab', '词汇'), ('kanji', '汉字')]:
        p_add.add_argument(f'--{mod}-level', metavar='LEVEL', help=f'{label} 等级 (N5/N4/N3/N2),不测则省略')
        p_add.add_argument(f'--{mod}-correct', type=int, metavar='CORRECT', help=f'{label} 正确数')
        p_add.add_argument(f'--{mod}-total', type=int, metavar='TOTAL', help=f'{label} 总题数')

    # progress
    sub.add_parser('progress', help='列出所有自测记录')

    # report
    sub.add_parser('report', help='生成首末对比报告(需要 >=2 条记录)')

    args = parser.parse_args()

    vault_dir = Path.home() / '桌面' / 'TechVault' / '日语'
    tracker = N2AssessmentTracker(vault_dir)

    # 把 --grammar-level/correct/total 重组为解析器期望的命名属性
    for mod in ['grammar', 'vocab', 'kanji']:
        setattr(args, f'{mod}_level', getattr(args, f'{mod}_level', None))
        setattr(args, f'{mod}_correct', getattr(args, f'{mod}_correct', None))
        setattr(args, f'{mod}_total', getattr(args, f'{mod}_total', None))

    # vocab 是别名,内部统一用 vocabulary
    if not hasattr(args, 'vocabulary_level'):
        args.vocabulary_level = args.vocab_level
        args.vocabulary_correct = args.vocab_correct
        args.vocabulary_total = args.vocab_total

    if args.command == 'add':
        add_assessment(args, tracker)
    elif args.command == 'progress':
        progress_view(tracker)
    elif args.command == 'report':
        report_view(tracker)


if __name__ == '__main__':
    main()