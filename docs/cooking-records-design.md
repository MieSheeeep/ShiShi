# 厨房足迹实现设计

2026-11-21，依据用户已确认的[修正案 R2](beginner-growth-update-proposal.md)。本文件冻结本轮前后端交接格式；接口实现状态以验收记录为准。

## 本轮范围

实现服务端下厨草稿、完成记录、照片与心得、作品墙、月份时间线、同菜历次尝试、拿手菜手动标记、五档等级与四枚可追溯印章。应用暖纸/焦茶/砖红主题，完成记录显影、展开和盖章交互，首页提供继续做饭和最近记录。保留食谱库、冰箱、采购、AI、小红书登录与周计划。月度拼贴导出、复杂照片对比滑块、社区与评论图属于 R2 第三批，不纳入当前实现。

## 数据与状态

新增 cooking_sessions 表：全局整数 id、账号 id、账号内稳定 number、客户端 client_id、version、state、cooked_on、started_at、completed_at、updated_at、body JSON；client_id 与 number 分别在账号内唯一。进行中 in_progress、完成 completed、撤回 withdrawn。采用现有 SQLite 事务和本地媒体，不引入依赖。

会话公开结构：

```json
{
  "id": 1, "number": 1, "client_id": "UUID", "version": 1,
  "state": "in_progress", "cooked_on": "2026-11-21", "title": "", "note": "",
  "started_at": "UTC ISO timestamp", "completed_at": null, "updated_at": "UTC ISO timestamp",
  "dishes": [{
    "id": "稳定UUID", "dish_key": "recipe:<64位实例哈希，示例简写>", "recipe_id": 7,
    "snapshot": {"name": "番茄炒蛋", "cover": "", "emoji": "🍅", "ingredients": [], "steps": [], "notes": ""},
    "outcome": "pending", "note": "", "photos": [], "completed_steps": []
  }]
}
```

快照从账号自己的已保存食谱复制，不能由客户端覆盖；菜品 dish_key 对前端是不透明字符串，绑定服务端随机生成的食谱实例身份。不能只使用可能被 SQLite 重用的整数 ID，也不能依赖客户端能提供的 created_at。使用模块私有 cooking_recipe_instances 表保存当前账号/食谱对应的随机实例 key；食谱删除触发器仅删除当前映射，保留所有历史快照与 key，后来 ID 复用会生成全新 key。修改原食谱仍属于同菜。手动补记生成独立 manual:UUID 标识，可选择已有 dish_key 继续练习，同一账号中验证关联。只允许自己的真实上传 /api/media 图片作为 photos，食谱封面只作明确标注的参考，不伪装用户成品。

PATCH dishes 只接受已有 dish id，以及 outcome、note、photos、completed_steps；未知、重复 id 或不存在的步骤拒绝。outcome 为 pending/success/practice/skipped。完成要求每道菜结果已确认，至少一道 success/practice，不强制勾完步骤。已完成记录可修改心得/日期/结果，但不能把所有菜改为未做；误记使用撤回。

修改采用 version 乐观锁；更新冲突返回 409，保留用户输入。完成成功后才清理下厨界面。重复创建返回同一草稿；重复完成或撤回返回现有状态、不重复计数。完成与更新在事务内进行，撤回后不可偷偷重新完成。

## 接口契约

均需当前账号鉴权，非本人 ID 返回404。路由由独立模块 install(app,engine,current_user) 接入，表在安装时创建，账号注销同时清理新增数据。

| 方法和路径 | 请求 | 响应 |
| --- | --- | --- |
| POST /api/cooking-sessions | client_id；recipe_ids；可选 cooked_on、manual_name、dish_key | 会话，recipe_ids 与 manual_name 二选一；重复 client_id 返回同一会话 |
| GET /api/cooking-sessions | 可选 state、dish_key、month，page=1、page_size=12（最多50） | {items,total,page,page_size}，按 cooked_on、id 倒序，默认不显示withdrawn |
| GET /api/cooking-sessions/{id} | 无 | 会话 |
| PATCH /api/cooking-sessions/{id} | version；可选 cooked_on/title/note/dishes | 更新后会话 |
| POST /api/cooking-sessions/{id}/complete | version | 会话，重复完成幂等 |
| POST /api/cooking-sessions/{id}/withdraw | version | 会话，重复撤回幂等 |
| PUT /api/cooking-dishes | dish_key、status=tried/practice/signature | {dish_key,status}，关联有效完成记录必须属于本人 |
| GET /api/cooking-summary | 无 | 下方摘要 |

