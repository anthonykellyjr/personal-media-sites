<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import MovieGrid from './components/MovieGrid.vue'
import NavCard from './components/NavCard.vue'
import { Toast, Modal, HelpTip } from '@webhead/shared'

import faviconImg from './assets/favicon.webp'
import blockbusterImg from './assets/blockbuster.jpg'
import technicalDiffImg from './assets/technical-diff-transparent.webp'

// ─── Header widget toggles ──────────────────────────────────────────────
// Build-time on/off switches for the header. Flip a boolean and rebuild
// (./deploy.sh status-hub) to hide/show a widget without touching markup.
// Order in the header follows template order, not this object.
const HEADER_WIDGETS = {
  bandwidth: true,     // upload Mbps pill
  cpu: true,           // CPU % pill
  gpu: true,           // GPU pill (temp + utilization combined)
  ram: true,           // RAM % pill
  activeStreams: true, // "● N Active" streams pill
}

// Announcement
const announcement = ref({ enabled: false, message: '', severity: 'info', dismissible: true, dismissed: false })

// Welcome message
const welcomeMessage = ref({ show: false })
const checkWelcome = () => {
  const hasSeenWelcome = localStorage.getItem('akplex_welcome_seen')
  if (!hasSeenWelcome) {
    welcomeMessage.value.show = true
    setTimeout(() => { dismissWelcome() }, 4000)
  }
}
const dismissWelcome = () => {
  welcomeMessage.value.show = false
  localStorage.setItem('akplex_welcome_seen', 'true')
}

const announcementClass = computed(() => {
  const classes = {
    red: 'bg-gradient-to-br from-red-900 to-red-800 border-red-600',
    yellow: 'bg-gradient-to-br from-amber-900 to-amber-800 border-amber-500',
    green: 'bg-gradient-to-br from-green-900 to-green-800 border-green-500',
    resolved: 'bg-gradient-to-br from-teal-900 via-cyan-900 to-blue-900 border-teal-500',
    info: 'bg-gradient-to-br from-blue-900 to-blue-800 border-blue-500'
  }
  return classes[announcement.value.severity] || classes.info
})

const announcementIcon = computed(() => {
  const icons = { 
    red: '🛑', 
    yellow: '⚠️', 
    green: '✅', 
    resolved: '🔄', 
    info: 'ℹ️' 
  }
  return icons[announcement.value.severity] || icons.info
})

const dismissAnnouncement = () => {
  announcement.value.dismissed = true
  // Store the version that was dismissed - new announcements get new versions
  if (announcement.value.version) {
    localStorage.setItem('announcement_dismissed_version', announcement.value.version.toString())
  }
}

const fetchAnnouncement = async () => {
  try {
    const res = await fetch('/api/announcement')
    if (!res.ok) return
    const data = await res.json()
    // Check if expired
    if (data.expiresAt && Date.now() > data.expiresAt) {
      data.enabled = false // Treat as disabled if expired
    }
    // Check if this specific version was already dismissed
    // New announcements get new versions, so previously dismissed won't match
    const dismissedVersion = localStorage.getItem('announcement_dismissed_version')
    const isDismissed = data.version && dismissedVersion === data.version.toString()
    announcement.value = { ...data, dismissed: isDismissed }
  } catch {}
}

// Stats (merged: streams + plex health + bandwidth)
const stats = ref({ streams: 0, bandwidthMbps: 0, plexOnline: null })
const statsError = ref(false)

const fetchStats = async () => {
  try {
    const res = await fetch('/api/tautulli-stats')
    if (!res.ok) { statsError.value = true; return }
    const data = await res.json()
    const bwKbps = data.totalBandwidthKbps || 0
    stats.value = {
      streams: data.activeStreams || 0,
      bandwidthMbps: (bwKbps / 1000).toFixed(1),
      plexOnline: data.plexOnline ?? null
    }
    statsError.value = false
  } catch { statsError.value = true }
}

// Disk Health (Scrutiny)
const diskHealth = ref({ total: 0, healthy: 0, warning: 0, failed: 0 })
const diskHealthError = ref(false)

const fetchDiskHealth = async () => {
  try {
    const res = await fetch('/api/disk-health')
    if (!res.ok) { diskHealthError.value = true; return }
    diskHealth.value = await res.json()
    diskHealthError.value = false
  } catch { diskHealthError.value = true }
}

// Speedtest
const speedtest = ref({ uploadMbps: 0 })
const speedtestError = ref(false)

const fetchSpeedtest = async () => {
  try {
    const res = await fetch('/api/speedtest')
    if (!res.ok) { speedtestError.value = true; return }
    speedtest.value = await res.json()
    speedtestError.value = false
  } catch { speedtestError.value = true }
}

const formatBandwidth = (mbps) => {
  const val = parseFloat(mbps)
  if (val >= 1000) return (val / 1000).toFixed(1) + ' Gbps'
  return val.toFixed(1) + ' Mbps'
}

// System Stats (CPU, Mem, Disk)
const sysStats = ref({ cpuPercent: null, memPercent: null, diskUsedTB: null, diskTotalTB: null, gpuTempC: null, gpuUtilPercent: null })

const fetchSysStats = async () => {
  try {
    const res = await fetch('/api/system-stats')
    if (!res.ok) return
    sysStats.value = await res.json()
  } catch {}
}

const overseerrStatus = ref({ status: 'checking', message: 'Checking...' })

const fetchOverseerrStatus = async () => { 
  try {
    const res = await fetch('/api/overseerr-status')
    if (!res.ok) {
      overseerrStatus.value = { status: 'offline', message: 'API error' }
      return
    }
    const data = await res.json()
    overseerrStatus.value = data
  } catch {
    overseerrStatus.value = { status: 'offline', message: 'Connection failed' }
  }
}

// Calendar
const episodes = ref([])
const calendarExpanded = ref(false)
const calendarError = ref(false)
const calendarScroll = ref(null)
const calendarCanScrollLeft = ref(false)
const calendarCanScrollRight = ref(false)
const checkCalendarScroll = () => {
  const el = calendarScroll.value
  if (!el) return
  calendarCanScrollLeft.value = el.scrollLeft > 4
  calendarCanScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 4
}
const scrollCalendarLeft = () => {
  const el = calendarScroll.value
  if (!el) return
  el.scrollBy({ left: -el.clientWidth * 0.75, behavior: 'smooth' })
}
const scrollCalendarRight = () => {
  const el = calendarScroll.value
  if (!el) return
  el.scrollBy({ left: el.clientWidth * 0.75, behavior: 'smooth' })
}

const fetchCalendar = async () => {
  try {
    const res = await fetch('/api/calendar')
    if (!res.ok) { calendarError.value = true; return }
    const data = await res.json()
    episodes.value = data.episodes || []
    calendarError.value = false
    nextTick(checkCalendarScroll)
  } catch { calendarError.value = true }
}

// Group episodes
const calendarDays = computed(() => {
  const now = new Date()
  const days = []

  // Yesterday (i=-1) through 6 days out (i=5) = 7 days total.
  // Backend already fetches now-2 → now+7, so no extra Sonarr cost.
  for (let i = -1; i < 6; i++) {
    const date = new Date(now)
    date.setDate(date.getDate() + i)
    date.setHours(0, 0, 0, 0)

    const dayName = i === -1 ? 'Yesterday' :
                    i === 0 ? 'Today' :
                    i === 1 ? 'Tomorrow' :
                    date.toLocaleDateString('en-US', { weekday: 'short' })
    const dateLabel = date.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' })

    days.push({
      date: date.toDateString(),
      dayName,
      dateLabel,
      isToday: i === 0,
      episodes: []
    })
  }

  episodes.value.forEach(ep => {
    if (!ep.airDateUtc) return
    const epDate = new Date(ep.airDateUtc)
    const epDateStr = epDate.toDateString()

    const day = days.find(d => d.date === epDateStr)
    if (day) {
      const aired = epDate < now
      const status = ep.hasFile ? 'available' : aired ? 'missing' : 'upcoming'
      day.episodes.push({
        ...ep,
        airTime: epDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
        status
      })
    }
  })

  days.forEach(day => {
    const seriesCounts = {}
    day.episodes.forEach(ep => {
      seriesCounts[ep.seriesTitle] = (seriesCounts[ep.seriesTitle] || 0) + 1
    })

    day.episodes.sort((a, b) => {
      const countA = seriesCounts[a.seriesTitle]
      const countB = seriesCounts[b.seriesTitle]
      if (countA !== countB) return countA - countB
      return new Date(a.airDateUtc) - new Date(b.airDateUtc)
    })
  })

  return days
})

