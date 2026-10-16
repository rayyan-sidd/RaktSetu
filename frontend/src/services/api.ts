export interface StockReport {
  id: number
  blood_bank_id: number
  blood_group: string
  blood_component?: string
  units_reported: number
  source_name: string
  data_timestamp: string
  source_reported_timestamp?: string | null
  retrieval_timestamp?: string | null
  freshness_indicator?: string | null
  verification_status: string
}

export interface BloodBank {
  id: number
  name: string
  city: string
  locality: string
  source_type?: string
  source_name?: string
  source_facility_id?: string | null
  raw_address?: string | null
  category?: string | null
  facility_type?: string | null
  stock_reports: StockReport[]
}

export interface BloodBankListResponse {
  items: BloodBank[]
  count: number
  data_notice: string
  data_timestamp?: string | null
}


/**
 * Resolve the base API URL from Vite environment variables.
 * Defaults to an empty string in local development to route through the Vite dev proxy (/api).
 */
export function getApiBaseUrl(): string {
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env.VITE_API_BASE_URL : ''
  return (envUrl || '').replace(/\/$/, '')
}

/**
 * Resolve the Telegram Bot URL from Vite environment variables.
 * Returns null if unset, empty, or configured with placeholder text.
 */
export function getTelegramBotUrl(): string | null {
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env.VITE_TELEGRAM_BOT_URL : ''
  if (!envUrl || typeof envUrl !== 'string') return null
  const trimmed = envUrl.trim()
  if (!trimmed || trimmed.includes('your_bot') || trimmed.includes('placeholder')) return null
  return trimmed
}

/**
 * Construct the endpoint URL with optional city and blood group query parameters.
 * Defaults to the relative proxy path (/api/blood-banks) in local development,
 * while supporting an explicitly configured baseUrl for separate deployments.
 */
export function buildDiscoveryUrl(
  city?: string | null,
  bloodGroup?: string | null,
  baseUrl: string = getApiBaseUrl()
): string {
  const cleanBase = baseUrl ? baseUrl.replace(/\/$/, '') : ''
  const basePath = cleanBase ? `${cleanBase}/api/blood-banks` : '/api/blood-banks'

  const params = new URLSearchParams()
  if (city && city !== 'All') {
    params.set('city', city)
  }
  if (bloodGroup && bloodGroup !== 'All') {
    params.set('blood_group', bloodGroup)
  }

  const queryString = params.toString()
  return queryString ? `${basePath}?${queryString}` : basePath
}

/**
 * Fetch blood banks and stock reports from the FastAPI backend.
 */
export async function fetchBloodBanks(
  city?: string | null,
  bloodGroup?: string | null,
  signal?: AbortSignal
): Promise<BloodBankListResponse> {
  const targetUrl = buildDiscoveryUrl(city, bloodGroup)

  const response = await fetch(targetUrl, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (!response.ok) {
    let errorDetail = `Request failed with HTTP status ${response.status}`
    try {
      const errorJson = await response.json()
      if (errorJson && errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail)
      }
    } catch {
      // Fallback to HTTP status text
      if (response.statusText) {
        errorDetail = `HTTP ${response.status}: ${response.statusText}`
      }
    }
    throw new Error(errorDetail)
  }

  const data: BloodBankListResponse = await response.json()
  return data
}

export interface FormattedTimestamp {
  localDisplay: string
  utcDisplay: string
  isoString: string
}

/**
 * Format an ISO 8601 UTC timestamp into a user-friendly localized string
 * while preserving and exposing the exact UTC provenance string.
 */
export function formatTimestamp(isoUtcTimestamp: string): FormattedTimestamp {
  try {
    const date = new Date(isoUtcTimestamp)
    if (isNaN(date.getTime())) {
      return {
        localDisplay: isoUtcTimestamp,
        utcDisplay: isoUtcTimestamp,
        isoString: isoUtcTimestamp,
      }
    }

    const localDisplay = new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(date)

    const utcDisplay = date.toISOString().replace('.000Z', 'Z')

    return {
      localDisplay,
      utcDisplay,
      isoString: isoUtcTimestamp,
    }
  } catch {
    return {
      localDisplay: isoUtcTimestamp,
      utcDisplay: isoUtcTimestamp,
      isoString: isoUtcTimestamp,
    }
  }
}

export interface ReportFreshnessInfo {
  type: 'source_timestamp' | 'live_badge' | 'demo_snapshot' | 'retrieval_only'
  primaryLabel: string
  primaryDisplay: string
  utcDisplay?: string
  secondaryNote?: string
  isLiveBadge: boolean
  isDemo: boolean
  isStale?: boolean
}

