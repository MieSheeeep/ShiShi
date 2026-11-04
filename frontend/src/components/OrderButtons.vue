<script setup>
import { ArrowUp, ArrowDown } from 'lucide-vue-next'
defineProps({index:Number,total:Number,label:String})
defineEmits(['move'])
</script>
<template><div class="order-buttons"><button type="button" :disabled="index===0" :aria-label="label+'上移'" @click="$emit('move',-1)"><ArrowUp :size="15"/></button><button type="button" :disabled="index===total-1" :aria-label="label+'下移'" @click="$emit('move',1)"><ArrowDown :size="15"/></button></div></template>
