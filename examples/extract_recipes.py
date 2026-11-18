"""可运行示例：对固定样例正文跑真实 AI 提取，输出效果、耗时与成本记录。

用法（在仓库根目录，需先配置 .env 里的 SHISHI_AI_API_KEY / SHISHI_AI_MODEL）：

    .venv/Scripts/python.exe examples/extract_recipes.py

结果会打印汇总，并把完整明细写到 ``data/extract-eval-report.json``。
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import ai_recipe, recipe_extract as re
from backend.core import normalize, quantity
from backend.recipe_extract_samples import SAMPLES

# deepseek-flash 官方定价（美元 / 百万 token，峰值时段）。
PRICE_INPUT_MISS = 0.30   # 输入 cache miss
PRICE_INPUT_HIT = 0.006   # 输入 cache hit
PRICE_OUTPUT = 1.20       # 输出


# ---- 评估辅助 ----

def _norm(name):
    return ''.join(normalize(name).split())


def _name_eq(a, b):
    a, b = _norm(a), _norm(b)
    if not a and not b:
        return True
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _ingredient_match(a, b):
    """食材名匹配：归一后相等，或互为子串（覆盖 葱花/葱、鸡翅/鸡翅中）。"""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _amount_ok(exp, got):
    e = ''.join(exp.split())
    g = ''.join(got.split())
    if e == '':
        return g == ''          # 正文没写用量，模型必须留空，不得补造
    if g == '':
        return False
    pe, pg = quantity(e), quantity(g)
    if pe is not None and pg is not None:
        return pe == pg         # 可称量：数字+单位一致（"两个"与"2个"等价）
    return True                 # 模糊用量（适量/少许/一点）：非空即算保留原文


def _step_covered(exp_step, got_steps):
    exp = set(''.join(exp_step.split()))
    if not exp:
        return False
    for g in got_steps:
        gs = set(''.join(g.split()))
        if len(exp & gs) >= max(2, len(exp) * 0.5):
            return True
    return False


def _match_ingredients(extracted, expected):
    """把提取食材与标注食材做贪心匹配，返回 (matched_pairs, recall, precision)。"""
    got = list(extracted)
    used = [False] * len(got)
    pairs = []
    matched_exp = 0
    for exp in expected:
        hit = None
        for i, g in enumerate(got):
            if not used[i] and _ingredient_match(g['name'], exp['name']):
                hit = i
                break
        if hit is not None:
            used[hit] = True
            pairs.append((exp, got[hit]))
            matched_exp += 1
    recall = matched_exp / len(expected) if expected else 1.0
    precision = matched_exp / len(got) if got else 1.0
    return pairs, recall, precision


def _evaluate_one(extracted, expected):
    """对单个菜谱计算指标；extracted 是后处理后的草稿，expected 是标注。"""
    name_ok = _name_eq(extracted['name'], expected['name']) if expected['name'] else (extracted['name'] == '')
    pairs, recall, precision = _match_ingredients(extracted['ingredients'], expected['ingredients'])
    amount_correct = sum(1 for e, g in pairs if _amount_ok(e['amount'], g['amount']))
    amount_total = len(pairs)
    # 缺失留空：标注为空的 name/minutes/servings，模型是否留空
    miss_fields = [('name', extracted['name']), ('minutes', extracted['minutes']), ('servings', extracted['servings'])]
    miss_expected = [(k, v) for k, v in miss_fields if expected.get(k) == '']
    miss_empty = sum(1 for _, v in miss_expected if v == '')
    step_recall = sum(1 for s in expected['steps'] if _step_covered(s, extracted['steps'])) / len(expected['steps']) if expected['steps'] else 1.0
    return {
        'name_ok': bool(name_ok),
        'ingredient_recall': round(recall, 3),
        'ingredient_precision': round(precision, 3),
        'amount_accuracy': round(amount_correct / amount_total, 3) if amount_total else None,
        'step_recall': round(step_recall, 3),
        'missing_empty': round(miss_empty / len(miss_expected), 3) if miss_expected else None,
    }


# ---- 计时与用量采集 ----

USAGE_LOG = []


def instrumented_chat(settings, messages, *, effort='low', max_tokens=4000):
    start = time.perf_counter()
    content, usage = ai_recipe._chat_usage(settings, messages, extra={'effort': effort, 'max_tokens': max_tokens})
    USAGE_LOG.append({'seconds': time.perf_counter() - start, 'usage': usage})
    return content


def main():
    re._chat = instrumented_chat
    settings = ai_recipe.config()
    if not settings['key']:
        print('未配置 SHISHI_AI_API_KEY，无法运行真实提取。')
        return

    report = {'model': settings['model'], 'samples': [], 'summary': {}}
    agg = {'name_ok': 0, 'name_total': 0, 'recall_sum': 0.0, 'recall_n': 0,
           'precision_sum': 0.0, 'precision_n': 0, 'amount_sum': 0.0, 'amount_n': 0,
           'step_sum': 0.0, 'step_n': 0, 'missing_sum': 0.0, 'missing_n': 0,
           'prompt_miss': 0, 'prompt_hit': 0, 'output': 0, 'seconds': 0.0}

    for sample in SAMPLES:
        USAGE_LOG.clear()
        start = time.perf_counter()
        result = re.extract(sample['text'], settings)
        elapsed = time.perf_counter() - start

        # 单道菜 or 多道菜
        expects = sample['expect'] if isinstance(sample['expect'], list) else [sample['expect']]
        recipes = result['recipes']
        # 拆分保持原文顺序，按下标配对评估（单道与多道一致）
        metrics = [_evaluate_one(recipes[i], exp) for i, exp in enumerate(expects) if i < len(recipes)]

        for m in metrics:
            agg['name_ok'] += int(m['name_ok']); agg['name_total'] += 1
            if m['ingredient_recall'] is not None:
                agg['recall_sum'] += m['ingredient_recall']; agg['recall_n'] += 1
            agg['precision_sum'] += m['ingredient_precision']; agg['precision_n'] += 1
            if m['amount_accuracy'] is not None:
                agg['amount_sum'] += m['amount_accuracy']; agg['amount_n'] += 1
            if m['step_recall'] is not None:
                agg['step_sum'] += m['step_recall']; agg['step_n'] += 1
            if m['missing_empty'] is not None:
                agg['missing_sum'] += m['missing_empty']; agg['missing_n'] += 1

        miss = sum(u['usage'].get('prompt_cache_miss_tokens', 0) for u in USAGE_LOG)
        hit = sum(u['usage'].get('prompt_cache_hit_tokens', 0) for u in USAGE_LOG)
        out = sum(u['usage'].get('completion_tokens', 0) for u in USAGE_LOG)
        agg['prompt_miss'] += miss; agg['prompt_hit'] += hit; agg['output'] += out; agg['seconds'] += elapsed

        report['samples'].append({
            'id': sample['id'], 'category': sample['category'], 'label': sample['label'],
            'split_into': len(recipes), 'multi': result['multi'],
            'seconds': round(elapsed, 2), 'calls': len(USAGE_LOG),
            'prompt_cache_miss_tokens': miss, 'prompt_cache_hit_tokens': hit, 'completion_tokens': out,
            'metrics': metrics,
            'recipes': [{k: v for k, v in r.items()} for r in recipes],
        })
        print(f"[{sample['id']}] 拆{len(recipes)}篇 用时{elapsed:.1f}s 入{miss}出{out} 指标={json.dumps(metrics, ensure_ascii=False)}")

    # 汇总
    cost_input = (agg['prompt_miss'] * PRICE_INPUT_MISS + agg['prompt_hit'] * PRICE_INPUT_HIT) / 1e6
    cost_output = agg['output'] * PRICE_OUTPUT / 1e6
    report['summary'] = {
        'name_accuracy': round(agg['name_ok'] / agg['name_total'], 3) if agg['name_total'] else None,
        'ingredient_recall': round(agg['recall_sum'] / agg['recall_n'], 3) if agg['recall_n'] else None,
        'ingredient_precision': round(agg['precision_sum'] / agg['precision_n'], 3) if agg['precision_n'] else None,
        'amount_accuracy': round(agg['amount_sum'] / agg['amount_n'], 3) if agg['amount_n'] else None,
        'step_recall': round(agg['step_sum'] / agg['step_n'], 3) if agg['step_n'] else None,
        'missing_empty_rate': round(agg['missing_sum'] / agg['missing_n'], 3) if agg['missing_n'] else None,
        'total_seconds': round(agg['seconds'], 2),
        'prompt_cache_miss_tokens': agg['prompt_miss'],
        'prompt_cache_hit_tokens': agg['prompt_hit'],
        'completion_tokens': agg['output'],
        'cost_usd': round(cost_input + cost_output, 6),
        'cost_input_usd': round(cost_input, 6),
        'cost_output_usd': round(cost_output, 6),
    }

    print('\n=== 汇总 ===')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))

    out_path = Path(__file__).resolve().parents[1] / 'data' / 'extract-eval-report.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n完整明细已写入', out_path)


if __name__ == '__main__':
    main()
