export interface StockReport {
  id: number
  blood_bank_id: number
  blood_group: string
  units_reported: number
  source_name: string
  data_timestamp: string
  verification_status: string
}

export interface BloodBank {
  id: number
  name: string
  city: string
  locality: string
  stock_reports: StockReport[]
}

export interface BloodBankListResponse {
  items: BloodBank[]
  count: number
  data_notice: string
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
