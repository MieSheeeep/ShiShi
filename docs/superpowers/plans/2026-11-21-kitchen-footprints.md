# 厨房足迹 R2 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; 每个实现任务先红绿测试，再需求审查，再质量审查。本轮用户已确认 R2 并要求开发，直接执行。

**Goal:** 完整交付 R2 第一、二批的记录、作品与成长体验和暖色主题。

**Architecture:** 独立后端 cooking 模块保存账号会话与快照，派生统计与印章；独立 Vue 组件承载跟做、足迹与首页入口；根 App 仅接入，保留原有能力。格式以 [实现设计](../../cooking-records-design.md) 为准。

**Tech Stack:** 现有 FastAPI / Pydantic / SQLite / SQLAlchemy / Vue 3 / Vite，无新增运行时依赖。

## Task 1 — 服务端会话与成长

Files: backend/cooking.py、backend/cooking_store.py、backend/cooking_schema.py、tests/test_cooking.py。公共入口 backend/main.py 安装路由；recipe_store.py 注销清理由集成任务完成。

- [x] 先写并运行集成测试，确认新路由404导致失败；隔离临时数据库。
- [x] 创建草稿、快照、版本更新、分页筛选、完成/撤回幂等、照片校验、手动补记与标记，按实现设计契约返回。
- [x] 测试跨账号拒绝、删食谱仍保留快照、真实日期、部分失手与跳过、旧version冲突、重复完成与撤回、四印章追溯、等级阈值、备份后读取一致。
- [x] 运行 `.venv/Scripts/python.exe -m pytest tests/test_cooking.py -q -p no:cacheprovider` 全绿，自审、提交，仅提交本任务文件。
- [x] 独立需求审查通过后再做独立质量审查；修复后复核。

## Task 2 — 记录与跟做组件

Files: frontend/src/useCookingJournal.js、cookingJournal.js、components/CookingWorkspace.vue、KitchenFootprints.vue、JournalHome.vue、kitchen-journal.css、tests/cooking-journal.test.mjs。不修改根 App、theme.css 或已有组件。

- [ ] 先测试有效尝试、照片缺省不伪装成品、月份分组、历次同菜、持久化成功前不清草稿、保存串行失败保留输入等核心逻辑，观察失败。
- [ ] 按契约提供 composable 及三个组件。Workspace 可使用snapshot跟做，自动保存步骤、逐菜确认结果/上传照片/心得、补记、保存失败重试，完成后显示作品反馈。
- [ ] Footprints 必须有作品墙、月份足迹、拿手菜、真实统计、四枚可点击回溯印章、编辑/撤回/再做一次与历史对比，不预填假记录。无图文字卡和空状态同样完整。
- [ ] Home 提供继续做饭、最近作品、成长目标，事件交给集成任务处理。音效不自动播放，支持 prefers-reduced-motion。
- [ ] Node测试与Vite构建通过，组件需求审查后质量审查，修复并提交。

## Task 3 — 根应用接入、全站暖色和回归

Files: App.vue、theme.css、mobile-navigation.css、main.js、recipe_store.py、docs/api.md、README.md、docs/verification.md、docs/cooking-records.md。

- [ ] 开发前核对 Task 1/2 接口及 emits，新增账号注销记录清理测试并观察失败，再接入事务清理。
- [ ] 根组件管理账号级 composable；开始做饭真实创建会话；恢复草稿、保存成功转记录；独立记录导航、我的次级入口；保留食谱选菜、冰箱、采购、AI、账号、周计划。
- [ ] 全站暖纸/奶油/焦茶/砖红；正文与按钮对比至少4.5:1；记录页宋体标题、真实日期和纪念号、朱砂印章，控制纹理和动画。
- [ ] 运行全量pytest、全部Node测试及生产构建；使用独立验收数据库，浏览器真实完成两次同菜、失手再尝试、上传、刷新、撤回、补记、草稿恢复；320/390/桌面截图。
- [ ] 需求与质量复审全部修复；更新接口、备份说明、截图与验证记录，获取最新main再检查差异。
- [ ] 提交并推送功能分支，交付PR（未获本轮明确合并请求时不自动合main），明确验证范围与未外调模型的限制。

## 执行记录

- 基线：123项pytest、15项Node测试及Vite构建通过。
- Task1：先接口缺失红，再实现；两轮审查定位并修复食谱ID复用、客户端created_at可重用、空白菜名和越界整数。最终需求与质量审查均通过，27项新增pytest实跑通过。
- 前端组件任务进行中，真实API的独立验收库已准备有图/无图、失手/再尝试和零记录账号，未写入主数据库。
