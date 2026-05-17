import { useApi as useSharedApi } from '@webhead/shared'

const api = useSharedApi({
  storageKey: 'kelly_collection_key',
  headerName: 'X-Kelly-Key'
})

export function useApi() {
  return {
    kellyKey: api.authKey,
    setKellyKey: api.setAuthKey,
    clearKellyKey: api.clearAuthKey,
    apiFetch: api.apiFetch
  }
}
