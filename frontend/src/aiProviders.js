/** 常见国内大模型服务的 OpenAI 兼容地址，供快捷选择一键填好地址与模型。 */
export const AI_PROVIDERS = [
  { id: 'deepseek', name: 'DeepSeek', base: 'https://api.deepseek.com/v1', model: 'deepseek-chat', hint: 'platform.deepseek.com 申请 Key' },
  { id: 'qwen', name: '通义千问', base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', hint: '阿里云百炼控制台申请 Key' },
  { id: 'kimi', name: 'Kimi', base: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k', hint: 'platform.moonshot.cn 申请 Key' },
  { id: 'zhipu', name: '智谱', base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash', hint: 'bigmodel.cn 申请 Key' },
]
