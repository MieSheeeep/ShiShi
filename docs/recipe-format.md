# 食拾食谱保存格式（V2）

食谱采用带版本号的 JSON，保存在 SQLite `recipes.body`；来源网址同时写入独立列，用于去重。材料和步骤使用稳定 ID，数组顺序就是展示与下厨顺序。编辑改变的是工作副本，来源原文和初始快照独立保留。

## 文档结构

以下为结构示例；图片文件名使用实际内容的 SHA-256，此处省略为 `…`。数据库生成食谱整数 ID，读取接口将其补为顶层 `id`。

```json
{
  "schema_version": 2,
  "name": "清蒸鱼",
  "emoji": "🐟",
  "minutes": "20",
  "servings": "2人份",
  "source": {
    "platform": "xiaohongshu",
    "url": "https://www.xiaohongshu.com/explore/笔记编号",
    "author": "原作者",
    "original_text": "导入时保留的正文",
    "original_images": ["/api/media/….jpg"],
    "imported_at": "2026-11-04T03:00:00+00:00"
  },
  "ingredients": [
    {"id": "ingredient-a", "name": "鱼", "amount": "1条", "kind": "食材"},
    {"id": "ingredient-b", "name": "盐", "amount": "少许", "kind": "调料"}
  ],
  "steps": [
    {"id": "step-a", "text": "处理鱼，放上姜片。", "images": ["/api/media/….jpg"]},
    {"id": "step-b", "text": "水开后放入蒸锅。", "images": []}
  ],
  "images": ["/api/media/….jpg"],
  "tag_ids": ["tag-steamer", "tag-light"],
  "notes": "下次少放一点盐。",
  "original_snapshot": {
    "kind": "imported",
    "captured_at": "2026-11-04T03:00:00+00:00",
    "recipe": {"schema_version": 2, "name": "导入时的名称", "steps": []}
  },
  "created_at": "2026-11-04T03:00:00+00:00",
  "updated_at": "2026-11-04T03:10:00+00:00"
}
```

快照中的 `recipe` 实际保留当时完整内容；上例为缩短篇幅作了省略。手动录入的来源网址、作者与原文可为空，平台为 `manual`。空缺的份数、耗时保持空字符串，不推测。

## 顺序和图片如何编辑

- 每个材料、每个步骤有独立 ID。上移、下移只调整数组位置，保留 ID；步骤文字和其 `images` 一起移动。
- 可以修改内容、添加或删除材料和步骤，在任一步骤下方插入新步骤。至少保留一项材料和一个步骤，保存时校验空白内容和重复 ID。
- 每步可关联多张已有原图，并调整这些图片的顺序。图集 `images` 的排序独立于步骤配图。
- 小红书导入默认保留原图集，不猜测每张图属于哪一步；用户可手动关联。
- 移除图片只移除工作副本引用；来源原图和快照保留，编辑器可重新选择。当前支持现有图片的重排与关联，尚无本机图片上传入口。
- 取消关闭时提示未保存修改；“撤回本次修改”恢复到本次打开编辑器时的状态。保存后再次编辑、刷新读取仍使用同一套 ID 与顺序。

## 自定义分组标签

标签独立保存为 `tag_groups(id, name)` 和 `tags(id, group_id, name)` 两张表。默认提供“我的分类”“厨具”“口味”，用户可以继续创建分组，例如“烹饪方式”。标签不限于预设词，可以添加“蒸锅”“空气炸锅”“清淡”等。

食谱 JSON 只保存 `tag_ids`。API 读取时额外返回解析后的 `tags`，便于显示：

```json
{"id": "tag-light", "name": "清淡", "group_id": "group-taste", "group": "口味"}
```

保存接口兼容携带上述 `tags` 对象或只携带 `tag_ids`。更改标签或分组名称不改变 ID，关联食谱同步显示新名称。删除标签会同时移除食谱的关联；非空分组须先移除内部标签。历史快照保留当时名称。选中多个标签时，列表只显示同时满足全部标签的食谱。

## 原始记录与旧数据迁移

导入预览创建 `kind=imported` 的快照，后续保存不覆盖；手动录入首次保存创建 `manual_entry` 快照。来源中的 `original_text`、`original_images` 和 `imported_at` 在后续编辑中保持不变。快照用于对照，没有一键覆盖当前食谱的恢复入口。

旧版步骤文字数组与平行的 `step_images` 按下标合并为步骤对象，生成稳定 ID；旧的文字标签迁到“我的分类”。迁移前通过 SQLite 在线备份生成 `data/shishi.db.pre-v2-时间.bak`，然后在同一事务里升级已有记录。旧记录的快照标为 `legacy_saved`，代表迁移时已保存版本，无法还原更早已被编辑掉的内容。未知版本号拒绝读取转换，避免误降级。

图片仍在 `data/media/`，数据库备份不包含图片文件。完整备份与恢复需要同时保留数据库和媒体目录，恢复旧版本时使用对应版本程序。实现见 [recipe_schema.py](../backend/recipe_schema.py) 与 [recipe_store.py](../backend/recipe_store.py)。
