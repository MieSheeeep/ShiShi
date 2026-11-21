# 食拾接口约定

本文档约定前后端共用的 HTTP 接口、数据结构和错误码。接口根地址为 `/api`，请求与响应均为 UTF-8 编码的 JSON。

厨房足迹新增下厨会话、成长摘要与菜品标记接口，完整字段、幂等与版本冲突规则见[下厨记录接口](cooking-records.md)。现有食谱、库存和采购接口继续兼容。

## 一、登录与鉴权

1. 除注册、登录外，所有业务接口都要求请求头携带登录令牌：

   ```http
   Authorization: Bearer <token>
   ```

2. 令牌由注册或登录接口返回，有效期 30 天；退出登录后立即失效。服务端只保存令牌的 SHA-256 摘要。
3. 令牌缺失、无效或过期时返回 `401`，响应头带 `WWW-Authenticate: Bearer`，响应体为 `{"detail": "请先登录"}`。
4. 前端把令牌保存在 `localStorage` 的 `shishi_token` 键；收到 `401` 时清除令牌并回到登录页。

## 二、统一错误格式

所有错误响应体均为 `{"detail": "中文说明"}`，前端直接展示该文案。

| 状态码 | 含义 |
| --- | --- |
| 200 | 成功 |
| 401 | 未登录、令牌失效或用户名密码错误 |
| 403 | 站点已关闭公开注册（`SHISHI_ALLOW_REGISTER=false`） |
| 404 | 资源不存在，或不属于当前账号 |
| 409 | 冲突：用户名已注册、来源链接已收藏、同一分组内重名 |
| 422 | 请求字段不合法：材料、步骤、图片、封面、标签、邀请码、AI 接口地址或密码长度不符合要求；上传图片不是 JPG/PNG/WEBP 或超过 5 MB |

跨账号访问统一按 `404` 处理，不暴露其他用户的数据是否存在。

## 三、数据结构

### 用户 User

```json
{ "id": 1, "username": "alice", "created_at": "2026-11-10T08:00:00+00:00" }
```

用户名 3–32 个字符、不能包含空白；密码 6–128 个字符。

### 登录响应 AuthResponse

```json
{ "token": "<登录令牌>", "user": { "id": 1, "username": "alice", "created_at": "..." } }
```

### 食谱 Recipe（保存格式 V2）

```json
{
  "id": 12,
  "schema_version": 2,
  "name": "番茄炒蛋",
  "emoji": "🍅",
  "source": {
    "platform": "douguo",
    "url": "https://www.douguo.com/cookbook/123.html",
    "author": "原作者",
    "original_text": "导入原文",
    "original_images": ["/api/media/<64位哈希>.jpg"],
    "imported_at": "2026-11-10T08:00:00+00:00"
  },
  "minutes": "15",
  "servings": "2人份",
  "tags": [{ "id": "<标签ID>", "group": "我的分类", "name": "快手菜" }],
  "notes": "",
  "images": ["/api/media/<64位哈希>.jpg"],
  "cover": "/api/demo/tomato-egg.jpg",
  "ingredients": [{ "id": "<稳定ID>", "name": "番茄", "amount": "2个", "kind": "食材" }],
  "steps": [{ "id": "<稳定ID>", "text": "番茄洗净切块", "images": [] }],
  "original_snapshot": { "kind": "imported", "captured_at": "...", "recipe": {} },
  "created_at": "...",
  "updated_at": "..."
}
```

`tag_ids` 是存储层字段，读取时同时返回对应 `tags` 明细。`ingredients` 与 `steps` 的 `id` 由编辑器生成，排序时不可重新生成。

### 标签目录 TagCatalogue

```json
{
  "groups": [{ "id": "<分组ID>", "name": "我的分类" }],
  "tags": [{ "id": "<标签ID>", "name": "快手菜", "group_id": "<分组ID>", "group": "我的分类" }]
}
```

### 采购清单 ShoppingItem

```json
{
  "name": "鸡蛋",
  "amount": "5个",
  "sources": [{ "recipe": "番茄炒蛋", "original": "鸡蛋 3个" }],
  "checked": false
}
```

### 食材匹配结果 MatchResult

