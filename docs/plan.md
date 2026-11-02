# 食拾实施计划

目标：完成可本地运行的豆果食谱管理初版。

- [x] tests/test_core.py：先定义解析、合并、URL 校验测试，运行确认失败。
- [x] backend/core.py：实现别名、Decimal 用量解析、豆果 HTML 提取、合并规则。
- [x] backend/main.py：SQLite 数据表与食谱、匹配、清单接口；内置示例。
- [x] frontend/src/App.vue、style.css：完成食谱库、导入编辑器、详情、食材筛选、清单。
- [x] start.ps1、README.md：依赖安装、构建与单端口启动说明。
- [x] 运行 pytest、npm run build 与本地接口检查，修复后交付。
