<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../recipeEditing'

const cookie = ref(''), hint = ref(''), source = ref('')
const busy = ref(false), error = ref(''), ok = ref('')

onMounted(load)

async function load() {
  try {
    const data = await api('/xhs/settings')
    hint.value = data.cookie_hint
    source.value = data.source
  } catch {}
}

async function save() {
  busy.value = true; error.value = ''; ok.value = ''
  try {
    const data = await api('/xhs/settings', 'PUT', { cookie: cookie.value })
    hint.value = data.cookie_hint
    source.value = data.source
    cookie.value = ''
    ok.value = '已保存，导入小红书笔记会带上登录态'
  } catch (e) { error.value = e.message } finally { busy.value = false }
}

async function clear() {
  busy.value = true; error.value = ''; ok.value = ''
  try {
    await api('/xhs/settings', 'PUT', { cookie: '' })
    hint.value = ''; source.value = ''
    ok.value = '已清除小红书登录态'
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>

<template>
  <section class="xhs-login">
    <h3>小红书登录态</h3>
    <p v-if="hint" class="muted small">已保存：{{ hint }}<span v-if="source==='environment'">（来自环境变量 XHS_COOKIE，账号配置优先）</span></p>
    <p v-else class="muted small">部分笔记需要登录才能读取。在浏览器登录小红书后，从开发者工具复制 Cookie 粘贴到这里；失效时重新复制一次即可。</p>
    <label>Cookie<textarea v-model="cookie" rows="2" placeholder="web_session=…; a1=…"/></label>
    <div v-if="error" class="alert" role="alert">{{ error }}</div>
    <p v-if="ok" class="ai-ok">{{ ok }}</p>
    <div class="ai-actions">
      <button class="secondary" :disabled="busy || source!=='account'" @click="clear">清除登录态</button>
      <button class="primary" :disabled="busy || !cookie.trim()" @click="save">{{ busy ? '保存中…' : '保存 Cookie' }}</button>
    </div>
  </section>
</template>

<style scoped>
.xhs-login{margin-top:20px;padding-top:16px;border-top:1px solid var(--border)}
.xhs-login h3{margin:0 0 6px;font-size:14px}
.xhs-login label{display:block;margin-top:10px;font-size:12px;color:var(--muted)}
.xhs-login textarea{margin-top:6px;width:100%;padding:9px 11px;border:1px solid var(--border);border-radius:8px;font:inherit;font-size:13px;resize:vertical}
</style>
