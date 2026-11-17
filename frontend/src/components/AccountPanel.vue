<script setup>
import { onMounted, ref } from 'vue'
import { Check, KeyRound, LogOut, ShieldAlert, UserRound, X } from 'lucide-vue-next'
import { api, clearToken } from '../recipeEditing'
import { AI_PROVIDERS } from '../aiProviders'
import XhsLogin from './XhsLogin.vue'

const props = defineProps({ username: String })
const emit = defineEmits(['close', 'logout'])

const base = ref(''), model = ref(''), key = ref(''), hint = ref(''), picked = ref('')
const aiBusy = ref(false), testing = ref(false), aiError = ref(''), aiOk = ref('')

const oldPassword = ref(''), newPassword = ref(''), confirmPassword = ref('')
const passwordBusy = ref(false), passwordError = ref(''), passwordOk = ref('')

const deletePassword = ref(''), deleteBusy = ref(false), deleteError = ref(''), deleteConfirm = ref(false)

onMounted(async () => {
  try {
    const data = await api('/ai/settings')
    base.value = data.base
    model.value = data.model
    hint.value = data.key_hint
  } catch {}
})

function choose(provider) {
  picked.value = provider.id
  base.value = provider.base
  model.value = provider.model
  aiOk.value = ''
}

function payload() {
  return { base: base.value, model: model.value, key: key.value }
}

async function saveAi() {
  aiBusy.value = true; aiError.value = ''; aiOk.value = ''
  try {
    const data = await api('/ai/settings', 'PUT', payload())
    hint.value = data.key_hint
    key.value = ''
    aiOk.value = 'AI 配置已更新'
  } catch (e) { aiError.value = e.message } finally { aiBusy.value = false }
}

async function verifyAi() {
  testing.value = true; aiError.value = ''; aiOk.value = ''
  try {
    await api('/ai/verify', 'POST', payload())
    aiOk.value = 'Key 可用'
  } catch (e) { aiError.value = e.message } finally { testing.value = false }
}

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) { passwordError.value = '两次输入的新密码不一致'; return }
  passwordBusy.value = true; passwordError.value = ''; passwordOk.value = ''
  try {
    await api('/auth/password', 'PATCH', { old_password: oldPassword.value, new_password: newPassword.value })
    oldPassword.value = newPassword.value = confirmPassword.value = ''
    passwordOk.value = '密码已更新，其他设备的登录已失效'
  } catch (e) { passwordError.value = e.message } finally { passwordBusy.value = false }
}

async function deleteAccount() {
  deleteBusy.value = true; deleteError.value = ''
  try {
    await api('/auth/account', 'DELETE', { password: deletePassword.value })
    clearToken()
    emit('logout')
  } catch (e) { deleteError.value = e.message; deleteConfirm.value = false } finally { deleteBusy.value = false }
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <section class="modal account-panel">
      <button class="close" aria-label="关闭" @click="emit('close')"><X /></button>
      <span class="modal-icon"><UserRound /></span>
      <div class="eyebrow">YOUR KITCHEN ACCOUNT</div>
      <h2>账号管理</h2>
      <p class="muted">{{ props.username }} · 数据只保存在这台电脑</p>

      <section class="account-block">
        <h3><KeyRound :size="16" /> AI 接口</h3>
        <p v-if="hint" class="muted small">当前 Key：{{ hint }}</p>
        <div class="provider-picks">
          <button v-for="provider in AI_PROVIDERS" :key="provider.id" type="button"
            :class="['provider-pick', { picked: picked === provider.id }]" @click="choose(provider)">
            {{ provider.name }}<Check v-if="picked === provider.id" :size="14" />
          </button>
        </div>
        <label>API 地址<input v-model="base" placeholder="https://api.deepseek.com/v1" /></label>
        <label>模型名<input v-model="model" placeholder="deepseek-chat" /></label>
        <label>新的 API Key<input v-model="key" type="password" autocomplete="off" :placeholder="hint ? '留空则沿用当前 Key' : 'sk-…'"/></label>
        <div v-if="aiError" class="alert" role="alert">{{ aiError }}</div>
        <p v-if="aiOk" class="ai-ok">{{ aiOk }}</p>
        <div class="ai-actions">
          <button class="secondary" :disabled="testing || aiBusy" @click="verifyAi">{{ testing ? '验证中…' : '验证 Key' }}</button>
          <button class="primary" :disabled="aiBusy || !base.trim() || !model.trim()" @click="saveAi">{{ aiBusy ? '保存中…' : '保存 AI 配置' }}</button>
        </div>
      </section>

      <XhsLogin />

      <section class="account-block">
        <h3>修改密码</h3>
        <label>当前密码<input v-model="oldPassword" type="password" autocomplete="current-password" /></label>
        <label>新密码<input v-model="newPassword" type="password" autocomplete="new-password" placeholder="至少 6 位" /></label>
        <label>确认新密码<input v-model="confirmPassword" type="password" autocomplete="new-password" /></label>
        <div v-if="passwordError" class="alert" role="alert">{{ passwordError }}</div>
        <p v-if="passwordOk" class="ai-ok">{{ passwordOk }}</p>
        <button class="primary wide" :disabled="passwordBusy || !oldPassword || !newPassword" @click="changePassword">{{ passwordBusy ? '更新中…' : '更新密码' }}</button>
      </section>

      <section class="account-block">
        <h3><LogOut :size="16" /> 登录状态</h3>
        <p class="muted small">退出后需要重新输入用户名和密码，数据仍保存在本机。</p>
        <button class="secondary wide" @click="emit('logout')">退出登录</button>
      </section>

      <section class="account-block danger-block">
        <h3><ShieldAlert :size="16" /> 注销账号</h3>
        <p class="muted small">删除后，食谱、标签、采购清单与设置都会从本机永久移除，无法恢复。</p>
        <template v-if="!deleteConfirm">
          <button class="danger-outline wide" @click="deleteConfirm=true">注销账号</button>
        </template>
        <template v-else>
          <label>输入密码确认<input v-model="deletePassword" type="password" autocomplete="current-password" /></label>
          <div v-if="deleteError" class="alert" role="alert">{{ deleteError }}</div>
          <div class="ai-actions">
            <button class="secondary" @click="deleteConfirm=false;deleteError='';deletePassword=''">再想想</button>
            <button class="danger-solid" :disabled="deleteBusy || !deletePassword" @click="deleteAccount">{{ deleteBusy ? '删除中…' : '确认永久删除' }}</button>
          </div>
        </template>
      </section>
    </section>
  </div>
</template>