// Search
const searchQuery = ref('')
const searchInput = ref(null)
const searchResults = ref([])
const searchLoading = ref(false)
let searchDebounce = null

const onSearchInput = () => {
  clearTimeout(searchDebounce)
  const q = searchQuery.value.trim()
  if (q.length < 2) { searchResults.value = []; return }
  searchLoading.value = true
  searchDebounce = setTimeout(async () => {
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      searchResults.value = data.results || []
    } catch { searchResults.value = [] }
    searchLoading.value = false
  }, 300)
}

const handleSearch = () => {
  if (searchResults.value.length === 1) {
    window.open(searchResults.value[0].url, '_blank')
    searchQuery.value = ''
    searchResults.value = []
  }
}

const pickResult = (result) => {
  window.open(result.url, '_blank')
  searchQuery.value = ''
  searchResults.value = []
}

// Toast notification
const toastShow = ref(false)
const toastMessage = ref('')
const toastType = ref('success')

// Quick issue report from search results
const reportedKey = ref(null)
const reportIssue = async (result) => {
  reportedKey.value = result.ratingKey
  try {
    await fetch('/api/issue-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: result.title,
        mediaType: result.type === 'movie' ? 'Movie' : 'TV',
        issueLabel: 'Playback issue (reported from search)',
        year: result.year || ''
      })
    })
    toastMessage.value = `Reported issue for "${result.title}"`
    toastType.value = 'success'
  } catch {
    toastMessage.value = 'Failed to report issue'
    toastType.value = 'error'
  }
  toastShow.value = true
  searchResults.value = searchResults.value.filter(r => r.ratingKey !== result.ratingKey)
  if (searchResults.value.length === 0) searchQuery.value = ''
  reportedKey.value = null
}

// ─── Quick Request ──────────────────────────────────────────────────────
// Modal triggered from the "Quick Request" app cell. Two flows:
//   1. Type-to-search Seerr; pick a result -> POST /api/quick-request
//      (creates a real Seerr request AND a matched text_request entry).
//   2. "Can't find it?" -> free-text falls back to POST /api/anon-request
//      (creates an unmatched text_request for later admin matching).
const quickOpen = ref(false)
const quickQuery = ref('')
const quickResults = ref([])
const quickLoading = ref(false)
const quickDebounce = ref(null)
const quickSending = ref(false)
const quickSent = ref(false)
const quickError = ref('')
const quickFallbackText = ref('')

const onQuickSearchInput = () => {
  quickError.value = ''
  if (quickDebounce.value) { clearTimeout(quickDebounce.value); quickDebounce.value = null }
  const q = quickQuery.value.trim()
  if (q.length < 2) { quickResults.value = []; quickLoading.value = false; return }
  quickLoading.value = true
  quickDebounce.value = setTimeout(async () => {
    try {
      const res = await fetch(`/api/seerr-search?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      quickResults.value = data.results || []
    } catch {
      quickResults.value = []
    }
    quickLoading.value = false
    quickDebounce.value = null
  }, 300)
}

const pickQuickResult = async (r) => {
  if (quickSending.value) return
  quickSending.value = true
  quickError.value = ''
  try {
    const res = await fetch('/api/quick-request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tmdbId: r.tmdbId, mediaType: r.mediaType, title: r.title, year: r.year })
    })
    const data = await res.json()
    if (res.ok && data.success) {
      quickSent.value = true
      quickQuery.value = ''
      quickResults.value = []
      setTimeout(() => { quickSent.value = false; quickOpen.value = false }, 1800)
    } else {
      quickError.value = data.error || 'Submission failed'
    }
  } catch (e) {
    quickError.value = e.message || 'Network error'
  }
  quickSending.value = false
}

const sendQuickFallback = async () => {
  const text = quickFallbackText.value.trim()
  if (!text || quickSending.value) return
  quickSending.value = true
  quickError.value = ''
  try {
    const res = await fetch('/api/anon-request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: text })
    })
    if (res.ok) {
      quickSent.value = true
      quickFallbackText.value = ''
      setTimeout(() => { quickSent.value = false; quickOpen.value = false }, 1800)
    } else {
      quickError.value = 'Submission failed'
    }
  } catch (e) {
    quickError.value = e.message || 'Network error'
  }
  quickSending.value = false
}

const closeQuickModal = () => {
  quickOpen.value = false
  quickQuery.value = ''
  quickResults.value = []
  quickFallbackText.value = ''
  quickError.value = ''
  quickSent.value = false
}

// ─── Quick Report ───────────────────────────────────────────────────────
// Modal triggered from the "Quick Report" app cell. Two flows in one modal:
//   1. Search Plex library -> select media -> pick an issue type ->
//      POST /api/issue-report (same backend as the /issues page).
//   2. General feedback textarea -> POST /api/general-message.
// Search results are filtered server-side via /api/seerr-status so only
// in-library media (status >= 3) shows up — issue reports for media we
// don't have wouldn't be actionable.
const reportOpen = ref(false)
const reportSearch = ref('')
const reportResults = ref([])
const reportLoading = ref(false)
const reportDebounce = ref(null)
const reportSelected = ref(null)
const reportIssueType = ref('')
const reportDetails = ref('')
const reportFeedback = ref('')
const reportSending = ref(false)
const reportSentKind = ref('')   // 'media' | 'feedback' | ''
const reportError = ref('')

const REPORT_TYPES = [
  { id: 'audio',     label: 'Audio' },
  { id: 'video',     label: 'Video' },
  { id: 'subtitles', label: 'Subtitles' },
  { id: 'buffering', label: 'Buffering' },
  { id: 'wrong',     label: 'Wrong File' },
  { id: 'quality',   label: 'Poor Quality' },
  { id: 'other',     label: 'Other' },
]

const onReportSearchInput = () => {
  reportError.value = ''
  if (reportDebounce.value) { clearTimeout(reportDebounce.value); reportDebounce.value = null }
  const q = reportSearch.value.trim()
  if (q.length < 2) { reportResults.value = []; reportLoading.value = false; return }
  reportLoading.value = true
  reportDebounce.value = setTimeout(async () => {
    try {
      const res = await fetch(`/api/seerr-search?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      const candidates = (data.results || []).slice(0, 8)
      const withStatus = await Promise.all(candidates.map(async (m) => {
        try {
          const sr = await fetch(`/api/seerr-status/${m.mediaType}/${m.tmdbId}`)
          const sd = await sr.json()
          return { ...m, status: sd.status }
        } catch { return { ...m, status: null } }
      }))
      // status 3 = processing, 4 = partially available, 5 = available
      reportResults.value = withStatus.filter(m => m.status >= 3)
    } catch {
      reportResults.value = []
    }
    reportLoading.value = false
    reportDebounce.value = null
  }, 300)
}

const pickReportResult = (r) => {
  reportSelected.value = r
  reportIssueType.value = ''
  reportDetails.value = ''
  reportSearch.value = ''
  reportResults.value = []
}

const clearReportSelection = () => {
  reportSelected.value = null
  reportIssueType.value = ''
  reportDetails.value = ''
}

const submitMediaReport = async () => {
  if (!reportSelected.value || !reportIssueType.value || reportSending.value) return
  reportSending.value = true
  reportError.value = ''
  const m = reportSelected.value
  const issueLabel = REPORT_TYPES.find(t => t.id === reportIssueType.value)?.label || reportIssueType.value
  try {
    const res = await fetch('/api/issue-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: m.title,
        year: m.year || '',
        mediaType: m.mediaType === 'tv' ? 'TV Show' : 'Movie',
        issueType: reportIssueType.value,
        issueLabel,
        details: reportDetails.value.trim(),
        tmdbId: m.tmdbId,
      })
    })
    if (res.ok) {
      reportSentKind.value = 'media'
      clearReportSelection()
      setTimeout(() => { closeReportModal() }, 1800)
    } else {
      reportError.value = 'Submission failed'
    }
  } catch (e) {
    reportError.value = e.message || 'Network error'
  }
  reportSending.value = false
}