时间使用 UTC ISO，cooked_on 独立保存上海日历日期，严格校验真实日期；允许补记过去日期，不接受未来日期。note 最多1000、title最多80；每会话最多20道菜，每道最多12张照片。客户端生成UUID以便网络重试，不提交个人隐私到样例。

摘要结构固定为：

```json
{
  "meals": 0, "dishes": 0,
  "level": {"number": 1, "tier": "bronze", "title": "倔强青铜", "star": 1, "next_at": 6, "remaining": 6},
  "percentile": {"percent": 0, "accounts": 1, "ahead": 0},
  "achievements": [{"id": "first-fire", "title": "第一次开火", "description": "留下一餐实际尝试", "unlocked": false, "session_id": null, "unlocked_at": null}],
  "repertoire": [{"dish_key": "recipe:<64位实例哈希，示例简写>", "name": "番茄炒蛋", "cover": "", "attempts": 1, "successes": 0, "last_note": "少放盐", "last_cooked_on": "2026-11-21", "status": "tried", "sessions": [1]}]
}
```

段位七档加巅峰：倔强青铜(0)/秩序白银(6)/荣耀黄金(12)/尊贵铂金(18)/永恒钻石(24)/至尊星耀(30)/最强王者(36)/巅峰(48，星数无上限)，每档 3 星、每 2 餐一星，巅峰档 next_at=null、remaining=0 且星数继续累加。百分位只比较本机账号的有效餐次，返回 percent/accounts/ahead，不是全服排名。有效菜数按 distinct dish_key，success与practice均计尝试，skipped不计。四印章ID first-fire、try-again、three-dishes、signature-dish，对应第一次/同菜失手后不同会话再次尝试/三种菜/同菜三个会话做成；按实际完成时间和id确定触发记录，不因日期补记编造先后。手动拿手菜标记与自动印章分开。撤回后摘要重新派生。

## 前端边界

useCookingJournal.js 管理API、保存队列、冲突和账号切换，提供 draft、summary、loading、error 及 start/patch/complete/withdraw/refresh。CookingWorkspace.vue 负责跟做与收尾，KitchenFootprints.vue 负责作品/时间/拿手菜视图及记录详情，JournalHome.vue 提供首页继续与最近足迹。新手术语使用少量固定释义；照片上传复用 /api/media。图片不是必须、失败仍能记录。

前端统一入口 `const journal=useCookingJournal()`，返回一个 reactive 对象（不是需要在子组件里逐个 `.value` 的 ref 包）：draft、drafts、records、total、page、summary、loading、saving、error、lastCompleted。动作约定 `loadAccount(userId)`、`reset()`、`refresh()`、`loadRecords({page,state,month,dish_key})`、`start({recipe_ids,manual_name,dish_key,cooked_on})`、`resume(id)`、`patch(patch,id?)`、`complete()`、`withdraw(id,version)`、`markDish(dish_key,status)`。start/resume/patch 返回会话，complete 返回已保存会话或抛出错误；成功才将 draft 清空并写入 lastCompleted。账号变化时旧请求结果必须失效，不能污染新账号页面。

三个组件统一接受 `journal` 对象；CookingWorkspace 发出 browse、recorded、records 事件；KitchenFootprints 发出 browse、cook、manual 事件（再做/补记由组件调用 start 后发出 cook）；JournalHome 发出 cook、records、browse。根 App 负责路由切换，不重复实现保存逻辑。patch 的默认目标为 draft；详情编辑传 id，不抢占进行中的 draft。loadRecords 只影响历史列表，refresh 更新 summary、drafts 与当前历史筛选，并保留尚未成功保存的表单输入。

保存队列串行化，将最新服务端 version 用于下一次更新；网络失败时保留编辑内容和可重试动作，409不能悄悄用服务端内容盖掉用户输入。照片上传期间禁用完成，上传失败保留选前内容；成功上传的地址留在编辑表单中，后续会话保存失败可直接重试。默认不实现音效，不需要增加音频资源。

根 App 仅接入导航与独立组件。主导航首页/做饭/记录/冰箱/我的，菜谱库保留首页和选菜固定入口，周计划、采购及账号仍可在我的与菜单入口访问。保持原菜谱和购物状态，不以重建数据代替升级。

主题使用 R2 色值；日期/月份/纪念号真实生成；空数据不预填假历史。卡片显影、展开、印章动画支持减少动态效果，音效默认关闭。暖色覆盖现有控件而不破坏功能，320/390/桌面验收。
