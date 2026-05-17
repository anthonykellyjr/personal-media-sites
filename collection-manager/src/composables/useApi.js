import { useApi as useSharedApi } from '@webhead/shared'

const api = useSharedApi({
  storageKey: 'collection_manager_admin_key',
  headerName: 'X-Admin-Key'
})

export function useApi() {
  return {
    adminKey: api.authKey,
    setAdminKey: api.setAuthKey,
    clearAdminKey: api.clearAuthKey,
    apiFetch: api.apiFetch
  }
}
