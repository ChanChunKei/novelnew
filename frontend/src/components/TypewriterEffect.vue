<template>
  <h1 class="typewriter text-4xl md:text-5xl font-extrabold text-center text-gray-800 tracking-wider" :style="{ '--char-count': fullText.length }">
    {{ displayedText }}
  </h1>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  text: {
    type: String,
    required: true,
  },
});

const fullText = props.text;
const displayedText = ref('');
let index = 0;
// ✅ 修复：保存定时器引用，防止内存泄漏
let interval: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  interval = setInterval(() => {
    if (index < fullText.length) {
      displayedText.value += fullText.charAt(index);
      index++;
    } else {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    }
  }, 150); // Adjust typing speed here
});

// ✅ 修复：组件卸载时清理定时器
onUnmounted(() => {
  if (interval) {
    clearInterval(interval);
    interval = null;
  }
});
</script>

<style scoped>
.typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  border-right: 0.1em solid #333; /* Blinking cursor */
  animation: typing 2s steps(var(--char-count, 10), end), blink-caret 0.75s step-end infinite;
  width: 100%;
}

/* Typing effect */
@keyframes typing {
  from {
    width: 0;
  }
  to {
    width: 100%;
  }
}

/* Cursor blinking effect */
@keyframes blink-caret {
  from,
  to {
    border-color: transparent;
  }
  50% {
    border-color: #333;
  }
}
</style>
