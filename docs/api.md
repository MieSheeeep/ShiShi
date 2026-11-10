# 食拾接口约定

本文档约定前后端共用的 HTTP 接口、数据结构和错误码。接口根地址为 `/api`，请求与响应均为 UTF-8 编码的 JSON。

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
| 404 | 资源不存在，或不属于当前账号 |
| 409 | 冲突：用户名已注册、来源链接已收藏、同一分组内重名 |
| 422 | 请求字段不合法：材料、步骤、图片、封面、标签或密码长度不符合要求；上传图片不是 JPG/PNG/WEBP 或超过 5 MB |

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
{ "ingredients": ["番茄", "鸡蛋"], "staples": ["盐", "油"] }
```

## 四、接口列表

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | 否 | 注册账号，返回令牌；新账号自动获得默认分组和 6 道演示食谱 |
| POST | `/api/auth/login` | 否 | 账号密码登录，返回令牌 |
| POST | `/api/auth/logout` | 是 | 退出登录，当前令牌失效 |
| GET | `/api/auth/me` | 是 | 返回当前用户，用于前端恢复会话 |
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
| POST | `/api/match` | 是 | 按现有食材匹配食谱 `{"ingredients": [], "staples": []}` |
| POST | `/api/shopping` | 是 | 按食谱 ID 合并采购清单 `{"ids": [1, 2]}` |
| GET | `/api/shopping` | 是 | 读取当前用户的采购清单 |
| PUT | `/api/shopping` | 是 | 覆盖保存采购清单 `{"items": [...]}` |
| GET | `/api/settings` | 是 | 读取常备食材 |
| PUT | `/api/settings` | 是 | 保存常备食材 |

图片通过 `GET /api/media/<文件>` 公开读取，URL 为内容哈希，图片本身不含用户隐私，不参与鉴权，便于 `<img>` 直接展示。内置演示封面使用 `GET /api/demo/<文件>`，随仓库分发。

`cover` 是食谱卡片的封面地址：只接受 `/api/media/` 或 `/api/demo/` 下的本地图片，留空时前端回退显示食谱图标。导入的食谱可在编辑器中把首图、步骤图或上传的照片设为封面。

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
- 新注册的账号若没有认领到旧数据，会自动复制 6 道内置演示食谱与“我的分类 / 厨具 / 口味”三个默认分组。