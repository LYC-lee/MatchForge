<script setup lang="ts">
import { RouterLink } from 'vue-router'

const features = [
  { title: '自然语言寻源', desc: '用一句话描述元器件需求,AI 自动解析规格。' },
  { title: '替代料推荐', desc: '基于知识图谱推荐兼容替代型号。' },
  { title: '供应商匹配', desc: '向量检索匹配有库存的供应商,按相关度排序。' },
  { title: '询价单生成', desc: '一键生成标准化 RFQ,线索分级推给上游。' },
]
</script>

<template>
  <section class="hero">
    <h1>AI 供需对接平台</h1>
    <p class="tagline">
      采购用自然语言描述原材料需求 → AI 解析规格 → 推荐替代料 → 匹配供应商 → 生成询价单
    </p>
    <RouterLink to="/rfq" class="cta">开始智能寻源 →</RouterLink>
  </section>

  <section class="features">
    <div v-for="f in features" :key="f.title" class="feature-card">
      <h3>{{ f.title }}</h3>
      <p>{{ f.desc }}</p>
    </div>
  </section>
</template>
