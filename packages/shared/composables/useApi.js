import { ref } from 'vue'

export function useApi({ storageKey, headerName }) {
  const authKey = ref(localStorage.getItem(storageKey) || '')

  const setAuthKey = (key) => {
    authKey.value = key
    localStorage.setItem(storageKey, key)
  }

  const clearAuthKey = () => {
    authKey.value = ''
    localStorage.removeItem(storageKey)
  }

  const apiFetch = async (path, options = {}) => {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        [headerName]: authKey.value,
        ...(options.headers || {}),
      },
    })
    if (res.status === 401) {
      throw new Error('Unauthorized')
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.error || `API error: ${res.status}`)
    }
    return res.json()
  }

  return { authKey, setAuthKey, clearAuthKey, apiFetch }
}
