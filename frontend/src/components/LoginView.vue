<script setup>
import { ref, computed } from 'vue'
import { Leaf, ArrowRight } from 'lucide-vue-next'
import { api, setToken } from '../recipeEditing'
const emit=defineEmits(['authenticated'])
const mode=ref('login'), username=ref(''), password=ref(''), confirm=ref(''), busy=ref(false), error=ref('')
const register=computed(()=>mode.value==='register')
function toggle(){mode.value=register.value?'login':'register';error.value='';confirm.value=''}
async function submit(){
  if(register.value&&password.value!==confirm.value){error.value='两次输入的密码不一致';return}
  busy.value=true;error.value=''
  try{
    const data=await api('/auth/'+(register.value?'register':'login'),'POST',{username:username.value,password:password.value})
    setToken(data.token)
    emit('authenticated',data)
  }catch(e){error.value=e.message}finally{busy.value=false}
}
</script>
<template>
<div class="auth-screen">
  <section class="auth-card">
    <div class="auth-brand"><span class="auth-symbol"><Leaf :size="24"/></span><div>食拾<small>SHI SHI</small></div></div>
    <div class="eyebrow">YOUR PRIVATE KITCHEN</div>
    <h1>{{register?'开一间自己的小厨房':'欢迎回到小厨房'}}</h1>
    <p class="muted">{{register?'注册后即可收藏食谱、整理食材和合并采购清单。':'登录后继续整理你的食谱、标签和采购清单。'}}</p>
    <form @submit.prevent="submit">
      <label>用户名<input v-model="username" required minlength="3" maxlength="32" autocomplete="username" placeholder="3-32 个字符，不能包含空格"/></label>
      <label>密码<input v-model="password" type="password" required minlength="6" maxlength="128" :autocomplete="register?'new-password':'current-password'" placeholder="至少 6 个字符"/></label>
      <label v-if="register">确认密码<input v-model="confirm" type="password" required minlength="6" maxlength="128" autocomplete="new-password" placeholder="再输入一次密码"/></label>
      <p v-if="error" class="alert" role="alert">{{error}}</p>
      <button class="primary wide" :disabled="busy">{{busy?'请稍候…':(register?'注册并进入':'登录')}} <ArrowRight :size="16"/></button>
    </form>
    <p class="auth-switch">{{register?'已经有账号了？':'还没有账号？'}}<button type="button" class="text-button" @click="toggle">{{register?'直接登录':'注册新账号'}}</button></p>
    <p class="auth-note"><Leaf :size="14"/> 每个账号的食谱、标签和清单相互独立，数据保存在本机。</p>
  </section>
</div>
</template>
<style scoped>
.auth-screen{min-height:100vh;display:grid;place-items:center;padding:32px 18px;background:radial-gradient(circle at 18% 12%,#eef1e4,#f8f9f5 52%,#f3f4ec)}
.auth-card{width:min(430px,100%);background:#fcfcf8;border:1px solid #e7eae2;border-radius:18px;padding:42px 38px 34px;box-shadow:0 24px 70px #233f3214}
.auth-brand{display:flex;align-items:center;gap:12px;font-family:serif;font-size:27px;font-weight:bold;letter-spacing:4px;margin-bottom:34px}
.auth-symbol{width:42px;height:46px;display:grid;place-items:center;background:#2e5945;color:#fff;border-radius:14px 14px 14px 4px;transform:rotate(-4deg)}
.auth-brand small{display:block;font:8px sans-serif;letter-spacing:4px;margin-top:4px;color:#879087}
.auth-card h1{font-size:26px;margin:0 0 12px}
.auth-card label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:#73806a;margin-bottom:16px}
.auth-card .wide{margin-top:6px}
.auth-switch{font-size:12px;color:#8d9587;margin:20px 0 0;display:flex;gap:6px;align-items:center}
.auth-note{display:flex;gap:6px;align-items:center;font-size:10px;line-height:1.7;color:#9ba28f;border-top:1px solid #eceee6;margin:26px 0 0;padding-top:18px}
</style>