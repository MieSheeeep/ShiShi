<script setup>
import { X, Clock3, Users, Pencil, Trash2, ArrowUpRight, Plus, Flame } from 'lucide-vue-next'
const props = defineProps({ recipe: Object, selected: Boolean, done: Object })
defineEmits(['close', 'edit', 'remove', 'toggle', 'cook'])
const sourceName = () => props.recipe.source.platform === 'xiaohongshu' ? '小红书' : '豆果美食'
</script>
<template>
  <div class="overlay" @click.self="$emit('close')">
    <section class="modal detail">
      <button class="close" @click="$emit('close')" aria-label="关闭详情"><X /></button>
      <div v-if="recipe.cover" class="detail-cover"><img :src="recipe.cover" :alt="recipe.name + '成品图'" /></div>
      <div v-else class="detail-emoji">{{ recipe.emoji || '🍲' }}</div>
      <h2>{{ recipe.name }}</h2>
      <div class="detail-meta">
        <span><Clock3 :size="15" />{{ recipe.minutes ? recipe.minutes + ' 分钟' : '耗时未注明' }}</span>
        <span><Users :size="15" />{{ recipe.servings || '份数未注明' }}</span>
        <span>{{ recipe.source.author || '自建菜谱' }}</span>
      </div>
      <div v-if="recipe.tags.length" class="selected-tags detail-tags">
        <span v-for="tag in recipe.tags" :key="tag.id" class="selected-tag">{{ tag.group }} · {{ tag.name }}</span>
      </div>
      <div class="detail-actions">
        <button class="primary" @click="$emit('cook', recipe.id)"><Flame :size="15" />开始做菜</button>
        <button class="secondary" @click="$emit('toggle', recipe.id)"><Plus :size="15" />{{ selected ? '移出菜单' : '加入菜单' }}</button>
        <button class="secondary" @click="$emit('edit', recipe)"><Pencil :size="15" />编辑</button>
        <a v-if="recipe.source.url" :href="recipe.source.url" target="_blank" rel="noopener noreferrer" class="secondary">{{ sourceName() }}原文<ArrowUpRight :size="15" /></a>
        <button class="icon-button danger" @click="$emit('remove', recipe)" aria-label="删除食谱"><Trash2 :size="17" /></button>
      </div>
      <details v-if="recipe.source.original_text" class="source-text"><summary>查看导入原文</summary><p class="original-body">{{ recipe.source.original_text }}</p></details>
      <section v-if="recipe.images.length" class="original-gallery">
        <h3>图集</h3>
        <div class="image-grid"><a v-for="(url, index) in recipe.images" :key="url" :href="url" target="_blank" rel="noopener noreferrer"><img :src="url" :alt="'图集图片' + (index + 1)" loading="lazy" /></a></div>
      </section>
      <h3>准备材料 <span>{{ recipe.ingredients.length }} 项</span></h3>
      <div v-for="item in recipe.ingredients" :key="item.id" class="ingredient-line"><span>{{ item.name }}<small v-if="item.kind === '调料'">调料</small></span><strong>{{ item.amount || '适量' }}</strong></div>
      <h3>步骤 <span>{{ recipe.steps.length }} 步</span></h3>
      <label v-for="(step, index) in recipe.steps" :key="step.id" class="cooking-step" :class="{ isdone: done[step.id] }">
        <input type="checkbox" v-model="done[step.id]" />
        <span class="step-number">{{ String(index + 1).padStart(2, '0') }}</span>
        <div class="cooking-step-content">
          <p>{{ step.text }}</p>
          <div v-if="step.images.length" class="step-pictures"><a v-for="(url, pictureIndex) in step.images" :key="url" :href="url" target="_blank" rel="noopener noreferrer" @click.stop><img :src="url" :alt="'步骤' + (index + 1) + '配图' + (pictureIndex + 1)" loading="lazy" /></a></div>
        </div>
      </label>
      <div v-if="recipe.notes" class="recipe-note"><strong>备注</strong><p>{{ recipe.notes }}</p></div>
      <button class="primary wide" @click="$emit('cook', recipe.id)"><Flame :size="17" />开始做这道菜</button>
    </section>
  </div>
</template>
