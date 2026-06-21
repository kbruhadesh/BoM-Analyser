/**
 * Frontend tests using Vitest + @testing-library/react
 *
 * Run:  npm test
 *
 * Covers:
 *  - utils: formatINR, priceRank, detectFormat (via utils)
 *  - useBomAnalysis hook state machine
 *  - BomUploader render + interactions
 *  - SummaryBar render
 *  - VendorMatrix render + row expand
 *  - OptimizationCard render
 *  - ExportBar button states
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { renderHook } from '@testing-library/react'
import React from 'react'

// ── Mocks ─────────────────────────────────────────────────────────────────────
vi.mock('../src/lib/api.js', () => ({
  analyzeBom:    vi.fn(),
  getTaskStatus: vi.fn(),
  getTaskResult: vi.fn(),
  exportResult:  vi.fn(),
  normalizeMpn:  vi.fn(),
  getFxRate:     vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(status, msg) { super(msg); this.status = status }
  },
}))

// ── 1. Utility functions ───────────────────────────────────────────────────────

describe('formatINR', () => {
  const { formatINR } = await import('../src/lib/utils.js')

  it('formats integer prices with ₹ symbol', () => {
    expect(formatINR(1000)).toMatch(/₹/)
    expect(formatINR(1000)).toContain('1,000')
  })

  it('uses 4 decimal places for sub-₹1 prices', () => {
    const result = formatINR(0.0038)
    expect(result).toBe('₹0.0038')
  })

  it('uses 3 decimal places for ₹1-₹10 range', () => {
    const result = formatINR(3.456)
    expect(result).toContain('3.456')
  })

  it('uses 2 decimal places for ₹10+ prices', () => {
    const result = formatINR(104.375)
    expect(result).toContain('104.38')
  })

  it('returns — for null values', () => {
    expect(formatINR(null)).toBe('—')
    expect(formatINR(undefined)).toBe('—')
  })

  it('handles zero correctly', () => {
    // 0 < 1 so gets 4dp
    expect(formatINR(0)).toBe('₹0.0000')
  })
})


describe('priceRank', () => {
  const { priceRank } = await import('../src/lib/utils.js')

  it('returns best for the lowest price', () => {
    expect(priceRank(81.57, [81.57, 104.37, 108.55, 112.62])).toBe('best')
  })

  it('returns high for the highest price', () => {
    expect(priceRank(112.62, [81.57, 104.37, 108.55, 112.62])).toBe('high')
  })

  it('returns mid for middle prices', () => {
    expect(priceRank(104.37, [81.57, 104.37, 108.55, 112.62])).toBe('mid')
  })

  it('returns oos when price is null', () => {
    expect(priceRank(null, [81.57, 104.37])).toBe('oos')
  })

  it('returns best when only one in-stock price', () => {
    expect(priceRank(100, [100])).toBe('best')
  })

  it('returns oos when allPrices is empty', () => {
    expect(priceRank(50, [])).toBe('oos')
  })
})


describe('getVendorConfig', () => {
  const { getVendorConfig } = await import('../src/lib/utils.js')

  it('returns correct badge class for known vendors', () => {
    expect(getVendorConfig('DigiKey').badgeClass).toBe('badge-digikey')
    expect(getVendorConfig('LCSC').badgeClass).toBe('badge-lcsc')
    expect(getVendorConfig('Robu').badgeClass).toBe('badge-robu')
  })

  it('returns short code for unknown vendor', () => {
    const cfg = getVendorConfig('SomeNewVendor')
    expect(cfg.short).toBe('SO')
  })

  it('returns the full label for known vendors', () => {
    expect(getVendorConfig('Robu').label).toBe('Robu.in')
  })
})


describe('formatQty', () => {
  const { formatQty } = await import('../src/lib/utils.js')

  it('formats with Indian locale', () => {
    // 100000 in Indian system = 1,00,000
    const result = formatQty(100000)
    expect(result).toMatch(/1,00,000|100,000/)   // allow either locale
  })

  it('returns — for null', () => {
    expect(formatQty(null)).toBe('—')
  })
})


// ── 2. useBomAnalysis hook ─────────────────────────────────────────────────────

describe('useBomAnalysis hook', () => {
  const { useBomAnalysis, STATES } = await import('../src/hooks/useBomAnalysis.js')
  const api = await import('../src/lib/api.js')

  beforeEach(() => vi.useFakeTimers())
  afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

  it('starts in IDLE state', () => {
    const { result } = renderHook(() => useBomAnalysis())
    expect(result.current.state).toBe(STATES.IDLE)
    expect(result.current.isIdle).toBe(true)
  })

  it('transitions to POLLING after successful submit', async () => {
    api.analyzeBom.mockResolvedValue({ task_id: 'test-uuid-1234' })
    api.getTaskStatus.mockResolvedValue({ status: 'processing', progress: 10 })

    const { result } = renderHook(() => useBomAnalysis())
    await act(async () => {
      await result.current.submit('Qty,MPN\n10,ATmega328P', 'csv')
    })

    expect(result.current.state).toBe(STATES.POLLING)
    expect(result.current.taskId).toBe('test-uuid-1234')
  })

  it('transitions to COMPLETE when status is complete', async () => {
    const mockResult = {
      summary: { total_components: 1, total_estimated_cost_inr: 815.70, total_savings_inr: 228.0, components_in_stock: 1, components_out_of_stock: 0, cheapest_vendor_overall: 'LCSC', usd_inr_rate: 83.5 },
      results: [],
    }
    api.analyzeBom.mockResolvedValue({ task_id: 'abc-123' })
    api.getTaskStatus.mockResolvedValue({ status: 'complete', progress: 100 })
    api.getTaskResult.mockResolvedValue(mockResult)

    const { result } = renderHook(() => useBomAnalysis())
    await act(async () => {
      await result.current.submit('test bom', 'text')
    })

    // Trigger polling cycle
    await act(async () => { vi.advanceTimersByTime(1300) })

    expect(result.current.state).toBe(STATES.COMPLETE)
    expect(result.current.result).toEqual(mockResult)
  })

  it('transitions to FAILED on API error', async () => {
    api.analyzeBom.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useBomAnalysis())
    await act(async () => {
      await result.current.submit('test', 'text')
    })

    expect(result.current.state).toBe(STATES.FAILED)
    expect(result.current.error).toBeTruthy()
  })

  it('reset() returns to IDLE', async () => {
    api.analyzeBom.mockResolvedValue({ task_id: 'xyz' })
    api.getTaskStatus.mockResolvedValue({ status: 'processing', progress: 20 })

    const { result } = renderHook(() => useBomAnalysis())
    await act(async () => { await result.current.submit('test', 'text') })
    act(() => { result.current.reset() })

    expect(result.current.state).toBe(STATES.IDLE)
    expect(result.current.taskId).toBeNull()
    expect(result.current.result).toBeNull()
  })

  it('progress and currentComponent are updated from status poll', async () => {
    api.analyzeBom.mockResolvedValue({ task_id: 'prog-test' })
    api.getTaskStatus.mockResolvedValue({ status: 'processing', progress: 55, current_component: 'NRF24L01+' })

    const { result } = renderHook(() => useBomAnalysis())
    await act(async () => { await result.current.submit('test', 'text') })
    await act(async () => { vi.advanceTimersByTime(1300) })

    expect(result.current.progress).toBe(55)
    expect(result.current.currentComponent).toBe('NRF24L01+')
  })
})


// ── 3. BomUploader component ───────────────────────────────────────────────────

describe('BomUploader', () => {
  const BomUploader = (await import('../src/components/BomUploader.jsx')).default

  it('renders without crashing', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={false} />)
    expect(screen.getByText(/BoM Analyzer/i)).toBeTruthy()
  })

  it('shows Analyze BoM button disabled when no content', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={false} />)
    const btn = screen.getByRole('button', { name: /Analyze BoM/i })
    expect(btn.disabled).toBe(true)
  })

  it('enables submit button after text is entered', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={false} />)
    const textarea = screen.getByPlaceholderText(/Qty,MPN/i)
    fireEvent.change(textarea, { target: { value: 'Qty,MPN\n10,ATmega328P' } })
    const btn = screen.getByRole('button', { name: /Analyze BoM/i })
    expect(btn.disabled).toBe(false)
  })

  it('calls onSubmit with text when Analyze button clicked', () => {
    const onSubmit = vi.fn()
    render(<BomUploader onSubmit={onSubmit} isBusy={false} />)
    const textarea = screen.getByPlaceholderText(/Qty,MPN/i)
    fireEvent.change(textarea, { target: { value: 'Qty,MPN\n10,ATmega328P' } })
    fireEvent.click(screen.getByRole('button', { name: /Analyze BoM/i }))
    expect(onSubmit).toHaveBeenCalledWith('Qty,MPN\n10,ATmega328P', 'csv')
  })

  it('loads sample BoM when Load sample is clicked', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={false} />)
    fireEvent.click(screen.getByRole('button', { name: /Load sample/i }))
    const textarea = screen.getByPlaceholderText(/Qty,MPN/i)
    expect(textarea.value).toContain('ATmega328P')
  })

  it('shows Analyzing spinner when isBusy=true', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={true} />)
    expect(screen.getByText(/Analyzing/i)).toBeTruthy()
  })

  it('shows detected format badge after paste', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={false} />)
    const textarea = screen.getByPlaceholderText(/Qty,MPN/i)
    fireEvent.change(textarea, { target: { value: 'Qty,MPN,Desc\n10,part,test' } })
    expect(screen.getByText('CSV')).toBeTruthy()
  })

  it('shows row count after content is entered', () => {
    render(<BomUploader onSubmit={() => {}} isBusy={false} />)
    const textarea = screen.getByPlaceholderText(/Qty,MPN/i)
    fireEvent.change(textarea, { target: { value: 'Qty,MPN\n10,A\n5,B\n20,C' } })
    expect(screen.getByText(/3 rows detected/i)).toBeTruthy()
  })
})


// ── 4. SummaryBar component ────────────────────────────────────────────────────

describe('SummaryBar', () => {
  const SummaryBar = (await import('../src/components/SummaryBar.jsx')).default

  const mockSummary = {
    total_components: 5,
    total_estimated_cost_inr: 12745.50,
    total_savings_inr: 2310.25,
    components_in_stock: 4,
    components_out_of_stock: 1,
    cheapest_vendor_overall: 'LCSC',
    usd_inr_rate: 83.52,
  }

  it('renders all 4 metric cards', () => {
    render(<SummaryBar summary={mockSummary} />)
    expect(screen.getByText(/Est\. Total Cost/i)).toBeTruthy()
    expect(screen.getByText(/Total Savings/i)).toBeTruthy()
    expect(screen.getByText(/In Stock/i)).toBeTruthy()
    expect(screen.getByText(/Best Vendor/i)).toBeTruthy()
  })

  it('shows correct in-stock ratio', () => {
    render(<SummaryBar summary={mockSummary} />)
    expect(screen.getByText('4/5')).toBeTruthy()
  })

  it('shows best vendor name', () => {
    render(<SummaryBar summary={mockSummary} />)
    expect(screen.getByText('LCSC')).toBeTruthy()
  })

  it('shows FX rate', () => {
    render(<SummaryBar summary={mockSummary} />)
    expect(screen.getByText(/83\.52/)).toBeTruthy()
  })

  it('returns null when summary is null', () => {
    const { container } = render(<SummaryBar summary={null} />)
    expect(container.firstChild).toBeNull()
  })
})


// ── 5. VendorMatrix component ──────────────────────────────────────────────────

const MOCK_RESULTS = [
  {
    component: 'ATmega328P-PU',
    normalized_mpn: 'ATmega328P',
    quantity_required: 10,
    best_vendor: 'LCSC',
    best_unit_price_inr: 81.57,
    best_total_price_inr: 815.70,
    availability: 'In Stock',
    moq: 5,
    savings_vs_worst_inr: 228.0,
    recommendation_reason: 'LCSC: lowest price, MOQ fits qty',
    all_vendors: [
      { vendor: 'DigiKey', vendor_part_number: 'ATMEGA-ND',  unit_price_inr: 104.37, stock_qty: 5000, moq: 1, availability: 'In Stock',     lead_time_weeks: null, price_breaks: [{ qty: 10, price_inr: 104.37 }] },
      { vendor: 'Mouser',  vendor_part_number: '556-ATM',    unit_price_inr: 108.55, stock_qty: 3200, moq: 1, availability: 'In Stock',     lead_time_weeks: null, price_breaks: [] },
      { vendor: 'LCSC',    vendor_part_number: 'C1570968',   unit_price_inr: 81.57,  stock_qty: 12000,moq: 5, availability: 'In Stock',     lead_time_weeks: null, price_breaks: [{ qty: 5, price_inr: 81.57 }, { qty: 50, price_inr: 70.98 }] },
      { vendor: 'Arrow',   vendor_part_number: 'ATmega328P', unit_price_inr: 112.62, stock_qty: 0,    moq: 1, availability: 'Out of Stock', lead_time_weeks: 8,    price_breaks: [] },
    ],
  },
]

describe('VendorMatrix', () => {
  const VendorMatrix = (await import('../src/components/VendorMatrix.jsx')).default

  it('renders component MPN in table', () => {
    render(<VendorMatrix results={MOCK_RESULTS} />)
    expect(screen.getByText('ATmega328P')).toBeTruthy()
  })

  it('renders OOS cell for Arrow', () => {
    render(<VendorMatrix results={MOCK_RESULTS} />)
    expect(screen.getByText('OOS')).toBeTruthy()
  })

  it('shows best vendor in Best column', () => {
    render(<VendorMatrix results={MOCK_RESULTS} />)
    // LCSC should appear as best vendor somewhere
    const lcscEls = screen.getAllByText('LCSC')
    expect(lcscEls.length).toBeGreaterThan(0)
  })

  it('shows savings value', () => {
    render(<VendorMatrix results={MOCK_RESULTS} />)
    expect(screen.getByText(/228/)).toBeTruthy()
  })

  it('expands price breaks row on click', () => {
    render(<VendorMatrix results={MOCK_RESULTS} />)
    const row = screen.getByText('ATmega328P').closest('tr')
    fireEvent.click(row)
    // Price break detail should appear
    expect(screen.getByText(/price break/i)).toBeTruthy()
  })

  it('collapses row on second click', () => {
    render(<VendorMatrix results={MOCK_RESULTS} />)
    const row = screen.getByText('ATmega328P').closest('tr')
    fireEvent.click(row)
    fireEvent.click(row)
    expect(screen.queryByText(/price break/i)).toBeNull()
  })

  it('returns null for empty results', () => {
    const { container } = render(<VendorMatrix results={[]} />)
    expect(container.firstChild).toBeNull()
  })
})


// ── 6. OptimizationCard component ─────────────────────────────────────────────

describe('OptimizationCard', () => {
  const OptimizationCard = (await import('../src/components/OptimizationCard.jsx')).default

  it('renders MPN and quantity', () => {
    render(<OptimizationCard result={MOCK_RESULTS[0]} />)
    expect(screen.getByText('ATmega328P')).toBeTruthy()
    expect(screen.getByText(/10 units required/i)).toBeTruthy()
  })

  it('renders in-stock indicator', () => {
    render(<OptimizationCard result={MOCK_RESULTS[0]} />)
    expect(screen.getByText(/in stock/i)).toBeTruthy()
  })

  it('shows best price with ₹ symbol', () => {
    render(<OptimizationCard result={MOCK_RESULTS[0]} />)
    expect(screen.getByText(/₹81\.57/i)).toBeTruthy()
  })

  it('shows savings vs worst', () => {
    render(<OptimizationCard result={MOCK_RESULTS[0]} />)
    expect(screen.getByText(/228/)).toBeTruthy()
  })

  it('shows recommendation reason', () => {
    render(<OptimizationCard result={MOCK_RESULTS[0]} />)
    expect(screen.getByText(/lowest price/i)).toBeTruthy()
  })

  it('shows OOS indicator when all vendors are OOS', () => {
    const oosResult = {
      ...MOCK_RESULTS[0],
      best_vendor: null,
      availability: 'Out of Stock',
      all_vendors: MOCK_RESULTS[0].all_vendors.map(v => ({ ...v, availability: 'Out of Stock', stock_qty: 0 })),
    }
    render(<OptimizationCard result={oosResult} />)
    expect(screen.getByText(/No stock/i)).toBeTruthy()
  })

  it('renders split order plan when provided', () => {
    const splitResult = {
      ...MOCK_RESULTS[0],
      split_order: [
        { vendor: 'LCSC',    vendor_part_number: 'C1', qty_from_vendor: 6, unit_price_inr: 81.57,  subtotal_inr: 489.42 },
        { vendor: 'DigiKey', vendor_part_number: 'C2', qty_from_vendor: 4, unit_price_inr: 104.37, subtotal_inr: 417.48 },
      ],
    }
    render(<OptimizationCard result={splitResult} />)
    expect(screen.getByText(/split order/i)).toBeTruthy()
  })
})


// ── 7. ExportBar component ─────────────────────────────────────────────────────

describe('ExportBar', () => {
  const ExportBar = (await import('../src/components/ExportBar.jsx')).default
  const api = await import('../src/lib/api.js')

  const mockSummary = {
    total_components: 5, total_estimated_cost_inr: 12745.50,
    total_savings_inr: 2310.25, usd_inr_rate: 83.5,
  }

  it('renders Export Excel and Export JSON buttons', () => {
    render(<ExportBar taskId="test-123" summary={mockSummary} />)
    expect(screen.getByRole('button', { name: /Export Excel/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Export JSON/i })).toBeTruthy()
  })

  it('calls exportResult with excel format on Excel button click', async () => {
    api.exportResult.mockResolvedValue(new Blob(['fake xlsx'], { type: 'application/xlsx' }))
    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    global.URL.revokeObjectURL = vi.fn()

    render(<ExportBar taskId="test-123" summary={mockSummary} />)
    fireEvent.click(screen.getByRole('button', { name: /Export Excel/i }))

    await waitFor(() => {
      expect(api.exportResult).toHaveBeenCalledWith('test-123', 'excel')
    })
  })

  it('calls exportResult with json format on JSON button click', async () => {
    api.exportResult.mockResolvedValue(new Blob(['{}'], { type: 'application/json' }))
    global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    global.URL.revokeObjectURL = vi.fn()

    render(<ExportBar taskId="test-123" summary={mockSummary} />)
    fireEvent.click(screen.getByRole('button', { name: /Export JSON/i }))

    await waitFor(() => {
      expect(api.exportResult).toHaveBeenCalledWith('test-123', 'json')
    })
  })

  it('shows Copied! after Copy summary is clicked', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) }
    })

    render(<ExportBar taskId="test-123" summary={mockSummary} />)
    fireEvent.click(screen.getByRole('button', { name: /Copy summary/i }))

    await waitFor(() => {
      expect(screen.getByText(/Copied!/i)).toBeTruthy()
    })
  })
})
