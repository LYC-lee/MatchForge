import { onMounted, onUnmounted } from 'vue'

export const DEMO_REFRESH_EVENT = 'matchforge:demo-refresh'

export function emitDemoRefresh() {
  window.dispatchEvent(new CustomEvent(DEMO_REFRESH_EVENT))
}

export function onDemoRefresh(handler: () => void | Promise<void>) {
  const listener = () => {
    void handler()
  }

  onMounted(() => window.addEventListener(DEMO_REFRESH_EVENT, listener))
  onUnmounted(() => window.removeEventListener(DEMO_REFRESH_EVENT, listener))
}
