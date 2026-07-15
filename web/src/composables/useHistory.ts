import type { ProcureState } from '@/types/procure'

const KEY = 'matchforge:history'

export interface HistoryRecord {
  id: string
  thread_id: string
  raw_query: string
  created_at: string
  rfq_sent: boolean
  state: ProcureState
}

function load(): HistoryRecord[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

function persist(list: HistoryRecord[]) {
  localStorage.setItem(KEY, JSON.stringify(list))
}

export function useHistory() {
  function list(): HistoryRecord[] {
    return load().sort((a, b) => b.created_at.localeCompare(a.created_at))
  }

  function get(id: string): HistoryRecord | undefined {
    return load().find((r) => r.id === id)
  }

  function saveRecord(r: HistoryRecord) {
    const all = load().filter((x) => x.id !== r.id)
    all.push(r)
    persist(all)
  }

  function remove(id: string) {
    persist(load().filter((x) => x.id !== id))
  }

  return { list, get, saveRecord, remove }
}