const submitFeedback = async () => {
  const text = reportFeedback.value.trim()
  if (!text || reportSending.value) return
  reportSending.value = true
  reportError.value = ''
  try {
    const res = await fetch('/api/general-message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    })
    if (res.ok) {
      reportSentKind.value = 'feedback'
      reportFeedback.value = ''
      setTimeout(() => { closeReportModal() }, 1800)
    } else {
      reportError.value = 'Submission failed'
    }
  } catch (e) {
    reportError.value = e.message || 'Network error'
  }
  reportSending.value = false
}

const closeReportModal = () => {
  reportOpen.value = false
  reportSearch.value = ''
  reportResults.value = []
  clearReportSelection()
  reportFeedback.value = ''
  reportError.value = ''
  reportSentKind.value = ''
}

// ─── Request Status ────────────────────────────────────────────────────
// Modal triggered from the "Request Status" bookmark. Shows a compact view of
// every user-submitted request and whether it's been uploaded yet or is still
// pending. Reuses /api/recently-fulfilled (same endpoint movies-feed uses).
// Lazy-fetches on first modal open + refetches each time it's reopened to
// surface fresh state without polling continuously.
const requestStatusOpen = ref(false)
const requestStatusItems = ref([])
const requestStatusLoading = ref(false)
const requestStatusError = ref('')
const requestStatusActiveTab = ref('uploaded')  // default tab — happy path first
// Server-side version counter. Sentinel -1 forces the first version-check to
// trigger an initial full fetch even if the server's version happens to be 0.
let requestStatusVersionSeen = -1

const fetchRequestStatus = async () => {
  requestStatusLoading.value = true
  requestStatusError.value = ''
  try {
    const res = await fetch('/api/recently-fulfilled')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    requestStatusItems.value = data.requests || []
  } catch (e) {
    requestStatusError.value = e.message || 'Failed to load'
  }
  requestStatusLoading.value = false
}

// Cheap version-check (~20 bytes). Only triggers the full fetch when the
// server's version counter has changed — bumped on every admin action that
// affects the request list. Polled every 30s; backend stays quiet otherwise.
const checkRequestStatusVersion = async () => {
  try {
    const res = await fetch('/api/recently-fulfilled/version')
    if (!res.ok) return
    const { version } = await res.json()
    if (version !== requestStatusVersionSeen) {
      requestStatusVersionSeen = version
      await fetchRequestStatus()
    }
  } catch {}
}

const openRequestStatus = () => {
  requestStatusOpen.value = true
  fetchRequestStatus()
}

const requestStatusCounts = computed(() => {
  let uploaded = 0, pending = 0, searching = 0
  for (const r of requestStatusItems.value) {
    if (r.state === 'uploaded') uploaded++
    else if (r.state === 'searching') searching++
    else pending++
  }
  return { uploaded, pending, searching }
})

// Items partitioned by state so each modal tab can render its own list.
const requestStatusByState = computed(() => {
  const out = { uploaded: [], pending: [], searching: [] }
  for (const r of requestStatusItems.value) {
    if (r.state === 'uploaded') out.uploaded.push(r)
    else if (r.state === 'searching') out.searching.push(r)
    else out.pending.push(r)
  }
  return out
})

// Tab definitions for the Request Status modal. Counts come from the
// computed above; `accent` matches the in-tile state-pill colors.
const requestStatusTabs = computed(() => [
  { id: 'uploaded',  label: 'Uploaded',  count: requestStatusCounts.value.uploaded,  accent: 'emerald' },
  { id: 'pending',   label: 'Pending',   count: requestStatusCounts.value.pending,   accent: 'amber'   },
  { id: 'searching', label: 'Searching', count: requestStatusCounts.value.searching, accent: 'indigo'  },
])

// Tutorials
const tutorials = ref([])
const activeVideo = ref(null)
const fetchTutorials = async () => {
  try {
    const res = await fetch('/tutorials/videos/videos.json')
    if (res.ok) tutorials.value = await res.json()
  } catch {}
}

// Intervals
let announcementInterval, statsInterval, calendarInterval, overseerrStatusInterval, diskHealthInterval, speedtestInterval, sysStatsInterval, requestStatusInterval

onMounted(() => {
  checkWelcome()
  fetchAnnouncement()
  fetchStats()
  fetchCalendar()
  fetchOverseerrStatus()
  fetchDiskHealth()
  fetchSpeedtest()
  fetchSysStats()
  fetchTutorials()
  // Prime the version + load initial data in one shot (sentinel -1 ensures fetch fires)
  checkRequestStatusVersion()
  announcementInterval = setInterval(fetchAnnouncement, 300000)
  statsInterval = setInterval(fetchStats, 10000)
  calendarInterval = setInterval(fetchCalendar, 600000)
  overseerrStatusInterval = setInterval(fetchOverseerrStatus, 30000)
  diskHealthInterval = setInterval(fetchDiskHealth, 600000)
  speedtestInterval = setInterval(fetchSpeedtest, 1800000)
  sysStatsInterval = setInterval(fetchSysStats, 15000)
  // Cheap version-check every 30s — only fetches the heavy payload when the
  // server's counter has changed (admin action invalidates it). Visibility
  // listener also pings the version on tab refocus for instant feedback.
  requestStatusInterval = setInterval(checkRequestStatusVersion, 30000)
  document.addEventListener('visibilitychange', onVisibilityRefresh)

  // "/" keyboard shortcut to focus search
  document.addEventListener('keydown', onSlashKey)
})

const onSlashKey = (e) => {
  if (e.key === '/' && !e.ctrlKey && !e.metaKey && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
    e.preventDefault()
    searchInput.value?.focus()
  }
}

onUnmounted(() => {
  clearInterval(announcementInterval)
  clearInterval(statsInterval)
  clearInterval(calendarInterval)
  clearInterval(overseerrStatusInterval)
  clearInterval(diskHealthInterval)
  clearInterval(speedtestInterval)
  clearInterval(sysStatsInterval)
  clearInterval(requestStatusInterval)
  document.removeEventListener('keydown', onSlashKey)
  document.removeEventListener('visibilitychange', onVisibilityRefresh)
})

// Refresh the badge count when the tab becomes visible again. Goes through
// the cheap version-check so we don't do a full fetch unless something actually
// changed while the tab was hidden.
const onVisibilityRefresh = () => {
  if (document.visibilityState === 'visible') checkRequestStatusVersion()
}

// Bookmarks for the sidebar grid. Tailwind JIT scans this file, so the full
// class strings here (`text-purple-400`, `hover:border-amber-500/40`, etc.)
// are picked up at build time.
const bookmarks = [
  {
    label: 'Request Status',
    action: 'requestStatus',
    iconColor: 'text-fuchsia-400',
    hoverBorder: 'hover:border-fuchsia-500/50',
    accent: true,  // styled prominently (border + glow) since it's the headline bookmark
    icon: '<path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/>'
  },
  {
    label: 'Collections',
    href: 'https://akplex.tv/collections',
    iconColor: 'text-amber-400',
    hoverBorder: 'hover:border-amber-500/40',
    icon: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>'
  },
  {
    label: 'Plex Tutorials',
    href: 'https://akplex.tv/tutorials',
    iconColor: 'text-emerald-400',
    hoverBorder: 'hover:border-emerald-500/40',
    icon: '<path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>'
  }
]
</script>

<template>
  <div class="min-h-screen font-sans relative overflow-hidden text-slate-200 selection:bg-fuchsia-500 selection:text-white">

    <div class="fixed inset-0 -z-10"
         style="background-image: linear-gradient(-225deg, #0F172A 0%, #1E1B4B 35%, #4C1D95 65%, #BE185D 100%);">
    </div>

    <div class="fixed inset-0 opacity-[0.03] pointer-events-none mix-blend-overlay"
         style="background-image: url('data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E');">
    </div>

    <div class="fixed top-4 left-4 right-4 z-50 flex justify-center pointer-events-none">
      <div v-if="welcomeMessage.show" class="flex items-center justify-between p-3 border rounded-xl bg-gradient-to-br from-green-900/90 to-emerald-900/90 border-green-500/30 backdrop-blur-md shadow-lg max-w-2xl w-full pointer-events-auto animate-slide-down">
        <div class="flex items-center gap-3">
          <span>👋</span>
          <p class="text-sm text-white">Welcome! Announcements will appear here in the case of downtime, maintenance, or other major events.</p>
        </div>
        <button @click="dismissWelcome" class="bg-white/10 hover:bg-white/20 text-white w-7 h-7 rounded-full transition flex-shrink-0 flex items-center justify-center">✕</button>
      </div>

      <div v-if="announcement.enabled && announcement.message && !announcement.dismissed && !welcomeMessage.show" :class="announcementClass" class="flex items-center justify-between p-3 border rounded-xl backdrop-blur-md shadow-lg max-w-2xl w-full pointer-events-auto animate-slide-down text-white">
        <div class="flex items-center gap-3">
          <span class="text-lg">{{ announcementIcon }}</span>
          <p class="text-base font-medium">{{ announcement.message }}</p>
        </div>
        <button v-if="announcement.dismissible" @click="dismissAnnouncement" class="bg-white/10 hover:bg-white/20 text-white w-7 h-7 rounded-full transition flex-shrink-0 flex items-center justify-center">✕</button>
      </div>
    </div>

    <div class="max-w-[1100px] mx-auto p-3 pt-2 sm:p-4 sm:pt-6 relative z-10 main-content">

      <!-- relative z-20 keeps tooltips above the app-cells stacking context below.
           Each app cell uses backdrop-blur which creates a new stacking context;
           without this, pill tooltips would be clipped behind the cells. -->
      <!-- Header: items-stretch lets each child fill the full header height,
           which is set by the tallest piece (the 2-row pill stack on sm+).
           Logo+search center themselves vertically inside that height so all
           three columns sit flush. -->
      <header class="relative z-20 flex items-stretch gap-2 sm:gap-3 mb-3 pb-3 border-b border-white/10">
        <!-- Logo + name -->
        <div class="flex items-center gap-2 flex-shrink-0">
          <img :src="faviconImg" alt="Plex Hub" class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl shadow-lg shadow-purple-500/20">
          <span class="text-xl sm:text-2xl font-bold bg-gradient-to-r from-pink-300 via-purple-300 to-indigo-300 bg-clip-text text-transparent tracking-tight">
            Plex Hub
          </span>
        </div>

        <!-- Search column: stretches between logo and pills, input centered vertically. -->
        <div class="flex-1 flex items-center min-w-0">
          <div class="relative w-full max-w-md">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input ref="searchInput" type="text" v-model="searchQuery" @input="onSearchInput" @keyup.enter="handleSearch" @keyup.escape="searchQuery = ''; searchResults = []" placeholder="Search library..." class="w-full h-10 sm:h-11 bg-white/[0.07] border border-white/25 rounded-xl px-4 pl-9 pr-8 text-sm text-white placeholder-white/40 focus:outline-none focus:border-purple-500/50 focus:bg-white/[0.1] focus:ring-1 focus:ring-purple-500/30 transition-all">
            <kbd v-if="!searchQuery" class="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:inline text-[9px] text-slate-500 bg-white/[0.06] border border-white/10 rounded px-1.5 py-0.5 font-mono">/</kbd>
            <button v-if="searchQuery" @mousedown.prevent="searchQuery = ''; searchResults = []" class="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white transition">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
            <Transition name="dropdown">
            <div v-if="searchResults.length > 0" class="absolute top-11 left-0 right-0 bg-[#0d1117] border border-purple-500/30 rounded-xl shadow-2xl shadow-purple-900/30 overflow-hidden z-50 max-h-80 overflow-y-auto">
              <div v-for="r in searchResults" :key="r.ratingKey" class="flex items-center gap-3 px-3 py-2 hover:bg-purple-600/20 transition-colors">
                <button @mousedown.prevent="pickResult(r)" class="flex items-center gap-3 min-w-0 flex-1 text-left">
                  <img v-if="r.thumb" :src="r.thumb" class="w-8 h-12 object-cover rounded flex-shrink-0" />
                  <div v-else class="w-8 h-12 bg-slate-700 rounded flex-shrink-0 flex items-center justify-center">
                    <svg class="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
                  </div>
                  <div class="min-w-0">
                    <div class="text-sm text-white truncate">{{ r.title }}</div>
                    <div class="text-xs text-slate-400">{{ r.year }} · {{ r.type === 'movie' ? 'Movie' : 'Series' }}</div>
                  </div>
                </button>
                <button @mousedown.prevent.stop="reportIssue(r)" class="flex-shrink-0 p-1.5 rounded-lg hover:bg-red-500/20 transition-colors group/report" title="Report issue">
                  <svg v-if="reportedKey === r.ratingKey" class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                  <svg v-else class="w-4 h-4 text-slate-500 group-hover/report:text-red-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z"/></svg>
                </button>
              </div>
            </div>
            </Transition>
            <div v-if="searchLoading && searchQuery.trim().length >= 2 && searchResults.length === 0" class="absolute top-11 left-0 right-0 bg-[#0d1117] border border-purple-500/30 rounded-xl shadow-2xl p-3 z-50">
              <div class="text-sm text-slate-400 text-center">Searching...</div>
            </div>
            <div v-else-if="!searchLoading && searchQuery.trim().length >= 2 && searchResults.length === 0 && searchDebounce === null" class="absolute top-11 left-0 right-0 bg-[#0d1117] border border-purple-500/30 rounded-xl shadow-2xl p-3 z-50">
              <div class="text-sm text-slate-400 text-center">No results</div>
            </div>
          </div>
        </div>

        <!-- Stat pills: 2-row vertical stack on sm+ (row 1 = system, row 2 = network).
             Mobile (<sm) collapses to just the Active streams pill.
             Each pill has its own tooltip (text-sm, z-[100]) that renders above
             the app-cells stacking context below the header. -->
        <div class="flex-shrink-0 flex flex-col gap-1.5 justify-center">
          <!-- Row 1: system stats (CPU / GPU / RAM). Hidden on mobile. -->
          <div class="hidden sm:flex gap-1.5 justify-end">
            <!-- CPU% -->
            <div v-if="HEADER_WIDGETS.cpu && sysStats.cpuPercent != null"
                 class="group/tip relative flex items-center gap-2 bg-slate-900/60 backdrop-blur-md border border-white/15 rounded-lg px-3 py-1.5 shadow-sm">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>
              <span class="text-sm font-bold text-slate-100 font-mono">{{ sysStats.cpuPercent }}%</span>
              <span class="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap bg-slate-900 text-slate-100 border border-white/20 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-[9999]">CPU Usage</span>
            </div>

            <!-- GPU (temp + utilization in one pill) -->
            <div v-if="HEADER_WIDGETS.gpu && sysStats.gpuTempC != null"
                 class="group/tip relative flex items-center gap-2 bg-slate-900/60 backdrop-blur-md border border-white/15 rounded-lg px-3 py-1.5 shadow-sm">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9l2 2 2-2m-2 2v4"/></svg>
              <span class="text-sm font-bold font-mono" :class="sysStats.gpuTempC >= 80 ? 'text-rose-400' : sysStats.gpuTempC >= 65 ? 'text-amber-400' : 'text-slate-100'">{{ sysStats.gpuTempC }}°</span>
              <span v-if="sysStats.gpuUtilPercent != null" class="text-slate-600 text-sm">·</span>
              <span v-if="sysStats.gpuUtilPercent != null" class="text-sm font-bold text-slate-100 font-mono">{{ sysStats.gpuUtilPercent }}%</span>
              <span class="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap bg-slate-900 text-slate-100 border border-white/20 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-[9999]">GPU Temp{{ sysStats.gpuUtilPercent != null ? ' · Utilization' : '' }}</span>
            </div>

            <!-- RAM % -->
            <div v-if="HEADER_WIDGETS.ram && sysStats.memPercent != null"
                 class="group/tip relative flex items-center gap-2 bg-slate-900/60 backdrop-blur-md border border-white/15 rounded-lg px-3 py-1.5 shadow-sm">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 6h14a1 1 0 011 1v10a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1zM9 9v6m6-6v6"/></svg>
              <span class="text-sm font-bold text-slate-100 font-mono">{{ sysStats.memPercent }}%</span>
              <span class="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap bg-slate-900 text-slate-100 border border-white/20 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-[9999]">RAM Usage</span>
            </div>
          </div>

          <!-- Row 2: streams + bandwidth. Active streams stays visible on mobile. -->
          <div class="flex gap-1.5 justify-end">
            <!-- Upload bandwidth -->
            <div v-if="HEADER_WIDGETS.bandwidth"
                 class="group/tip relative hidden sm:flex items-center gap-2 bg-slate-900/60 backdrop-blur-md border border-white/15 rounded-lg px-3 py-1.5 shadow-sm">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 11l5-5m0 0l5 5m-5-5v12"/></svg>
              <span class="text-sm font-bold text-slate-100 font-mono">{{ stats.bandwidthMbps }}</span>
              <span class="text-xs text-slate-500 font-medium">Mbps</span>
              <span class="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap bg-slate-900 text-slate-100 border border-white/20 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-[9999]">Upload Bandwidth</span>
            </div>

            <!-- Active streams (always visible, even on mobile) -->
            <div v-if="HEADER_WIDGETS.activeStreams"
                 class="group/tip relative flex items-center bg-slate-900/60 backdrop-blur-md border border-white/15 rounded-lg px-3 py-1.5 gap-2 shadow-sm">
              <div class="relative flex h-2.5 w-2.5"">
                <span v-if="stats.streams > 0" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5" :class="stats.streams > 0 ? 'bg-green-500' : 'bg-slate-600'"></span>
              </div>
              <span class="text-sm font-bold text-slate-100 font-mono">{{ stats.streams }}</span>
              <span class="text-xs text-slate-500 hidden sm:inline font-medium">Active</span>
              <span class="absolute top-full mt-2 right-0 sm:right-auto sm:left-1/2 sm:-translate-x-1/2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap bg-slate-900 text-slate-100 border border-white/20 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-[9999]">Active Streams</span>
            </div>
          </div>
        </div>
      </header>

      <!-- Top action area: app cells (left, 2 of 3 cols on lg+) sit next to the
           Bookmarks panel (right, 1 of 3 cols). On md and below they stack
           vertically — cells take full width with a 2x2 grid, bookmarks below. -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 lg:gap-4 mb-4 pb-4 border-b border-white/5">

        <!-- Cells: always rows of 2 now. lg+ gets 2 of 3 outer cols. -->
        <div class="lg:col-span-2 grid grid-cols-2 gap-2 sm:gap-3">
        <!-- Quick Request: opens modal w/ Seerr search + free-text fallback -->
        <button @click="quickOpen = true" class="group flex flex-col items-center gap-1.5 bg-slate-950/60 backdrop-blur-xl border border-fuchsia-500/30 rounded-2xl p-2.5 sm:p-3 hover:bg-slate-900/80 hover:-translate-y-0.5 active:scale-95 shadow-[0_0_20px_rgba(217,70,239,0.12)] hover:shadow-[0_0_30px_rgba(217,70,239,0.3)] hover:border-fuchsia-500/50 transition-all duration-200 cursor-pointer">
          <img :src="blockbusterImg" alt="" class="w-20 h-20 sm:w-24 sm:h-24 object-cover rounded-xl shadow-md group-hover:drop-shadow-[0_0_8px_rgba(217,70,239,0.5)] transition">
          <span class="text-sm font-bold text-white">Request Content</span>
        </button>

        <a href="https://app.plex.tv/desktop" class="group relative flex flex-col items-center gap-1.5 bg-slate-950/60 backdrop-blur-xl border border-white/10 rounded-2xl p-2.5 sm:p-3 hover:bg-slate-900/80 hover:-translate-y-0.5 active:scale-95 hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.6),0_0_30px_rgba(251,146,60,0.2)] hover:border-orange-500/40 transition-all duration-200">
          <!-- Pulse-dot health indicator -->
          <span class="absolute top-2 right-2 flex h-2.5 w-2.5" :title="statsError || stats.plexOnline !== true ? 'Plex offline' : 'Plex online'">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" :class="statsError || stats.plexOnline !== true ? 'bg-rose-400' : 'bg-emerald-400'"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 shadow-[0_0_6px_currentColor]" :class="statsError || stats.plexOnline !== true ? 'bg-rose-500 text-rose-500' : 'bg-emerald-500 text-emerald-500'"></span>
          </span>
          <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/plex.png" alt="Plex" class="w-20 h-20 sm:w-24 sm:h-24 drop-shadow-md">
          <span class="text-sm font-bold text-white">AK's Plex</span>
        </a>

        <a href="https://akplex.tv/recently-added" class="group flex flex-col items-center gap-1.5 bg-slate-950/60 backdrop-blur-xl border border-white/10 rounded-2xl p-2.5 sm:p-3 hover:bg-slate-900/80 hover:-translate-y-0.5 active:scale-95 hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.6),0_0_30px_rgba(52,211,153,0.2)] hover:border-emerald-500/40 transition-all duration-200">
          <!-- Clapperboard + "new" plus badge: unambiguous "new movie/show
               added" iconography. Clapperboard body is shifted up-left a bit
               to leave room for the badge in the bottom-right corner. -->
          <svg class="w-20 h-20 sm:w-24 sm:h-24 text-emerald-400 drop-shadow-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19.5 5 2.8 9.3l-.7-2.3c-.3-1.1.4-2.2 1.5-2.5L15.7 1.5c1.1-.3 2.2.4 2.5 1.5z"/>
            <path d="m5.4 4.1 2.8 3.7"/>
            <path d="m11.2 2.5 2.8 3.7"/>
            <path d="M2.8 9.3h16.7v5a2 2 0 0 1-2 2H4.8a2 2 0 0 1-2-2z"/>
            <circle cx="19" cy="19" r="4"/>
            <path d="M19 17v4M17 19h4"/>
          </svg>
          <span class="text-sm font-bold text-white">New Uploads</span>
        </a>

        <!-- Quick Report: opens modal w/ media-issue search + general feedback -->
        <button @click="reportOpen = true" class="group flex flex-col items-center gap-1.5 bg-slate-950/60 backdrop-blur-xl border border-rose-500/30 rounded-2xl p-2.5 sm:p-3 hover:bg-slate-900/80 hover:-translate-y-0.5 active:scale-95 shadow-[0_0_20px_rgba(244,63,94,0.10)] hover:shadow-[0_0_30px_rgba(244,63,94,0.25)] hover:border-rose-500/50 transition-all duration-200 cursor-pointer">
          <img :src="technicalDiffImg" alt="" class="w-20 h-20 sm:w-24 sm:h-24 object-cover rounded-xl shadow-md group-hover:drop-shadow-[0_0_8px_rgba(244,63,94,0.5)] transition">
          <span class="text-sm font-bold text-white">Report an Issue</span>
        </button>
        </div>
        <!-- /cells -->

        <!-- Bookmarks panel: stacked column on lg+ (alongside cells), 2-col grid
             on smaller screens (below cells). Uses the shared `bookmarks` array;
             items with `action` render as <button> (modal triggers), the rest as <a>. -->
        <section class="lg:col-span-1">
          <h2 class="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2 px-1 mb-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block"></span> Bookmarks
          </h2>
          <div class="grid grid-cols-2 lg:grid-cols-1 gap-1.5">
            <component
              v-for="b in bookmarks"
              :key="b.label"
              :is="b.action ? 'button' : 'a'"
              :href="b.action ? undefined : b.href"
              :type="b.action ? 'button' : undefined"
              @click="b.action === 'requestStatus' ? openRequestStatus() : null"
              :class="[
                'flex items-center gap-3 backdrop-blur-sm border rounded-xl px-3 py-2 hover:bg-slate-900/80 transition-all duration-300 text-left w-full',
                b.accent
                  ? 'bg-slate-950/70 border-fuchsia-500/40 shadow-[0_0_18px_rgba(217,70,239,0.15)] hover:shadow-[0_0_24px_rgba(217,70,239,0.3)]'
                  : 'bg-slate-950/50 border-white/10',
                b.hoverBorder
              ]"
            >
              <svg
                :class="['w-4 h-4 flex-shrink-0', b.iconColor]"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                v-html="b.icon"
              ></svg>
              <span :class="['text-sm font-medium truncate', b.accent ? 'text-white font-bold' : 'text-slate-300']">{{ b.label }}</span>
              <span v-if="b.action === 'requestStatus' && requestStatusItems.length > 0 && requestStatusCounts.pending > 0"
                    class="ml-auto px-1.5 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30 flex-shrink-0">
                {{ requestStatusCounts.pending }}
              </span>
              <svg v-else class="w-4 h-4 text-white/20 ml-auto flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
            </component>
          </div>
        </section>

      </div>

      <!-- Status bars (commented out — health moved into Plex cell) -->
      <!--
      <div class="flex flex-col gap-1.5 mb-3">
        <div class="flex items-center gap-3 bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full flex-shrink-0 shadow-[0_0_6px_currentColor]" :class="statsError ? 'bg-rose-500 text-rose-500' : stats.plexOnline === true ? 'bg-emerald-500 text-emerald-500' : 'bg-rose-500 text-rose-500'"></div>
          <span class="text-sm font-medium text-slate-300">Plex</span>
          <span class="text-xs px-2 py-0.5 rounded font-bold ml-auto tracking-wider uppercase" :class="statsError || stats.plexOnline !== true ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'">
            {{ statsError ? 'DOWN' : stats.plexOnline === true ? 'OK' : 'DOWN' }}
          </span>
        </div>
        <div class="flex items-center gap-3 bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-2">
          <div class="w-2 h-2 rounded-full flex-shrink-0 shadow-[0_0_6px_currentColor]" :class="overseerrStatus.status === 'online' ? 'bg-emerald-500 text-emerald-500' : overseerrStatus.status === 'degraded' ? 'bg-amber-500 text-amber-500' : 'bg-rose-500 text-rose-500'"></div>
          <span class="text-sm font-medium text-slate-300">Supporting Sites</span>
          <span class="text-xs px-2 py-0.5 rounded font-bold ml-auto tracking-wider uppercase" :class="overseerrStatus.status === 'online' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : overseerrStatus.status === 'degraded' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'">
            {{ overseerrStatus.status === 'online' ? 'OK' : overseerrStatus.status === 'degraded' ? 'WARN' : 'DOWN' }}
          </span>
        </div>
      </div>
      -->

      <!-- Bookmarklets (commented out — merged into action cells + bookmarks section) -->
      <!--
      <div class="grid grid-cols-2 gap-2 mb-5">
        <a href="https://akplex.tv/recently-added" class="flex items-center gap-2 bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl px-3 py-2 hover:border-purple-500/40 hover:bg-slate-900/80 transition-all duration-300 group">
          <svg class="w-5 h-5 text-purple-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/></svg>
          <span class="text-xs sm:text-sm font-medium text-slate-300">New Uploads</span>
        </a>
        <button @click="msgOpen = true" class="flex items-center gap-2 bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl px-3 py-2 hover:border-purple-500/40 hover:bg-slate-900/80 transition-all duration-300 cursor-pointer group text-left">
          <svg class="w-5 h-5 text-purple-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
          <span class="text-xs sm:text-sm font-medium text-slate-300">Anonymous Message</span>
        </button>
      </div>
      -->

      <!-- Request Content modal: Seerr search + free-text fallback. -->
      <Modal v-model="quickOpen"
             title="Request Content"
             :max-width="640"
             border-class="border-fuchsia-500/30"
             @close="closeQuickModal">
        <p class="text-sm text-slate-300">Search for a movie or show, then click a result to request it.</p>

        <div class="relative">
          <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input v-model="quickQuery" @input="onQuickSearchInput" type="text" placeholder="Inception, Planet Earth..." class="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 pl-11 py-3 text-base text-white placeholder-slate-500 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/30">
        </div>

        <div class="min-h-[120px]">
          <div v-if="quickLoading" class="text-sm text-slate-400 text-center py-6">Searching...</div>
          <div v-else-if="quickQuery.trim().length >= 2 && quickResults.length === 0" class="text-sm text-slate-500 text-center py-6">No results.</div>
          <div v-else-if="quickResults.length > 0" class="space-y-2">
            <button v-for="r in quickResults" :key="`${r.mediaType}-${r.tmdbId}`" @click="pickQuickResult(r)" :disabled="quickSending" class="w-full flex items-center gap-4 bg-slate-800/60 hover:bg-fuchsia-600/20 border border-white/5 hover:border-fuchsia-500/40 rounded-xl p-3 text-left transition disabled:opacity-50 disabled:cursor-not-allowed">
              <img v-if="r.posterUrl" :src="r.posterUrl" class="w-12 h-16 object-cover rounded flex-shrink-0" />
              <div v-else class="w-12 h-16 bg-slate-700 rounded flex-shrink-0 flex items-center justify-center">
                <svg class="w-6 h-6 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4"/></svg>
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-base text-white truncate font-medium">{{ r.title }}</div>
                <div class="text-sm text-slate-400">{{ r.year || '—' }} · {{ r.mediaType === 'movie' ? 'Movie' : 'Series' }}</div>
              </div>
              <svg class="w-5 h-5 text-fuchsia-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
            </button>
          </div>
          <div v-else class="text-sm text-slate-500 text-center py-6">Start typing a title above to see results.</div>
        </div>

        <div class="bg-slate-800/40 border border-white/10 rounded-xl p-4 space-y-3">
          <label class="block text-sm font-bold text-slate-200">Can't find it? Send a text request</label>
          <input v-model="quickFallbackText" type="text" placeholder="e.g. that documentary about octopuses" @keyup.enter="sendQuickFallback" class="w-full bg-slate-900/80 border border-white/10 rounded-lg px-4 py-3 text-base text-white placeholder-slate-500 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/30">
          <button @click="sendQuickFallback" :disabled="quickSending || !quickFallbackText.trim()" class="w-full px-4 py-3 text-sm font-bold text-white bg-fuchsia-600 hover:bg-fuchsia-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition">
            {{ quickSending ? 'Sending...' : 'Send text request' }}
          </button>
        </div>

        <div v-if="quickSent" class="text-sm text-emerald-400 text-center font-medium">Sent! Thank you.</div>
        <div v-else-if="quickError" class="text-sm text-rose-400 text-center font-medium">{{ quickError }}</div>

        <template #footer>
          <a href="/request" target="_blank" class="flex items-center justify-center gap-1.5 text-sm text-fuchsia-300 hover:text-fuchsia-200 transition font-medium">
            Open the full request page
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          </a>
        </template>
      </Modal>

      <!-- Request Status modal: tabbed view of every user-submitted request.
           Default tab = Uploaded (the happy path), with tabs for Pending
           and Searching (admin-flagged "hard to find"). Reuses the same
           /api/recently-fulfilled data the Requests tab on /recently-added/
           consumes. Lazy-fetched on open + prefetched on mount. -->
      <Modal v-model="requestStatusOpen"
             v-model:active-tab="requestStatusActiveTab"
             title="Request Status"
             :max-width="640"
             border-class="border-fuchsia-500/30"
             :tabs="requestStatusTabs">
        <!-- Shared empty / loading / error states (rendered inside each tab slot below). -->
        <template v-for="tabId in ['uploaded', 'pending', 'searching']" :key="tabId" #[`tab-${tabId}`]>
          <div v-if="requestStatusLoading && requestStatusItems.length === 0" class="text-sm text-slate-400 text-center py-6">Loading…</div>
          <div v-else-if="requestStatusError" class="text-sm text-rose-400 text-center py-6">{{ requestStatusError }}</div>
          <div v-else-if="requestStatusByState[tabId].length === 0" class="text-sm text-slate-500 text-center py-10">
            <template v-if="tabId === 'uploaded'">No uploaded requests yet.</template>
            <template v-else-if="tabId === 'pending'">Nothing pending — you're all caught up.</template>
            <template v-else>Nothing marked as searching.</template>
          </div>
          <div v-else class="space-y-2">
            <component
              v-for="req in requestStatusByState[tabId]"
              :key="`${req.title}-${req.type}-${req.addedAt}`"
              :is="req.plexUrl ? 'a' : 'div'"
              :href="req.plexUrl"
              :target="req.plexUrl ? '_blank' : undefined"
              class="flex items-center gap-3 bg-slate-800/40 border border-white/5 rounded-lg p-4 transition-colors"
              :class="req.plexUrl ? 'hover:bg-slate-800/80 hover:border-fuchsia-500/30 cursor-pointer' : ''"
            >
              <img v-if="req.posterUrl" :src="req.posterUrl" class="w-14 h-18 object-cover rounded flex-shrink-0" :alt="req.title">
              <div v-else class="w-14 h-18 bg-slate-700/60 rounded flex-shrink-0 flex items-center justify-center">
                <svg class="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-bold text-white truncate">{{ req.title }}</div>
                <div class="text-xs text-slate-400">{{ req.year || '—' }}<span v-if="req.type === 'movie' || req.type === 'tv'"> · {{ req.type === 'movie' ? 'Movie' : 'Series' }}</span></div>
              </div>
            </component>
          </div>
        </template>

        <template #footer>
          <a href="https://akplex.tv/recently-added"
             class="flex items-center justify-center gap-2 text-sm font-bold text-fuchsia-300 hover:text-fuchsia-200 transition">
            See all on the Requests page
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          </a>
        </template>
      </Modal>

      <!-- Report an Issue modal: media-issue search + general feedback in one place. -->
      <Modal v-model="reportOpen"
             title="Report an Issue"
             :max-width="640"
             border-class="border-rose-500/30"
             @close="closeReportModal">
        <!-- Section 1: media-specific issue -->
        <div class="space-y-3">
          <label class="block text-sm font-bold text-slate-200">Report an issue with specific media</label>

          <div v-if="!reportSelected" class="space-y-2">
            <div class="relative">
              <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
              <input v-model="reportSearch" @input="onReportSearchInput" type="text" placeholder="Search the library..." class="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 pl-11 py-3 text-base text-white placeholder-slate-500 focus:outline-none focus:border-rose-500/50 focus:ring-1 focus:ring-rose-500/30">
            </div>
            <div v-if="reportLoading" class="text-sm text-slate-400 text-center py-3">Searching...</div>
            <div v-else-if="reportSearch.trim().length >= 2 && reportResults.length === 0" class="text-sm text-slate-500 text-center py-3">No matching content in the library.</div>
            <div v-else-if="reportResults.length > 0" class="space-y-2 max-h-56 overflow-y-auto thin-scrollbar">
              <button v-for="r in reportResults" :key="`${r.mediaType}-${r.tmdbId}`" @click="pickReportResult(r)" class="w-full flex items-center gap-3 bg-slate-800/60 hover:bg-rose-600/20 border border-white/5 hover:border-rose-500/40 rounded-xl p-2.5 text-left transition">
                <img v-if="r.posterUrl" :src="r.posterUrl" class="w-10 h-14 object-cover rounded flex-shrink-0" />
                <div v-else class="w-10 h-14 bg-slate-700 rounded flex-shrink-0"></div>
                <div class="min-w-0 flex-1">
                  <div class="text-sm text-white truncate font-medium">{{ r.title }}</div>
                  <div class="text-xs text-slate-400">{{ r.year || '—' }} · {{ r.mediaType === 'movie' ? 'Movie' : 'Series' }}</div>
                </div>
              </button>
            </div>
          </div>

          <div v-else class="bg-slate-800/40 border border-rose-500/30 rounded-xl p-4 space-y-3">
            <div class="flex items-start gap-3">
              <img v-if="reportSelected.posterUrl" :src="reportSelected.posterUrl" class="w-12 h-16 object-cover rounded flex-shrink-0" />
              <div v-else class="w-12 h-16 bg-slate-700 rounded flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <div class="text-base text-white font-medium truncate">{{ reportSelected.title }}</div>
                <div class="text-xs text-slate-400">{{ reportSelected.year || '—' }} · {{ reportSelected.mediaType === 'movie' ? 'Movie' : 'Series' }}</div>
              </div>
              <button @click="clearReportSelection" class="text-xs text-slate-400 hover:text-white transition">change</button>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 uppercase tracking-wide mb-2">What's the issue?</label>
              <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <button v-for="t in REPORT_TYPES" :key="t.id" @click="reportIssueType = t.id"
                        :class="reportIssueType === t.id ? 'bg-rose-600 border-rose-400 text-white' : 'bg-slate-900/60 border-white/10 text-slate-300 hover:border-rose-500/40 hover:text-white'"
                        class="border rounded-lg px-3 py-2 text-xs font-medium transition">
                  {{ t.label }}
                </button>
              </div>
            </div>

            <textarea v-model="reportDetails" rows="2" placeholder="Optional details..." class="w-full bg-slate-900/80 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-rose-500/50 focus:ring-1 focus:ring-rose-500/30 resize-none"></textarea>

            <button @click="submitMediaReport" :disabled="!reportIssueType || reportSending" class="w-full px-4 py-2.5 text-sm font-bold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition">
              {{ reportSending ? 'Sending...' : 'Submit Report' }}
            </button>
          </div>
        </div>

        <!-- Divider -->
        <div class="relative py-1">
          <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-white/10"></div></div>
          <div class="relative flex justify-center"><span class="px-3 bg-slate-900/95 text-xs text-slate-500 uppercase tracking-widest">or</span></div>
        </div>

        <!-- Section 2: general feedback (anonymous message) -->
        <div class="space-y-3">
          <label class="block text-sm font-bold text-slate-200">Send a general message or feedback</label>
          <textarea v-model="reportFeedback" rows="3" placeholder="Anything else you'd like to share..." class="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 resize-none"></textarea>
          <div class="flex items-center justify-between">
            <span class="text-[10px] text-slate-500">Anonymous — no personal info collected</span>
            <button @click="submitFeedback" :disabled="!reportFeedback.trim() || reportSending" class="px-5 py-2 text-sm font-bold text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition">
              {{ reportSending ? 'Sending...' : 'Send Message' }}
            </button>
          </div>
        </div>

        <div v-if="reportSentKind" class="text-sm text-emerald-400 text-center font-medium">
          {{ reportSentKind === 'media' ? 'Report submitted. Thanks!' : 'Message sent. Thanks!' }}
        </div>
        <div v-else-if="reportError" class="text-sm text-rose-400 text-center font-medium">{{ reportError }}</div>

        <template #footer>
          <a href="/issues" target="_blank" class="flex items-center justify-center gap-1.5 text-sm text-rose-300 hover:text-rose-200 transition font-medium">
            Open the full issues page
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          </a>
        </template>
      </Modal>

      <Teleport to="body">
        <transition name="fade">
          <div v-if="activeVideo" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="activeVideo = null">
            <div class="absolute inset-0 bg-black/80 backdrop-blur-sm"></div>
            <div class="relative w-full max-w-3xl bg-slate-900/95 backdrop-blur-xl border border-white/15 rounded-2xl overflow-hidden shadow-2xl">
              <div class="flex items-center justify-between px-4 py-3 border-b border-white/10">
                <h3 class="text-sm font-bold text-white">{{ activeVideo.title }}</h3>
                <button @click="activeVideo = null" class="text-slate-400 hover:text-white transition">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
              </div>
              <video :src="'/tutorials/videos/' + activeVideo.filename" controls autoplay preload="auto" class="w-full aspect-video object-contain bg-black"></video>
              <p v-if="activeVideo.description" class="px-4 py-3 text-xs text-slate-400">{{ activeVideo.description }}</p>
            </div>
          </div>
        </transition>
      </Teleport>

      <section v-if="episodes.length > 0 || calendarError" class="mb-4 pb-4 border-b border-white/5">
        <div class="flex items-center justify-between mb-2 px-1">
          <h2 class="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block"></span> TV Calendar
            <HelpTip tip="Green dot = episode uploaded. Amber dot = aired but waiting for upload. Gray dot = not yet aired." size="sm" />
          </h2>
          <button v-if="calendarExpanded" @click="calendarExpanded = false" class="flex items-center gap-1.5 text-xs font-bold transition-all px-4 py-2 rounded-xl border-2 shadow-lg text-white bg-purple-600 border-purple-400 hover:bg-purple-700 shadow-purple-500/30">
            Collapse
            <svg class="w-4 h-4 rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/></svg>
          </button>
        </div>

        <div v-if="calendarError && episodes.length === 0" class="text-rose-400 text-xs p-3 bg-rose-900/20 border border-rose-500/20 rounded-xl">
          Unable to load TV calendar
        </div>

        <div v-else class="relative">
          <button v-if="calendarCanScrollLeft" @click="scrollCalendarLeft" class="absolute left-0 top-0 bottom-0 w-12 flex items-center justify-center bg-gradient-to-r from-black/70 via-black/40 to-transparent rounded-l-xl z-10">
            <svg class="w-6 h-6 text-white drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7"/></svg>
          </button>
          <div ref="calendarScroll" @scroll="checkCalendarScroll" class="flex gap-2 overflow-x-auto pb-2 -mx-6 px-4 sm:mx-0 sm:px-0 scrollbar-hide">
          <!-- Responsive widths: 2 / 3 / 4 / 5 cards visible per breakpoint.
               At lg+ exactly 5 of the 7 days fit, so days 6-7 sit behind the
               right-edge scroll chevron (calendarCanScrollRight). -->
          <div v-for="day in calendarDays" :key="day.date"
               :class="[
                 'flex-shrink-0 w-[calc(50%-4px)] sm:w-[calc(33.333%-6px)] md:w-[calc(25%-6px)] lg:w-[calc(20%-7px)] bg-slate-950/60 backdrop-blur-xl rounded-xl transition-colors duration-300 group border',
                 day.isToday
                   ? 'border-fuchsia-500/50 ring-1 ring-fuchsia-500/20 shadow-[0_0_18px_rgba(217,70,239,0.18)]'
                   : 'border-white/15 hover:border-white/25'
               ]">

            <div :class="[
                   'px-3 py-1.5 border-b flex items-center justify-between',
                   day.isToday ? 'border-fuchsia-500/30 bg-fuchsia-500/10' : 'border-white/5 bg-white/[0.03]'
                 ]">
              <span :class="['text-xs sm:text-sm font-bold', day.isToday ? 'text-fuchsia-200' : 'text-slate-200']">{{ day.dayName }}</span>
              <span :class="['text-xs font-mono', day.isToday ? 'text-fuchsia-300' : 'text-slate-400']">{{ day.dateLabel }}</span>
            </div>

            <div class="p-2 space-y-1 transition-all duration-300 custom-scrollbar" :class="{ 'max-h-[250px] overflow-y-auto': calendarExpanded }">
              <template v-if="day.episodes.length > 0">
                <div v-for="ep in (calendarExpanded ? day.episodes : day.episodes.slice(0, 2))" :key="ep.id"
                     class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-default">
                  <div class="relative flex-shrink-0 group/status" :title="ep.status === 'available' ? 'Uploaded' : ep.status === 'missing' ? 'Not yet uploaded' : 'Not yet aired'">
                    <span class="block w-2 h-2 rounded-full" :class="ep.status === 'available' ? 'bg-emerald-400' : ep.status === 'missing' ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'"></span>
                    <span class="absolute -top-8 left-1/2 -translate-x-1/2 px-2.5 py-1 rounded-md text-[9px] font-medium whitespace-nowrap bg-slate-800 text-slate-200 border border-white/10 shadow-lg opacity-0 group-hover/status:opacity-100 transition-opacity pointer-events-none z-50">{{ ep.status === 'available' ? 'Uploaded' : ep.status === 'missing' ? 'Not yet uploaded' : 'Not yet aired' }}</span>
                  </div>
                  <div class="min-w-0 flex-1">
                    <span class="text-xs sm:text-sm font-bold text-white truncate block leading-tight">{{ ep.seriesTitle }}</span>
                    <span class="text-xs text-slate-400 inline-flex items-center gap-1.5">
                      S{{ ep.seasonNumber }}E{{ ep.episodeNumber }}
                      <span class="px-1.5 py-[1px] rounded-md bg-fuchsia-500/15 border border-fuchsia-500/30 text-fuchsia-300 text-[10px] font-bold leading-none">{{ ep.airTime }}</span>
                    </span>
                  </div>
                </div>
              </template>
              <div v-else class="text-center py-4 text-slate-500 text-xs italic">No episodes</div>
            </div>

            <div v-if="!calendarExpanded && day.episodes.length > 2" @click="calendarExpanded = true"
                 class="px-3 py-2 text-center text-xs font-bold text-purple-300 border-t border-purple-500/30 bg-purple-500/15 cursor-pointer hover:bg-purple-500/30 hover:text-white transition-colors rounded-b-xl">
              +{{ day.episodes.length - 2 }} more
            </div>
          </div>
          </div>
          <button v-if="calendarCanScrollRight" @click="scrollCalendarRight" class="absolute right-0 top-0 bottom-0 w-12 flex items-center justify-center bg-gradient-to-l from-black/70 via-black/40 to-transparent rounded-r-xl z-10">
            <svg class="w-6 h-6 text-white drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7"/></svg>
          </button>
        </div>
      </section>

      <section class="mt-2 mb-4 pb-4 border-b border-white/5">
        <div class="flex items-center justify-between mb-2 px-1">
          <h2 class="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block"></span> Trending Movies
          </h2>
          <a href="https://akplex.tv/recently-added" class="text-sm font-bold text-slate-300 uppercase tracking-widest hover:text-white transition-colors flex items-center gap-1.5">
            Newest Uploads
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
          </a>
        </div>
        <MovieGrid :limit="7" layout="horizontal" :refresh-interval="600000" :show-header="false" />
      </section>

      <!-- Plex Tips & Tricks (full width now; Bookmarks moved up next to the cells). -->
      <section class="mb-4">
        <div class="flex items-center justify-between mb-2 px-1">
          <h2 class="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block"></span> Plex Tips &amp; Tricks
          </h2>
          <a v-if="tutorials.length > 0" href="https://akplex.tv/tutorials" class="text-sm font-bold text-slate-300 uppercase tracking-widest hover:text-white transition-colors flex items-center gap-1.5">
            See All
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
          </a>
        </div>
        <div v-if="tutorials.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
          <button v-for="vid in tutorials" :key="vid.id" @click="activeVideo = vid" class="group bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl overflow-hidden hover:border-purple-500/40 hover:bg-slate-900/80 transition-all duration-300 text-left">
            <div class="relative aspect-video bg-black">
              <img v-if="vid.thumbnail" :src="'/tutorials/videos/' + vid.thumbnail" :alt="vid.title" class="w-full h-full object-cover" loading="lazy">
              <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
                <svg class="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
              </div>
              <div class="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-black/10 transition-colors">
                <svg class="w-10 h-10 text-white/80 drop-shadow-lg" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              </div>
            </div>
            <div class="px-2 py-1.5">
              <span class="text-[11px] font-bold text-white leading-tight line-clamp-2">{{ vid.title }}</span>
            </div>
          </button>
        </div>
        <div v-else class="bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-center">
          <span class="text-sm text-slate-400 italic">Coming soon</span>
        </div>
      </section>

      <footer class="text-center py-4 text-slate-500 text-xs border-t border-white/5">
        <p>WebHead Media &copy; 2025</p>
        <div class="mt-1 flex items-center justify-center gap-3">
          <a href="https://akplex.tv/issues" class="text-slate-400 hover:text-purple-400 transition inline-block border-b border-transparent hover:border-purple-400/50 pb-0.5">Report an Issue</a>
          <span class="text-slate-600">&middot;</span>
          <a href="https://akplex.tv/collections" class="text-slate-400 hover:text-purple-400 transition inline-block border-b border-transparent hover:border-purple-400/50 pb-0.5">Collections</a>
        </div>
      </footer>
    </div>
  </div>
  <Toast :show="toastShow" :message="toastMessage" :type="toastType" @close="toastShow = false" />
</template>

<style>
/* Unscoped — needed for Teleport'd modal transitions */
.fade-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: scale(0.95);
}
.fade-leave-to {
  opacity: 0;
  transform: scale(0.97);
}
.dropdown-enter-active { transition: opacity 0.15s ease-out; }
.dropdown-leave-active { transition: opacity 0.1s ease-in; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; }
</style>