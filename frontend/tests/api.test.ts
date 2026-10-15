import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDiscoveryUrl,
  fetchBloodBanks,
  formatTimestamp,
  type BloodBankListResponse,
} from '../src/services/api.ts'

describe('Discovery API Service', () => {
  const BASE_URL = 'http://127.0.0.1:8000'

  it('constructs an unfiltered URL when parameters are null, undefined, or "All"', () => {
    assert.equal(
      buildDiscoveryUrl(null, null, BASE_URL),
      'http://127.0.0.1:8000/api/blood-banks'
    )
    assert.equal(
      buildDiscoveryUrl('All', 'All', BASE_URL),
      'http://127.0.0.1:8000/api/blood-banks'
    )
  })

  it('constructs URL with city query parameter', () => {
    const url = buildDiscoveryUrl('Delhi', null, BASE_URL)
    assert.equal(url, 'http://127.0.0.1:8000/api/blood-banks?city=Delhi')
  })

  it('constructs URL with blood group query parameter and URL encodes plus sign', () => {
    const url = buildDiscoveryUrl(null, 'O+', BASE_URL)
    assert.equal(url, 'http://127.0.0.1:8000/api/blood-banks?blood_group=O%2B')

    const urlNeg = buildDiscoveryUrl(null, 'AB-', BASE_URL)
    assert.equal(urlNeg, 'http://127.0.0.1:8000/api/blood-banks?blood_group=AB-')
  })

  it('constructs URL with combined city and blood group parameters', () => {
    const url = buildDiscoveryUrl('Lucknow', 'A+', BASE_URL)
    assert.equal(url, 'http://127.0.0.1:8000/api/blood-banks?city=Lucknow&blood_group=A%2B')
  })

  it('formats UTC ISO 8601 timestamps accurately while retaining UTC provenance', () => {
    const isoUtc = '2026-10-15T12:00:00Z'
    const formatted = formatTimestamp(isoUtc)

    assert.equal(formatted.isoString, isoUtc)
    assert.ok(formatted.localDisplay.length > 0)
    assert.ok(formatted.utcDisplay.includes('2026-10-15T12:00:00'))
  })

  it('handles invalid timestamps gracefully without throwing', () => {
    const invalid = 'not-a-timestamp'
    const formatted = formatTimestamp(invalid)
    assert.equal(formatted.localDisplay, invalid)
    assert.equal(formatted.utcDisplay, invalid)
  })

  it('validates BloodBankListResponse contract structure', () => {
    const mockResponse: BloodBankListResponse = {
      items: [
        {
          id: 1,
          name: 'Demo Central Transfusion Facility',
          city: 'Delhi',
          locality: 'Connaught Place (Central Delhi)',
          stock_reports: [
            {
              id: 8,
              blood_bank_id: 1,
              blood_group: 'O-',
              units_reported: 5,
              source_name: 'Synthetic demo dataset',
              data_timestamp: '2026-10-15T12:00:00Z',
              verification_status: 'demo',
            },
          ],
        },
      ],
      count: 1,
      data_notice:
        'All records are synthetic demonstration data and do not reflect real-time hospital inventory or guaranteed physical blood availability.',
    }

    assert.equal(mockResponse.count, 1)
    assert.equal(mockResponse.items.length, 1)
    assert.equal(mockResponse.items[0].city, 'Delhi')
    assert.equal(mockResponse.items[0].stock_reports[0].blood_group, 'O-')
    assert.equal(mockResponse.items[0].stock_reports[0].verification_status, 'demo')
    assert.ok(mockResponse.data_notice.includes('synthetic demonstration data'))
  })

  it('validates empty response contract handling', () => {
    const emptyResponse: BloodBankListResponse = {
      items: [],
      count: 0,
      data_notice:
        'All records are synthetic demonstration data and do not reflect real-time hospital inventory or guaranteed physical blood availability.',
    }

    assert.equal(emptyResponse.count, 0)
    assert.equal(emptyResponse.items.length, 0)
    assert.ok(emptyResponse.data_notice.length > 0)
  })

  it('fetchBloodBanks successfully fetches and parses data when backend responds', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          items: [{ id: 1, name: 'Test Bank', city: 'Delhi', locality: 'CP', stock_reports: [] }],
          count: 1,
          data_notice: 'Synthetic data notice',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )

    try {
      const data = await fetchBloodBanks('Delhi', 'O+')
      assert.equal(data.count, 1)
      assert.equal(data.items[0].name, 'Test Bank')
      assert.equal(data.data_notice, 'Synthetic data notice')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('fetchBloodBanks throws descriptive error message on HTTP error response', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({ detail: "Invalid city 'Mumbai'. Supported cities: Delhi, Lucknow." }),
        { status: 422, headers: { 'Content-Type': 'application/json' } }
      )

    try {
      await assert.rejects(
        async () => {
          await fetchBloodBanks('Mumbai')
        },
        {
          name: 'Error',
          message: "Invalid city 'Mumbai'. Supported cities: Delhi, Lucknow.",
        }
      )
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('fetchBloodBanks rejects on network connection failure (backend down)', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = async () => {
      throw new TypeError('fetch failed: ECONNREFUSED 127.0.0.1:8000')
    }

    try {
      await assert.rejects(
        async () => {
          await fetchBloodBanks('Delhi')
        },
        {
          name: 'TypeError',
          message: /fetch failed/,
        }
      )
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})
