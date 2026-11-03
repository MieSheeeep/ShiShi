# 第三方代码声明

## ReaJason/xhs — MIT

- 项目：https://github.com/ReaJason/xhs
- 固定参考提交：f4b62d9f8e4078e631fc6e4ec8e430bc711ee9f0
- 原始文件：[xhs/core.py](https://github.com/ReaJason/xhs/blob/f4b62d9f8e4078e631fc6e4ec8e430bc711ee9f0/xhs/core.py)
- 复用范围：`XhsClient.get_note_by_id_from_html` 中读取 `window.__INITIAL_STATE__`、读取 `noteDetailMap` 以及递归将驼峰键名转为下划线的逻辑。
- 本项目文件：`backend/vendor/xhs_html.py`。
- 修改：网络获取与解析分离；采用 BeautifulSoup 定位脚本；改进空值替换，保留字符串中的 undefined；增加字段检查与可读错误。未复用请求签名、发帖、互动、批量采集或验证码处理代码。
- Copyright (c) 2023 ReaJason
- 许可证全文：[third_party/xhs-LICENSE](third_party/xhs-LICENSE)。

本项目未依赖 MediaCrawler 或 XHS-Downloader，也未将它们的代码合并入仓库。
