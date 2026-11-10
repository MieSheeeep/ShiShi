# 食拾实施计划

目标：完成可本地运行的豆果食谱管理初版。

- [x] tests/test_core.py：先定义解析、合并、URL 校验测试，运行确认失败。
- [x] backend/core.py：实现别名、Decimal 用量解析、豆果 HTML 提取、合并规则。
- [x] backend/main.py：SQLite 数据表与食谱、匹配、清单接口；内置示例。
- [x] frontend/src/App.vue、style.css：完成食谱库、导入编辑器、详情、食材筛选、清单。
- [x] start.ps1、README.md：依赖安装、构建与单端口启动说明。
- [x] 运行 pytest、npm run build 与本地接口检查，修复后交付。
## 后端升级：账号登录与用户隔离（2026-11-10）

- [x] backend/auth.py：用户名密码注册登录、scrypt 密码哈希、会话令牌与退出。
- [x] backend/recipe_store.py：食谱、标签、清单、设置按 user_id 隔离；旧单用户表迁移与首个账号认领。
- [x] backend/main.py：登录注册接口与全部业务接口 Bearer 鉴权，跨账号访问返回 404。
- [x] docs/api.md：统一数据结构、接口清单、错误码与完整流程约定。
- [x] frontend/src/components/LoginView.vue、App.vue、recipeEditing.js：登录注册页、令牌持久化、401 自动登出。
- [x] tests/test_auth.py、tests/test_upgrade.py：鉴权、隔离与升级认领测试；全量 53 项通过，前端构建通过。
## 封面与标签调整（2026-11-10）

- [x] 标签沿用「快手菜」，内置示例、接口文档与现有账号数据保持一致。
- [x] backend/recipe_schema.py、media.py、main.py：食谱 cover 字段、封面上传接口与首图兜底。
- [x] frontend RecipeEditor.vue、RecipeDetail.vue、App.vue：上传/选择封面、卡片与详情显示实物图。
- [x] backend/demo_images/：6 道演示食谱的真实菜品封面与来源说明；升级时自动补图。
- [x] tests/test_cover.py：封面往返、非法地址、上传鉴权与格式、自动首图封面；全量 57 项通过。