/**
 * Determine freshness and timestamp presentation based on provenance.
 * Strictly distinguishes source-reported time from RaktSetu retrieval time,
 * handles live stock badge indicators without claiming exact times or live guarantees,
 * identifies stale records (>24h), and maintains demo snapshot distinction.
 */
export function getReportFreshnessInfo(report?: StockReport | null): ReportFreshnessInfo {
  if (!report) {
    return {
      type: 'retrieval_only',
      primaryLabel: 'Timestamp',
      primaryDisplay: 'No data',
      isLiveBadge: false,
      isDemo: false,
    }
  }

  // 1. Synthetic demo data
  if (report.verification_status === 'demo') {
    const formatted = formatTimestamp(report.data_timestamp)
    return {
      type: 'demo_snapshot',
      primaryLabel: 'Snapshot Time',
      primaryDisplay: formatted.localDisplay,
      utcDisplay: formatted.utcDisplay,
      secondaryNote: 'Simulated demonstration timestamp',
      isLiveBadge: false,
      isDemo: true,
    }
  }

  // 2. Live stock badge indicator (source indicates live stock without exact timestamp)
  if (
    report.freshness_indicator === 'live_stock_badge' ||
    (!report.source_reported_timestamp && report.freshness_indicator)
  ) {
    const retrievalFormatted = report.retrieval_timestamp
      ? formatTimestamp(report.retrieval_timestamp)
      : null
    return {
      type: 'live_badge',
      primaryLabel: 'Portal Indicator',
      primaryDisplay: 'Live Stock Badge',
      secondaryNote: retrievalFormatted
        ? `Retrieved by RaktSetu: ${retrievalFormatted.localDisplay} (UTC: ${retrievalFormatted.utcDisplay}). Portal shows live indicator without exact hospital timestamp; not a physical stock guarantee.`
        : 'Portal shows live indicator without exact hospital timestamp; not a physical stock guarantee.',
      isLiveBadge: true,
      isDemo: false,
    }
  }

  // 3. Source-reported hospital timestamp is present
  if (report.source_reported_timestamp) {
    const srcFormatted = formatTimestamp(report.source_reported_timestamp)
    const retrievalFormatted = report.retrieval_timestamp
      ? formatTimestamp(report.retrieval_timestamp)
      : null

    // Check if timestamp is older than 24 hours relative to retrieval (or current time)
    const srcTime = new Date(report.source_reported_timestamp).getTime()
    const baselineTime = report.retrieval_timestamp
      ? new Date(report.retrieval_timestamp).getTime()
      : Date.now()
    const isStale = !isNaN(srcTime) && (baselineTime - srcTime) > 24 * 60 * 60 * 1000

    let note = retrievalFormatted ? `Retrieved by RaktSetu: ${retrievalFormatted.localDisplay}` : undefined
    if (isStale) {
      note = `⚠️ Stale report (>24h old) • May not reflect current physical stock. ${note || ''}`.trim()
    }

    return {
      type: 'source_timestamp',
      primaryLabel: 'Hospital Reported',
      primaryDisplay: srcFormatted.localDisplay,
      utcDisplay: srcFormatted.utcDisplay,
      secondaryNote: note,
      isLiveBadge: false,
      isDemo: false,
      isStale,
    }
  }

  // 4. External report with only retrieval or legacy timestamp
  const fallbackFormatted = formatTimestamp(report.retrieval_timestamp || report.data_timestamp)
  return {
    type: 'retrieval_only',
    primaryLabel: 'Retrieval Time',
    primaryDisplay: fallbackFormatted.localDisplay,
    utcDisplay: fallbackFormatted.utcDisplay,
    secondaryNote: 'Source portal did not report an explicit hospital update timestamp.',
    isLiveBadge: false,
    isDemo: false,
  }
}

/**
 * Filter and sort blood banks for discovery presentation.
 * By default (includeDemo = false), demo facilities are excluded so that only external
 * e-RaktKosh records are shown.
 * When includeDemo is enabled (true), external records are placed first, followed by demo records.
 * The relative ordering of facilities within each partition is strictly preserved.
 */
export function filterAndSortBloodBanks(
  banks: BloodBank[],
  includeDemo: boolean = false
): BloodBank[] {
  if (!includeDemo) {
    return banks.filter(bank => bank.source_type !== 'demo')
  }
  const external = banks.filter(bank => bank.source_type !== 'demo')
  const demo = banks.filter(bank => bank.source_type === 'demo')
  return [...external, ...demo]
}
