# 食拾 ShiShi

把豆果网页里的做法，收进自己的本地食谱库。

## 启动

需要 Python 3.11+、Node.js 20.19+。在 PowerShell 中执行：

```powershell
cd E:\co\ShiShi
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

打开 http://127.0.0.1:8000 。首次运行会安装依赖并构建前端；服务仅监听本机。Ctrl+C 停止。

开发时后端运行 `python -m uvicorn backend.main:app --reload`，另开终端进入 frontend 执行 `npm run dev`。

## 已实现

- 豆果 cookbook 链接导入：先预览，可修改材料、步骤、标签、来源后保存；重复链接提示。
- 食谱库搜索、分类、编辑、删除，详情和步骤勾选（步骤进度仅保留本次页面会话）。
- 按已有材料和常备调料找菜，显示缺失材料，配置保存到本地。
- 多选食谱合并采购清单，支持修改用量、勾选、查看来源、导出文本。
- SQLite 持久化，首次初始化六道明确标识的演示食谱。

数据保存在 `data/shishi.db`，备份时停止服务并复制该文件。项目未配置登录，适合单用户本机使用。

## 导入范围与限制

只接受 `https://www.douguo.com/cookbook/数字.html`，自动移除查询参数。支持 Recipe JSON-LD 和豆果材料表/步骤节点。只采集一个页面，最长请求等待 20 秒、限制 3 MB、拒绝重定向；页面不存在、访问受限、验证或解析不完整时显示失败提示，支持手动录入。

没有接入大模型。未注明的信息保持为空或“未注明”，不生成新做法。当前环境访问豆果发生 TLS 连接失败，真实在线采集尚未验证；固定 HTML 解析样本与失败路径已覆盖测试。实际网站改版可能需要调整选择器。

数量用 Decimal 计算，支持克/千克、毫升/升；不同维度分开。适量、少许、范围保留原文。支持常见单字中文数量，不覆盖所有中文数量表达。别名表位于 backend/core.py。

## 检查

```powershell
python -m pytest tests -q -p no:cacheprovider
cd frontend
npm run build
```

后端接口文档：http://127.0.0.1:8000/docs 。设计与实施范围见 docs/design.md、docs/plan.md。