食谱字段加上 `missing`：当前用户缺少的材料名数组，按缺料数量和比例升序排序。

### 常备食材 Settings

```json
{ "ingredients": [{"name": "番茄", "amount": "2", "unit": "个"}], "staples": [{"name": "盐", "amount": "", "unit": ""}] }
```

名称必填；`amount` 与 `unit` 可为空，表示未记录用量。

完整食品库存见[冰箱管理与兼容升级](fridge-management.md)。新版存在后，Settings 是同一库存的在库投影，已用完条目不参与采购、计划和库存找菜。旧 Settings 读写保持兼容。

采购清单可选布尔字段 `pantry` 表示本次核对认为家中已有，可通过原 `PUT /api/shopping` 调整；兼容旧增强分支的 `at_home` 读取。菜单确认及用量修改规则见[菜单与采购](menu-shopping-flow.md)。

新增鉴权接口：`GET /api/fridge`，`POST /api/fridge/items`，`PUT /api/fridge/items/{id}`，`DELETE /api/fridge/items/{id}`，以及 `POST /api/fridge/categories`、`PATCH /api/fridge/categories/{id}`、`DELETE /api/fridge/categories/{id}`。字段、状态码、迁移和限制见冰箱说明。

### AI 配置 AiSettings

```json
{ "base": "https://api.deepseek.com/v1", "model": "deepseek-chat", "configured": true, "source": "account", "key_hint": "••••5678" }
```

写入时可以只传 `base` 与 `model`，省略 `key` 表示沿用已保存的 Key。读取时只返回末四位，不回传完整 Key。`source` 为 `account` 或 `env`，表示配置来自账号还是环境变量。

### 小红书登录态 XhsSettings

```json
{ "configured": true, "source": "account", "cookie_hint": "••••789xyz" }
```

写入 `{"cookie": "web_session=…; a1=…"}` 保存登录态，提交空串表示退出登录。内容需包含 `web_session` 或 `a1=`，否则返回 422；读取只返回末六位，不回传完整 Cookie。`source` 为 `account`（账号内保存，优先）或 `environment`（来自 `XHS_COOKIE`），`configured` 表示当前是否可用。导入小红书链接时自动带上该账号的登录态。

