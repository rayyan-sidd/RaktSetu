import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDiscoveryUrl,
  fetchBloodBanks,
  formatTimestamp,
  getApiBaseUrl,
  getReportFreshnessInfo,
  filterAndSortBloodBanks,
  getTelegramBotUrl,
  type BloodBank,
  type BloodBankListResponse,
  type StockReport,
} from '../src/services/api.ts'

describe('Discovery API Service', () => {
  it('defaults to relative /api path for Vite dev proxy when baseUrl is empty or omitted', () => {
    assert.equal(getApiBaseUrl(), '')
    assert.equal(buildDiscoveryUrl(), '/api/blood-banks')
    assert.equal(buildDiscoveryUrl(null, null), '/api/blood-banks')
    assert.equal(buildDiscoveryUrl('All', 'All'), '/api/blood-banks')
  })

  it('constructs relative proxy URL with city query parameter', () => {
    const url = buildDiscoveryUrl('Delhi', null)
    assert.equal(url, '/api/blood-banks?city=Delhi')
  })

  it('constructs relative proxy URL with blood group query parameter and URL encodes plus sign', () => {
    const url = buildDiscoveryUrl(null, 'O+')
    assert.equal(url, '/api/blood-banks?blood_group=O%2B')

    const urlNeg = buildDiscoveryUrl(null, 'AB-')
    assert.equal(urlNeg, '/api/blood-banks?blood_group=AB-')
  })

  it('constructs relative proxy URL with combined city and blood group parameters', () => {
    const url = buildDiscoveryUrl('Lucknow', 'A+')
    assert.equal(url, '/api/blood-banks?city=Lucknow&blood_group=A%2B')
  })

  it('supports explicitly configured baseUrl for deployment while preserving query encoding', () => {
    const customBase = 'http://127.0.0.1:8000'
    assert.equal(
      buildDiscoveryUrl(null, null, customBase),
      'http://127.0.0.1:8000/api/blood-banks'
    )
    assert.equal(
      buildDiscoveryUrl('Delhi', 'O+', customBase),
      'http://127.0.0.1:8000/api/blood-banks?city=Delhi&blood_group=O%2B'
    )
    assert.equal(
      buildDiscoveryUrl(null, null, 'https://api.raktsetu.org/'),
      'https://api.raktsetu.org/api/blood-banks'
    )
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

  describe('Report Freshness and Provenance Handling', () => {
    it('correctly handles null or missing stock report', () => {
      const freshness = getReportFreshnessInfo(null)
      assert.equal(freshness.type, 'retrieval_only')
      assert.equal(freshness.primaryDisplay, 'No data')
      assert.equal(freshness.isLiveBadge, false)
      assert.equal(freshness.isDemo, false)
    })

    it('identifies synthetic demo snapshots and displays simulation disclaimer', () => {
      const demoReport: StockReport = {
        id: 1,
        blood_bank_id: 1,
        blood_group: 'O+',
        blood_component: 'Unspecified',
        units_reported: 12,
        source_name: 'Synthetic demo dataset',
        data_timestamp: '2026-10-15T12:00:00Z',
        verification_status: 'demo',
      }

      const freshness = getReportFreshnessInfo(demoReport)
      assert.equal(freshness.type, 'demo_snapshot')
      assert.equal(freshness.isDemo, true)
      assert.equal(freshness.isLiveBadge, false)
      assert.equal(freshness.primaryLabel, 'Snapshot Time')
      assert.ok(freshness.secondaryNote?.includes('Simulated demonstration timestamp'))
      assert.ok(freshness.utcDisplay?.includes('2026-10-15T12:00:00'))
    })

    it('identifies live stock badge indicators without claiming exact time or physical guarantee', () => {
      const liveBadgeReport: StockReport = {
        id: 2,
        blood_bank_id: 2,
        blood_group: 'A+',
        blood_component: 'Whole Blood',
        units_reported: 8,
        source_name: 'e-RaktKosh',
        verification_status: 'reported_unverified',
        freshness_indicator: 'live_stock_badge',
        source_reported_timestamp: null,
        retrieval_timestamp: '2026-10-16T06:00:00Z',
        data_timestamp: '2026-10-16T06:00:00Z',
      }

      const freshness = getReportFreshnessInfo(liveBadgeReport)
      assert.equal(freshness.type, 'live_badge')
      assert.equal(freshness.isLiveBadge, true)
      assert.equal(freshness.isDemo, false)
      assert.equal(freshness.primaryLabel, 'Portal Indicator')
      assert.equal(freshness.primaryDisplay, 'Live Stock Badge')
      // Must not claim physical guarantee and must state portal indicator
      assert.ok(freshness.secondaryNote?.includes('not a physical stock guarantee'))
      assert.ok(freshness.secondaryNote?.includes('Retrieved by RaktSetu'))
    })

    it('distinguishes source-reported hospital timestamp from RaktSetu retrieval time', () => {
      const sourceReported: StockReport = {
        id: 3,
        blood_bank_id: 2,
        blood_group: 'B+',
        blood_component: 'Packed Red Blood Cells',
        units_reported: 15,
        source_name: 'e-RaktKosh',
        verification_status: 'reported_unverified',
        source_reported_timestamp: '2026-10-16T05:30:00Z',
        retrieval_timestamp: '2026-10-16T06:00:00Z',
        data_timestamp: '2026-10-16T06:00:00Z',
      }

      const freshness = getReportFreshnessInfo(sourceReported)
      assert.equal(freshness.type, 'source_timestamp')
      assert.equal(freshness.isLiveBadge, false)
      assert.equal(freshness.primaryLabel, 'Hospital Reported')
      assert.ok(freshness.utcDisplay?.includes('2026-10-16T05:30:00'))
      // Retrieval time is mentioned separately as RaktSetu retrieval, not hospital update
      assert.equal(freshness.isStale, false)
      assert.ok(freshness.secondaryNote?.includes('Retrieved by RaktSetu'))
    })

    it('identifies stale source reports when timestamp is older than 24 hours', () => {
      const staleReport: StockReport = {
        id: 33,
        blood_bank_id: 10,
        blood_group: 'O+',
        blood_component: 'Whole Blood',
        units_reported: 8,
        source_name: 'e-RaktKosh',
        verification_status: 'reported_unverified',
        source_reported_timestamp: '2026-07-13T05:44:24Z',
        retrieval_timestamp: '2026-10-16T06:00:00Z',
        data_timestamp: '2026-10-16T06:00:00Z',
      }

      const freshness = getReportFreshnessInfo(staleReport)
      assert.equal(freshness.type, 'source_timestamp')
      assert.equal(freshness.isStale, true)
      assert.ok(freshness.secondaryNote?.includes('Stale report (>24h old)'))
      assert.ok(freshness.secondaryNote?.includes('Retrieved by RaktSetu'))
    })

    it('falls back to retrieval-only when source provides neither source timestamp nor live badge', () => {
      const fallbackReport: StockReport = {
        id: 4,
        blood_bank_id: 3,
        blood_group: 'AB-',
        blood_component: 'Platelets',
        units_reported: 4,
        source_name: 'e-RaktKosh',
        verification_status: 'reported_unverified',
        retrieval_timestamp: '2026-10-16T06:10:00Z',
        data_timestamp: '2026-10-16T06:10:00Z',
      }

      const freshness = getReportFreshnessInfo(fallbackReport)
      assert.equal(freshness.type, 'retrieval_only')
      assert.equal(freshness.primaryLabel, 'Retrieval Time')
      assert.ok(freshness.secondaryNote?.includes('did not report an explicit hospital update timestamp'))
    })
  })

  describe('Mixed Sources and Component Contract', () => {
    it('validates BloodBankListResponse envelope with data_timestamp and mixed records', () => {
      const mixedResponse: BloodBankListResponse = {
        items: [
          {
            id: 1,
            name: 'Demo Central Transfusion Facility',
            city: 'Delhi',
            locality: 'Central Delhi',
            source_type: 'demo',
            source_name: 'Synthetic demo dataset',
            stock_reports: [
              {
                id: 101,
                blood_bank_id: 1,
                blood_group: 'O+',
                blood_component: 'Unspecified',
                units_reported: 20,
                source_name: 'Synthetic demo dataset',
                verification_status: 'demo',
                data_timestamp: '2026-10-15T12:00:00Z',
              },
            ],
          },
          {
            id: 2,
            name: 'AIIMS Blood Centre',
            city: 'Delhi',
            locality: 'Ansari Nagar',
            source_type: 'external_source',
            source_name: 'e-RaktKosh',
            source_facility_id: 'eraktkosh:delhi:aiims',
            category: 'Government',
            facility_type: 'Hospital',
            stock_reports: [
              {
                id: 201,
                blood_bank_id: 2,
                blood_group: 'O+',
                blood_component: 'Packed Red Blood Cells',
                units_reported: 45,
                source_name: 'e-RaktKosh',
                verification_status: 'reported_unverified',
                source_reported_timestamp: '2026-10-16T05:00:00Z',
                retrieval_timestamp: '2026-10-16T06:00:00Z',
                data_timestamp: '2026-10-16T06:00:00Z',
              },
            ],
          },
        ],
        count: 2,
        data_notice:
          'Records include both synthetic demonstration data and official source-reported snapshots from e-RaktKosh (MoHFW). External inventory is source-reported, may be stale, and does not guarantee real-time physical blood availability. Always verify directly with the blood bank.',
        data_timestamp: '2026-10-16T06:00:00Z',
      }

      assert.equal(mixedResponse.count, 2)
      assert.equal(mixedResponse.data_timestamp, '2026-10-16T06:00:00Z')
      assert.ok(mixedResponse.data_notice.includes('synthetic demonstration data'))
      assert.ok(mixedResponse.data_notice.includes('e-RaktKosh'))

      // Legacy demo record keeps Unspecified
      const demoBank = mixedResponse.items[0]
      assert.equal(demoBank.source_type, 'demo')
      assert.equal(demoBank.stock_reports[0].blood_component, 'Unspecified')
      assert.notEqual(demoBank.stock_reports[0].blood_component, 'Whole Blood')

      // External record has concrete component and reported_unverified
      const extBank = mixedResponse.items[1]
      assert.equal(extBank.source_type, 'external_source')
      assert.equal(extBank.stock_reports[0].blood_component, 'Packed Red Blood Cells')
      assert.equal(extBank.stock_reports[0].verification_status, 'reported_unverified')
    })
  })

  describe('Discovery Real Data Prioritization and Demo Filtering', () => {
    const demoFacility1: BloodBank = {
      id: 1,
      name: 'Demo Central Transfusion Facility',
      city: 'Delhi',
      locality: 'Connaught Place',
      source_type: 'demo',
      source_name: 'Synthetic demo dataset',
      stock_reports: [
        {
          id: 101,
          blood_bank_id: 1,
          blood_group: 'O+',
          blood_component: 'Unspecified',
          units_reported: 12,
          source_name: 'Synthetic demo dataset',
          verification_status: 'demo',
        },
      ],
    }

    const demoFacility2: BloodBank = {
      id: 2,
      name: 'Demo North Charitable Blood Centre',
      city: 'Lucknow',
      locality: 'Hazratganj',
      source_type: 'demo',
      source_name: 'Synthetic demo dataset',
      stock_reports: [
        {
          id: 102,
          blood_bank_id: 2,
          blood_group: 'B+',
          blood_component: 'Unspecified',
          units_reported: 8,
          source_name: 'Synthetic demo dataset',
          verification_status: 'demo',
        },
      ],
    }

    const extFacility1: BloodBank = {
      id: 10,
      name: 'AIIMS Main Blood Bank',
      city: 'Delhi',
      locality: 'Ansari Nagar',
      source_type: 'external_source',
      source_name: 'e-RaktKosh',
      stock_reports: [
        {
          id: 201,
          blood_bank_id: 10,
          blood_group: 'O+',
          blood_component: 'Whole Blood',
          units_reported: 30,
          source_name: 'e-RaktKosh',
          verification_status: 'reported_unverified',
          source_reported_timestamp: '2026-10-16T05:00:00Z',
        },
      ],
    }

    const extFacility2: BloodBank = {
      id: 11,
      name: 'Safdarjung Hospital Blood Centre',
      city: 'Delhi',
      locality: 'Ring Road',
      source_type: 'external_source',
      source_name: 'e-RaktKosh',
      stock_reports: [
        {
          id: 202,
          blood_bank_id: 11,
          blood_group: 'A+',
          blood_component: 'Whole Blood',
          units_reported: 15,
          source_name: 'e-RaktKosh',
          verification_status: 'reported_unverified',
          source_reported_timestamp: '2026-10-16T05:15:00Z',
        },
      ],
    }

    const extFacility3: BloodBank = {
      id: 12,
      name: 'KGMU Blood Bank Lucknow',
      city: 'Lucknow',
      locality: 'Chowk',
      source_type: 'external_source',
      source_name: 'e-RaktKosh',
      stock_reports: [
        {
          id: 203,
          blood_bank_id: 12,
          blood_group: 'O+',
          blood_component: 'Whole Blood',
          units_reported: 25,
          source_name: 'e-RaktKosh',
          verification_status: 'reported_unverified',
          source_reported_timestamp: '2026-10-16T05:30:00Z',
        },
      ],
    }

    const mixedDataset: BloodBank[] = [
      demoFacility1,
      extFacility1,
      demoFacility2,
      extFacility2,
      extFacility3,
    ]

    it('excludes demo facilities by default when includeDemo is false or omitted', () => {
      // Test with omitted parameter (default false)
      const defaultResult = filterAndSortBloodBanks(mixedDataset)
      assert.equal(defaultResult.length, 3)
      assert.ok(defaultResult.every(b => b.source_type !== 'demo'))
      assert.deepEqual(
        defaultResult.map(b => b.id),
        [10, 11, 12]
      )

      // Test with explicit false
      const explicitFalseResult = filterAndSortBloodBanks(mixedDataset, false)
      assert.equal(explicitFalseResult.length, 3)
      assert.ok(explicitFalseResult.every(b => b.source_type !== 'demo'))
    })

    it('includes demo facilities when includeDemo toggle is enabled (true)', () => {
      const result = filterAndSortBloodBanks(mixedDataset, true)
      assert.equal(result.length, 5)
      // Contains both external and demo
      assert.equal(result.filter(b => b.source_type === 'external_source').length, 3)
      assert.equal(result.filter(b => b.source_type === 'demo').length, 2)
    })

    it('strictly orders external facilities first and demo facilities afterward when enabled', () => {
      const result = filterAndSortBloodBanks(mixedDataset, true)
      assert.equal(result.length, 5)

      // First 3 must be external facilities
      assert.equal(result[0].id, 10)
      assert.equal(result[0].source_type, 'external_source')
      assert.equal(result[1].id, 11)
      assert.equal(result[1].source_type, 'external_source')
      assert.equal(result[2].id, 12)
      assert.equal(result[2].source_type, 'external_source')

      // Following 2 must be demo facilities
      assert.equal(result[3].id, 1)
      assert.equal(result[3].source_type, 'demo')
      assert.equal(result[4].id, 2)
      assert.equal(result[4].source_type, 'demo')

      // Verify that every external item appears before every demo item
      const firstDemoIndex = result.findIndex(b => b.source_type === 'demo')
      const lastExternalIndex = result
        .map((b, i) => (b.source_type !== 'demo' ? i : -1))
        .reduce((max, i) => Math.max(max, i), -1)
      assert.ok(lastExternalIndex < firstDemoIndex)
    })

    it('restores complete demo exclusion when toggle is disabled again', () => {
      // Start OFF
      const initial = filterAndSortBloodBanks(mixedDataset, false)
      assert.equal(initial.length, 3)
      assert.ok(!initial.some(b => b.source_type === 'demo'))

      // Toggle ON
      const toggledOn = filterAndSortBloodBanks(mixedDataset, true)
      assert.equal(toggledOn.length, 5)
      assert.ok(toggledOn.some(b => b.source_type === 'demo'))

      // Toggle OFF
      const toggledOff = filterAndSortBloodBanks(mixedDataset, false)
      assert.equal(toggledOff.length, 3)
      assert.ok(!toggledOff.some(b => b.source_type === 'demo'))
      assert.deepEqual(
        toggledOff.map(b => b.id),
        [10, 11, 12]
      )
    })

    it('preserves city and blood-group filtering across toggle states', () => {
      // Filter for Delhi
      const delhiBanks = mixedDataset.filter(b => b.city === 'Delhi')
      assert.equal(delhiBanks.length, 3) // 2 external, 1 demo

      const delhiDefault = filterAndSortBloodBanks(delhiBanks, false)
      assert.equal(delhiDefault.length, 2)
      assert.deepEqual(
        delhiDefault.map(b => b.name),
        ['AIIMS Main Blood Bank', 'Safdarjung Hospital Blood Centre']
      )

      const delhiWithDemo = filterAndSortBloodBanks(delhiBanks, true)
      assert.equal(delhiWithDemo.length, 3)
      assert.deepEqual(
        delhiWithDemo.map(b => b.name),
        [
          'AIIMS Main Blood Bank',
          'Safdarjung Hospital Blood Centre',
          'Demo Central Transfusion Facility',
        ]
      )

      // Filter for blood group O+
      const oPlusBanks = mixedDataset.filter(b =>
        b.stock_reports.some(r => r.blood_group === 'O+')
      )
      assert.equal(oPlusBanks.length, 3) // 2 external (AIIMS, KGMU), 1 demo

      const oPlusDefault = filterAndSortBloodBanks(oPlusBanks, false)
      assert.equal(oPlusDefault.length, 2)
      assert.ok(oPlusDefault.every(b => b.source_type !== 'demo'))
      assert.deepEqual(
        oPlusDefault.map(b => b.id),
        [10, 12]
      )

      const oPlusWithDemo = filterAndSortBloodBanks(oPlusBanks, true)
      assert.equal(oPlusWithDemo.length, 3)
      assert.deepEqual(
        oPlusWithDemo.map(b => b.id),
        [10, 12, 1] // external [10, 12] first, then demo [1]
      )
    })

    it('handles edge cases gracefully: empty list, pure external, pure demo', () => {
      // Empty input
      assert.deepEqual(filterAndSortBloodBanks([], false), [])
      assert.deepEqual(filterAndSortBloodBanks([], true), [])

      // Pure external list
      const pureExt = [extFacility1, extFacility2]
      assert.deepEqual(filterAndSortBloodBanks(pureExt, false), pureExt)
      assert.deepEqual(filterAndSortBloodBanks(pureExt, true), pureExt)

      // Pure demo list
      const pureDemo = [demoFacility1, demoFacility2]
      assert.deepEqual(filterAndSortBloodBanks(pureDemo, false), [])
      assert.deepEqual(filterAndSortBloodBanks(pureDemo, true), pureDemo)
    })
  })

  describe('Telegram Bot Configuration', () => {
    it('returns null when VITE_TELEGRAM_BOT_URL is unset, empty, or placeholder', () => {
      // In Node test runner without env var, getTelegramBotUrl() should safely return null
      assert.equal(getTelegramBotUrl(), null)
    })
  })
})
