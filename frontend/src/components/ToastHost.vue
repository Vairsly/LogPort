<template>
  <div class="toast" :class="{ show: !!message }">{{ message }}</div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '' }
})
</script>
