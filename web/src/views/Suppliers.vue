<script setup lang="ts">
const suppliers = [
  { name: '深圳华强电子世界', region: '华南', parts: 12000, verified: true },
  { name: '上海赛格电子市场', region: '华东', parts: 8600, verified: true },
  { name: '北京中发电子市场', region: '华北', parts: 5400, verified: false },
]
</script>

<template>
  <section class="suppliers">
    <h2>供应商目录</h2>
    <p class="hint">已接入的供应商资源(示例数据,后续对接后端 /api/suppliers)</p>
    <table>
      <thead>
        <tr><th>供应商</th><th>区域</th><th>在售料号</th><th>认证</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in suppliers" :key="s.name">
          <td>{{ s.name }}</td>
          <td>{{ s.region }}</td>
          <td>{{ s.parts.toLocaleString() }}</td>
          <td>
            <span class="badge" :class="s.verified ? 'ok' : 'pending'">
              {{ s.verified ? '已认证' : '待审核' }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
