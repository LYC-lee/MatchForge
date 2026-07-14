import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/Home.vue'),
  },
  {
    path: '/rfq',
    name: 'rfq',
    component: () => import('@/views/Rfq.vue'),
  },
  {
    path: '/suppliers',
    name: 'suppliers',
    component: () => import('@/views/Suppliers.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
