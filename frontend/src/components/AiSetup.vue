<script setup>
import { onMounted, ref } from 'vue'
import { Check, Sparkles, X } from 'lucide-vue-next'
import { api } from '../recipeEditing'
import { AI_PROVIDERS } from '../aiProviders'

const emit = defineEmits(['close', 'saved'])
const base = ref(''), model = ref(''), key = ref(''), picked = ref('')
const busy = ref(false), testing = ref(false), error = ref(''), ok = ref('')

onMounted(async () => {
  try {
    const data = await api('/ai/settings')
    base.value = data.base
    model.value = data.model
  } catch {}
})

function choose(provider) {
  picked.value = provider.id
  base.value = provider.base
  model.value = provider.model
  ok.value = ''
}

function payload() {
  return { base: base.value, model: model.value, key: key.value }
}

async function verify() {
  testing.value = true; error.value = ''; ok.value = ''
  try {
    await api('/ai/verify', 'POST', payload())
    ok.value = 'Key 可用，可以保存了'
  } catch (e) { error.value = e.message } finally { testing.value = false }
}

async function save() {
  busy.value = true; error.value = ''
  try {
    await api('/ai/settings', 'PUT', payload())
    emit('saved')
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <section class="modal ai-setup">
      <button class="close" aria-label="关闭" @click="emit('close')"><X /></button>
      <span class="modal-icon"><Sparkles /></span>
      <div class="eyebrow">SET UP YOUR AI</div>
      <h2>配置启动 AI 服务</h2>
      <div class="provider-picks">
        <button v-for="provider in AI_PROVIDERS" :key="provider.id" type="button"
          :class="['provider-pick', { picked: picked === provider.id }]" @click="choose(provider)">
          {{ provider.name }}<Check v-if="picked === provider.id" :size="14" />
        </button>
      </div>
      <p v-if="picked" class="provider-hint">{{ AI_PROVIDERS.find(p => p.id === picked).hint }}</p>
      <label>API 地址<input v-model="base" placeholder="https://api.deepseek.com/v1" /></label>
      <label>模型名<input v-model="model" placeholder="deepseek-chat" /></label>
      <label>API Key<input v-model="key" type="password" autocomplete="off" placeholder="sk-…"/></label>
      <div v-if="error" class="alert" role="alert">{{ error }}</div>
      <p v-if="ok" class="ai-ok">{{ ok }}</p>
      <div class="ai-actions">
        <button class="secondary" :disabled="testing || busy" @click="verify">{{ testing ? '验证中…' : '验证 Key' }}</button>
        <button class="primary" :disabled="busy || !base.trim() || !model.trim() || !key.trim()" @click="save">{{ busy ? '保存中…' : '保存并启用 AI' }}</button>
      </div>
      <button class="text-button ai-later" @click="emit('close')">稍后再说</button>
    </section>
  </div>
</template>