## 四、接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/health` | 否 | 健康检查，返回 `{"status": "ok", "journal_mode": "..."}` |
| GET | `/api/auth/policy` | 否 | 返回站点注册策略 `{"allow_register": true, "invite_required": false}` |
| POST | `/api/auth/register` | 否 | 注册账号，返回令牌；开启 `SHISHI_INVITE_CODE` 时需附带 `invite_code`；新账号自动获得默认分组和 6 道演示食谱 |
| POST | `/api/auth/login` | 否 | 账号密码登录，返回令牌 |
| POST | `/api/auth/logout` | 是 | 退出登录，当前令牌失效 |
| GET | `/api/auth/me` | 是 | 返回当前用户，用于前端恢复会话 |
| PUT | `/api/auth/password` | 是 | 修改密码 `{"old_password": "...", "new_password": "..."}`；其他会话令牌失效 |
| DELETE | `/api/auth/account` | 是 | 注销账号 `{"password": "..."}`；删除该账号的食谱、标签、清单、设置与会话 |
| GET | `/api/recipes?tag_id=<ID>&tag_id=<ID>` | 是 | 当前用户的食谱列表，多个标签为“同时满足” |
| POST | `/api/recipes` | 是 | 新增食谱；来源链接在当前账号内重复返回 409 |
| PUT | `/api/recipes/{id}` | 是 | 更新食谱；只能改自己的记录 |
| DELETE | `/api/recipes/{id}` | 是 | 删除食谱；不存在或非本人返回 404 |
| POST | `/api/media` | 是 | 上传封面图（multipart 字段 `file`，JPG/PNG/WEBP，≤5 MB），返回 `/api/media/<哈希>.<扩展名>` |
| GET | `/api/tags` | 是 | 当前用户的标签目录 |
| POST | `/api/tag-groups` | 是 | 新建分组 `{"name": "厨具"}` |
| POST | `/api/tags` | 是 | 新建标签 `{"group_id": "...", "name": "烤箱"}` |
| PATCH | `/api/tag-groups/{id}` | 是 | 重命名分组 `{"name": "..."}` |
| PATCH | `/api/tags/{id}` | 是 | 重命名标签 `{"name": "..."}` |
| DELETE | `/api/tag-groups/{id}` | 是 | 删除空分组；分组内仍有标签返回 422 |
| DELETE | `/api/tags/{id}` | 是 | 删除标签并清理自己食谱中的引用 |
| POST | `/api/imports` | 是 | 解析豆果或小红书链接，返回可编辑草稿（不落库） |
| POST | `/api/imports/search` | 是 | 按菜名搜索豆果 `{"keyword": "...", "index": 0}`，返回草稿与 `meta`；已收藏的结果自动跳过 |
| POST | `/api/imports/generate` | 是 | 用一句话生成食谱草稿 `{"prompt": "..."}`；自动加入「AI」标签并查找封面 |
| GET | `/api/ai/settings` | 是 | 读取当前账号的 AI 配置（Key 只回显末四位） |
| PUT | `/api/ai/settings` | 是 | 保存 AI 配置 `{"base": "...", "model": "...", "key": "..."}` |
| GET | `/api/xhs/settings` | 是 | 读取小红书登录态（Cookie 只回显末六位） |
| PUT | `/api/xhs/settings` | 是 | 保存或清除小红书登录态 `{"cookie": "..."}`；空串表示退出，格式不符返回 422 |
| POST | `/api/ai/suggest` | 是 | 按食材推荐菜式 `{"ingredients": [], "staples": []}`，返回 `{"dishes": [{"name": "...", "reason": "..."}]}` |
| POST | `/api/match` | 是 | 按现有食材匹配食谱 `{"ingredients": [], "staples": []}` |
| POST | `/api/shopping` | 是 | 按食谱 ID 合并采购清单 `{"ids": [1, 2]}`；按冰箱库存扣减，库存足够的条目标记为 `pantry` 且不计入待买 |
| GET | `/api/shopping` | 是 | 读取当前用户的采购清单 |
| PUT | `/api/shopping` | 是 | 覆盖保存采购清单 `{"items": [...]}` |
| GET | `/api/settings` | 是 | 读取常备食材 |
| PUT | `/api/settings` | 是 | 保存常备食材 |

图片通过 `GET /api/media/<文件>` 公开读取，URL 为内容哈希，图片本身不含用户隐私，不参与鉴权，便于 `<img>` 直接展示。内置演示封面使用 `GET /api/demo/<文件>`，随仓库分发。

`cover` 是食谱卡片的封面地址：只接受 `/api/media/` 或 `/api/demo/` 下的本地图片，留空时前端回退显示食谱图标。导入的食谱可在编辑器中把首图、步骤图或上传的照片设为封面。AI 生成的草稿会按菜名在豆果检索一张成品图并下载到 `/api/media/`，未命中时留空。

AI 相关接口在未配置模型时返回 422，`detail` 提示先在账号管理中填写 Key；模型返回内容无法解析为食谱时同样返回 422。

## 五、完整流程示例

```http
POST /api/auth/register
{"username": "alice", "password": "secret123"}

200 {"token": "t...", "user": {"id": 1, "username": "alice", ...}}
```

```http
POST /api/recipes
Authorization: Bearer t...
{"name": "番茄炒蛋", "source": "", "ingredients": [{"name": "番茄", "amount": "2个"}], "steps": ["切块", "炒熟"]}

200 {"id": 7, "name": "番茄炒蛋", "ingredients": [{"name": "番茄", ...}], ...}
```

```http
GET /api/recipes
Authorization: Bearer t...

200 [{...}]
```

## 六、用户隔离与数据迁移

- 食谱、标签分组、标签、采购清单、常备食材都按账号隔离；不同用户可以使用相同的来源链接。
- 升级前没有账号归属的本地数据（旧 `recipes`、`tag_groups`、清单与设置）会在**第一个账号注册时**整体交给该账号，避免旧收藏丢失。
- 新注册的账号若没有认领到旧数据，会自动复制 6 道内置演示食谱与“我的分类 / 厨具 / 口味 / 四季”四个默认分组；「我的分类」下附带「AI」标签用于标记 AI 生成的食谱。
