# 智能提取：采集正文 → 统一食谱

把采集到的正文（小红书笔记、豆果原文等）用 AI 整理成统一的 V2 食谱草稿。重点解决正文混写、信息缺失和一篇多道菜三类问题，缺失内容保留为空并提示核对，不让模型自行补造。

## 模块

- `backend/recipe_extract.py`：提取与清洗逻辑，独立模块，不依赖采集改进即可开工。
- `backend/recipe_extract_samples.py`：12 个固定样例正文与人工标注（ground truth）。
- `examples/extract_recipes.py`：可运行示例，跑真实提取并输出效果、耗时与成本。
- `tests/test_recipe_extract.py`：18 个单元测试（mock LLM，验证拆分、提取、后处理与不补造）。

复用已有基础，不另建重复规则：

| 复用 | 用途 |
| --- | --- |
| `ai_recipe.config()` / `_chat()` | 模型配置与 OpenAI 兼容调用 |
| `core.normalize()` | 食材归一（西红柿→番茄、食盐→盐、食用油→油） |
| `core.quantity()` | 用量解析（示例里的用量一致性对比） |
| `condiments.is_condiment()` | 调料 / 食材分类 |

## 对外接口

```python
from backend import recipe_extract

recipe_extract.split_article(text, settings)   # 多道菜拆分，返回每道菜的正文片段列表
recipe_extract.extract_one(text, settings)     # 单篇提取（模型原始输出 + 字段兜底）
recipe_extract.extract(text, settings)         # 编排：拆分 → 逐篇提取 → 后处理
```

`extract` 返回 `{'recipes': [...], 'multi': bool}`，每篇草稿为：

```python
{
  'name': '番茄炒蛋', 'minutes': '', 'servings': '',
  'ingredients': [{'name': '番茄', 'amount': '2个', 'kind': '食材'}, ...],
  'steps': ['...'], 'notes': '',
  'warnings': ['...'],   # 核对提示
}
```

## 关键约束与实现

- **只提取、不补造**：提示词强制「绝不补造、推测或脑补正文没有的信息」；缺失字段保留空字符串 / 空数组。
- **缺失留空并提示核对**：缺菜名、缺食材、缺步骤、缺用量都会生成 `warnings` 提示；食材用量为空时保留为空，不自动填「适量」。
- **补造校验（输出校验）**：后处理确定性检查每个食材名是否在正文出现（含别名反向匹配），未出现则提示「可能为补造」；菜名未在正文直接出现时提示「可能为推断」。
- **多道菜拆分**：独立 `split_article`，用「第一道/第二道」「【菜名】」「主菜/配菜/蘸料/主食」等分隔识别多道菜，逐篇提取。

## 样例覆盖

12 个固定样例（可公开、去敏的合成家常菜正文）：

| 类别 | 样例 | 覆盖点 |
| --- | --- | --- |
| 对照 | standard-clear | 标准清晰菜谱，验证不破坏正常提取 |
| 混写 | mixed-prose | 食材用量散在散文中、未写菜名 |
| 混写 | mixed-story | 开头故事叙述，食谱藏在中后段 |
| 混写 | mixed-no-section | 食材与步骤不分段，逗号连写 |
| 缺失 | missing-name | 有食材步骤、缺菜名 |
| 缺失 | missing-amount | 食材只列名称、全无用量 |
| 缺失 | missing-steps | 只有食材、无步骤 |
| 缺失 | missing-meta | 食材步骤完整、无耗时份量 |
| 缺失 | missing-almost-all | 几乎无内容 |
| 多道 | multi-two | 一篇两道完整菜 |
| 多道 | multi-three | 一篇三道菜 |
| 多道 | multi-main-side | 一道主菜 + 一个蘸料 |

## 效果、耗时与成本记录

模型 `deepseek-flash`（DeepSeek-V4.1-Flash-1017），一次运行 12 个样例（含拆分共 28 次请求）。

| 指标 | 结果 |
| --- | --- |
| 菜名准确率 | 100%（16/16） |
| 食材召回率 | 100% |
| 食材精确率（无补造食材） | 100% |
| 用量准确率 | 100% |
| 步骤覆盖率 | 98.4%（一处步骤粒度差异） |
| 缺失字段留空率（不补造） | 100%（24/24） |
| 总耗时 | 50.36 秒（平均约 4.2 秒/样例） |
| 输入 token（cache miss） | 5530 |
| 输入 token（cache hit） | 4090 |
| 输出 token | 6017 |
| 总成本 | 约 $0.0089 |

成本按 DeepSeek 官方定价（峰值时段：输入 cache miss $0.30/M、cache hit $0.006/M、输出 $1.20/M）计算，参考 [DeepSeek 官方定价页](https://api-docs.deepseek.com/quick_start/pricing/)。完整明细见 `examples/extract_recipes.py` 运行后写出的 `data/extract-eval-report.json`（该目录已被 gitignore，不入库）。

## 运行方式

```powershell
# 先配置仓库根 .env（已 gitignore）：
#   SHISHI_AI_API_KEY=...
#   SHISHI_AI_MODEL=deepseek-flash

.\.venv\Scripts\python.exe examples\extract_recipes.py
```

单元测试（无需 API Key，mock LLM）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_recipe_extract.py -q -p no:cacheprovider
```

## 已知限制

- 提取结果由模型生成，同一样例多次运行存在轻微波动（本次记录为单次代表运行）。
- 步骤粒度与模型的分句习惯有关：少数情况会把相邻两步合并或拆开（步骤覆盖率 98.4% 的来源）。
- 主菜 + 蘸料这类「一篇多道」依赖模型的拆分判断，语义边界（蘸料是否独立成菜）存在歧义；已通过拆分提示词显式约束。
- 补造校验是「提示核对」而非硬删除，避免误删别名或口语化表述。
