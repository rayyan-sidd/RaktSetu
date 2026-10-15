import { useState, useEffect } from 'react'
import {
  Sun,
  Moon,
  Search,
  Droplet,
  ShieldCheck,
  Clock,
  MapPin,
  Bot,
  AlertTriangle,
  HeartHandshake,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Database,
  Radio,
} from 'lucide-react'

// Blood Groups supported
const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] as const
type BloodGroup = typeof BLOOD_GROUPS[number]

type City = 'Delhi' | 'Lucknow'

interface BloodBankItem {
  id: string
  name: string
  city: City
  locality: string
  distanceKm: number
  bloodGroup: BloodGroup
  reportedUnits: number
  freshness: string
  source: string
  verificationStatus: 'Simulated Demo Data (Unverified)'
  contactPhone: string
}

const DEMO_BANKS: BloodBankItem[] = [
  {
    id: 'delhi-1',
    name: 'AIIMS Blood Transfusion Services',
    city: 'Delhi',
    locality: 'Ansari Nagar, New Delhi',
    distanceKm: 3.2,
    bloodGroup: 'O+',
    reportedUnits: 8,
    freshness: 'Sample timestamp: 24m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 11 2658 8500',
  },
  {
    id: 'delhi-2',
    name: 'Safdarjung Hospital Regional Blood Center',
    city: 'Delhi',
    locality: 'Ring Road, New Delhi',
    distanceKm: 4.1,
    bloodGroup: 'B+',
    reportedUnits: 5,
    freshness: 'Sample timestamp: 1h ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 11 2616 5060',
  },
  {
    id: 'delhi-3',
    name: 'Red Cross Blood Bank Delhi',
    city: 'Delhi',
    locality: 'Golf Links, New Delhi',
    distanceKm: 5.7,
    bloodGroup: 'AB+',
    reportedUnits: 3,
    freshness: 'Sample timestamp: 35m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 11 2371 1551',
  },
  {
    id: 'delhi-4',
    name: 'Ram Manohar Lohia Hospital Blood Bank',
    city: 'Delhi',
    locality: 'Connaught Place, New Delhi',
    distanceKm: 6.5,
    bloodGroup: 'A+',
    reportedUnits: 6,
    freshness: 'Sample timestamp: 48m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 11 2340 4000',
  },
  {
    id: 'lucknow-1',
    name: 'KGMU Shatabdi Blood Bank & Transfusion',
    city: 'Lucknow',
    locality: 'Chowk, Lucknow',
    distanceKm: 2.8,
    bloodGroup: 'O+',
    reportedUnits: 7,
    freshness: 'Sample timestamp: 18m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 522 225 7540',
  },
  {
    id: 'lucknow-2',
    name: 'SGPGI Transfusion Medicine Department',
    city: 'Lucknow',
    locality: 'Raebareli Road, Lucknow',
    distanceKm: 8.4,
    bloodGroup: 'B-',
    reportedUnits: 4,
    freshness: 'Sample timestamp: 50m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 522 266 8004',
  },
  {
    id: 'lucknow-3',
    name: 'Dr. Ram Manohar Lohia Institute Blood Center',
    city: 'Lucknow',
    locality: 'Gomti Nagar, Lucknow',
    distanceKm: 5.2,
    bloodGroup: 'A+',
    reportedUnits: 6,
    freshness: 'Sample timestamp: 32m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 522 669 2000',
  },
  {
    id: 'lucknow-4',
    name: 'Balrampur Hospital Blood Bank',
    city: 'Lucknow',
    locality: 'Kaiserbagh, Lucknow',
    distanceKm: 3.9,
    bloodGroup: 'O-',
    reportedUnits: 2,
    freshness: 'Sample timestamp: 15m ago',
    source: 'Synthetic Demo Record',
    verificationStatus: 'Simulated Demo Data (Unverified)',
    contactPhone: '+91 522 222 2234',
  },
]

export default function App() {
  // Theme State
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('raktsetu-theme')
      if (stored === 'light' || stored === 'dark') return stored
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return 'light'
  })

  // Apply Theme class to <html>
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('raktsetu-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'))
  }

  // Search filter states
  const [selectedCity, setSelectedCity] = useState<City>('Delhi')
  const [selectedGroup, setSelectedGroup] = useState<BloodGroup>('O+')
  const [showConsentDonorAlert, setShowConsentDonorAlert] = useState(true)

  // Filtered demo items
  const filteredBanks = DEMO_BANKS.filter(
    bank => bank.city === selectedCity && (bank.bloodGroup === selectedGroup || bank.reportedUnits > 0)
  )

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] transition-colors duration-200 font-sans selection:bg-[#B91C35]/15 selection:text-[#B91C35]">
      {/* Top Banner: Ethical Disclaimer */}
      <div className="bg-[#B91C35] text-white text-xs py-1.5 px-4 text-center font-medium tracking-wide flex items-center justify-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
        <span>
          <strong>Hackathon Prototype Notice:</strong> All data shown is synthetic demonstration data. Live hospital feeds, Telegram notifications, and AI integrations are in progress and not connected.
        </span>
      </div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-30 border-b border-[var(--border-main)] bg-[var(--bg-surface)]/85 backdrop-blur-md transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
          {/* Logo & Tagline */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#B91C35] to-[#8C1024] text-white shadow-md shadow-[#B91C35]/20">
              <Droplet className="w-5 h-5 fill-white text-white" />
              <span className="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-amber-500 rounded-full border-2 border-[var(--bg-surface)]" title="Prototype Mode" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  RaktSetu
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] border border-[#B91C35]/20">
                  रक्तसेतु
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] hidden sm:block">
                Bridging the gap between need and help.
              </p>
            </div>
          </div>

          {/* Center Navigation Links (Informational) */}
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-[var(--text-secondary)]">
            <a href="#discovery" className="hover:text-[#B91C35] transition-colors">
              Simulated Discovery
            </a>
            <a href="#safeguards" className="hover:text-[#B91C35] transition-colors">
              Safeguards & Disclaimers
            </a>
            <a href="#pillars" className="hover:text-[#B91C35] transition-colors">
              Architecture Plan
            </a>
            <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              <MapPin className="w-3 h-3 text-[#B91C35]" />
              Target Cities: Delhi & Lucknow
            </span>
          </nav>

          {/* Right Controls: Theme Toggle & Status */}
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
              className="p-2.5 rounded-xl border border-[var(--border-main)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:border-[#B91C35]/50 transition-all focus:outline-none focus:ring-2 focus:ring-[#B91C35]/50 cursor-pointer"
            >
              {theme === 'light' ? (
                <Moon className="w-4 h-4 text-slate-700" />
              ) : (
                <Sun className="w-4 h-4 text-amber-400" />
              )}
            </button>

            <a
              href="https://github.com/rayyan-sidd/RaktSetu"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-[#142433] dark:bg-white text-white dark:text-[#142433] hover:opacity-90 transition-opacity"
            >
              <span>GitHub</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-16 lg:pt-20 lg:pb-24 border-b border-[var(--border-main)]">
        {/* Soft Background Radial Glows */}
        <div className="absolute top-10 left-1/2 -translate-x-1/2 w-[600px] h-[350px] bg-gradient-to-tr from-[#B91C35]/10 via-[#FFF1F2]/20 dark:via-[#B91C35]/5 to-transparent blur-3xl pointer-events-none -z-10" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left Column: Headlines & Call to Action */}
            <div className="lg:col-span-7 space-y-6 text-left">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#FFF1F2] dark:bg-[#B91C35]/15 border border-[#B91C35]/25 text-[#B91C35] text-xs font-semibold tracking-wide">
                <span className="w-2 h-2 rounded-full bg-[#B91C35] animate-pulse" />
                <span>Open-Source Hackathon Prototype • Delhi & Lucknow Scope</span>
              </div>

              {/* Main Headline */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-[var(--text-primary)] leading-[1.12]">
                Bridging the gap between{' '}
                <span className="bg-gradient-to-r from-[#B91C35] via-[#D32F4C] to-[#E11D48] bg-clip-text text-transparent">
                  urgent need
                </span>{' '}
                and voluntary help.
              </h1>

              {/* Sub-paragraph */}
              <p className="text-base sm:text-lg text-[var(--text-secondary)] leading-relaxed max-w-2xl">
                RaktSetu is an early-stage prototype designing transparent, source-attributed blood discovery for{' '}
                <strong className="text-[var(--text-primary)]">Delhi</strong> and{' '}
                <strong className="text-[var(--text-primary)]">Lucknow</strong>, alongside an architectural model for privacy-preserving voluntary donor coordination.
              </p>

              {/* Scope & Architecture Pillars */}
              <div className="grid grid-cols-3 gap-4 pt-2 max-w-lg border-t border-[var(--border-main)]">
                <div>
                  <div className="text-xl sm:text-2xl font-bold text-[var(--text-primary)]">Delhi & LKO</div>
                  <div className="text-xs text-[var(--text-secondary)]">Target Initial Scope</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-bold text-[#B91C35]">8 Groups</div>
                  <div className="text-xs text-[var(--text-secondary)]">ABO & Rh Tracked</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-bold text-amber-600 dark:text-amber-400">Opt-In</div>
                  <div className="text-xs text-[var(--text-secondary)]">Mandatory Consent</div>
                </div>
              </div>
            </div>

            {/* Right Column: 3D Blood-Drop & Connected Network Visual */}
            <div className="lg:col-span-5 flex justify-center relative">
              <div className="relative w-72 h-72 sm:w-88 sm:h-88 flex items-center justify-center">
                {/* Outer Glow Halo */}
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-[#B91C35]/25 to-rose-300/10 dark:from-[#B91C35]/35 dark:to-transparent blur-2xl animate-pulse-glow" />

                {/* Orbiting SVG Network Rings */}
                <svg
                  className="absolute inset-0 w-full h-full text-slate-300 dark:text-slate-700 pointer-events-none"
                  viewBox="0 0 350 350"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <circle cx="175" cy="175" r="140" stroke="currentColor" strokeWidth="1" strokeDasharray="4 6" opacity="0.6" />
                  <circle cx="175" cy="175" r="105" stroke="currentColor" strokeWidth="1.2" opacity="0.4" />
                  <circle cx="175" cy="175" r="70" stroke="currentColor" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />

                  {/* Network Ray Lines */}
                  <line x1="175" y1="175" x2="310" y2="120" stroke="#B91C35" strokeWidth="1.5" strokeOpacity="0.4" />
                  <line x1="175" y1="175" x2="60" y2="240" stroke="#B91C35" strokeWidth="1.5" strokeOpacity="0.4" />
                  <line x1="175" y1="175" x2="260" y2="270" stroke="#15803D" strokeWidth="1.5" strokeOpacity="0.4" />
                </svg>

                {/* Central 3D Crimson Teardrop Structure */}
                <div className="relative z-10 w-44 h-44 sm:w-52 sm:h-52 rounded-full flex items-center justify-center animate-float-slow">
                  {/* Outer Depth Glass Ring */}
                  <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-[#8C1024] via-[#B91C35] to-[#E11D48] shadow-2xl shadow-[#B91C35]/40 flex items-center justify-center p-2">
                    {/* Inner Refraction Core */}
                    <div className="w-full h-full rounded-full bg-gradient-to-b from-[#B91C35] via-[#8C1024] to-[#5C0A17] flex flex-col items-center justify-center relative overflow-hidden border border-white/20">
                      {/* Specular Highlight Sheen */}
                      <div className="absolute top-2 left-6 w-16 h-8 bg-white/30 rounded-full blur-[2px] -rotate-35 pointer-events-none" />
                      <div className="absolute bottom-4 right-6 w-10 h-4 bg-rose-400/20 rounded-full blur-[4px] pointer-events-none" />

                      {/* Teardrop Icon Symbol */}
                      <Droplet className="w-16 h-16 text-white drop-shadow-md fill-white/90" />
                      <span className="text-[10px] font-bold tracking-widest uppercase text-white/90 mt-1">
                        RaktSetu
                      </span>
                    </div>
                  </div>
                </div>

                {/* Floating Telemetry Badge 1: Mock Data Indicator */}
                <div className="absolute -top-2 right-4 z-20 bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-xl px-3 py-2 shadow-lg backdrop-blur-md flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                  <div className="text-left">
                    <p className="text-[10px] font-bold text-[var(--text-primary)]">Demo Data Only</p>
                    <p className="text-[9px] text-amber-600 dark:text-amber-400 font-medium">Not Real Blood Stock</p>
                  </div>
                </div>

                {/* Floating Telemetry Badge 2: Integration Status */}
                <div className="absolute -bottom-3 left-4 z-20 bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-xl px-3 py-2 shadow-lg backdrop-blur-md flex items-center gap-2">
                  <Radio className="w-3.5 h-3.5 text-[#B91C35]" />
                  <div className="text-left">
                    <p className="text-[10px] font-bold text-[var(--text-primary)]">External Sync</p>
                    <p className="text-[9px] text-[var(--text-secondary)]">Disconnected in Prototype</p>
                  </div>
                </div>

                {/* Floating Telemetry Badge 3: Privacy Relay Specification */}
                <div className="absolute top-1/2 -left-6 -translate-y-1/2 z-20 bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-xl px-3 py-2 shadow-lg backdrop-blur-md hidden sm:flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <div className="text-left">
                    <p className="text-[10px] font-bold text-[var(--text-primary)]">Zero Phone Leaks</p>
                    <p className="text-[9px] text-emerald-600 dark:text-emerald-400 font-medium">Planned Telegram Relay</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Discovery Interactive Widget */}
      <section id="discovery" className="py-12 lg:py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-8 border-b border-[var(--border-main)]">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#B91C35]">
                <Search className="w-3.5 h-3.5" />
                <span>Simulated Discovery Console</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)] mt-1">
                Explore Sample Blood Availability Records
              </h2>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Filter mock records by target city and ABO/Rh group to preview how source attribution, timestamps, and verification badges will be displayed.
              </p>
            </div>

            {/* City Selector Pills */}
            <div className="flex items-center gap-2 bg-[var(--bg-elevated)] p-1.5 rounded-xl border border-[var(--border-main)]">
              {(['Delhi', 'Lucknow'] as City[]).map(city => (
                <button
                  key={city}
                  onClick={() => setSelectedCity(city)}
                  className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    selectedCity === city
                      ? 'bg-[#B91C35] text-white shadow-sm'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {city} (Scope)
                </button>
              ))}
            </div>
          </div>

          {/* Blood Group Selector Chips */}
          <div className="pt-6">
            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
              Select Blood Group:
            </label>
            <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 sm:gap-3">
              {BLOOD_GROUPS.map(group => {
                const isSelected = selectedGroup === group
                return (
                  <button
                    key={group}
                    onClick={() => setSelectedGroup(group)}
                    className={`py-2.5 px-3 rounded-xl font-bold text-sm border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-[#B91C35] text-white border-[#B91C35] shadow-md shadow-[#B91C35]/25 scale-102'
                        : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border-[var(--border-main)] hover:border-[#B91C35]/40'
                    }`}
                  >
                    {group}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Voluntary Donor Alert Checkbox (Simulated) */}
          <div className="mt-6 pt-4 border-t border-[var(--border-main)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <label className="flex items-center gap-2.5 cursor-pointer text-xs sm:text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={showConsentDonorAlert}
                onChange={e => setShowConsentDonorAlert(e.target.checked)}
                className="w-4 h-4 rounded text-[#B91C35] focus:ring-[#B91C35] accent-[#B91C35]"
              />
              <span>
                Simulate voluntary donor notification matching for <strong>{selectedCity}</strong> (Mock preview — live Telegram notifications are not connected)
              </span>
            </label>

            <div className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-amber-500" />
              <span>All records below are synthetic demo data • External APIs not connected</span>
            </div>
          </div>
        </div>

        {/* Results Grid */}
        <div className="mt-8 space-y-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <span>Sample records for {selectedCity} ({selectedGroup})</span>
              <span className="text-xs font-normal text-[var(--text-secondary)]">
                ({filteredBanks.length} demo items)
              </span>
            </h3>
            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" />
              Simulated demonstration records only
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredBanks.map(bank => (
              <div
                key={bank.id}
                className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-xl p-5 hover:border-[#B91C35]/40 transition-all shadow-sm hover:shadow-md flex flex-col justify-between"
              >
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="font-bold text-base text-[var(--text-primary)] leading-snug">
                        {bank.name}
                      </h4>
                      <p className="text-xs text-[var(--text-secondary)] flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3 text-[#B91C35]" />
                        {bank.locality} • ~{bank.distanceKm} km (Sample distance)
                      </p>
                    </div>

                    {/* Blood Group Pill */}
                    <span className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] font-extrabold text-sm border border-[#B91C35]/30">
                      {bank.bloodGroup}
                    </span>
                  </div>

                  {/* Stock & Freshness Data Strip */}
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[var(--border-main)]">
                    <div>
                      <span className="text-[11px] text-[var(--text-secondary)] block">
                        Sample Reported Units:
                      </span>
                      <span className="text-sm font-bold text-[var(--text-primary)]">
                        {bank.reportedUnits} units (Demo)
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] text-[var(--text-secondary)] block">
                        Timestamp Display:
                      </span>
                      <span className="text-xs font-medium text-[var(--text-primary)] flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {bank.freshness}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Footer Tag Strip */}
                <div className="mt-4 pt-3 border-t border-[var(--border-main)] flex items-center justify-between text-xs">
                  <span className="text-[11px] text-[var(--text-secondary)] bg-[var(--bg-elevated)] px-2 py-0.5 rounded border border-[var(--border-main)]">
                    {bank.source}
                  </span>
                  <span className="text-[11px] font-medium text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50 px-2 py-0.5 rounded flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {bank.verificationStatus}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3 Core Architecture Pillars (Design Specifications) */}
      <section id="pillars" className="py-12 lg:py-16 border-t border-[var(--border-main)] bg-[var(--bg-elevated)]/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <span className="text-xs font-bold uppercase tracking-wider text-[#B91C35]">
              System Architecture
            </span>
            <h2 className="text-3xl font-extrabold text-[var(--text-primary)] mt-1">
              Planned RaktSetu Workflow
            </h2>
            <p className="text-sm text-[var(--text-secondary)] mt-2">
              Architecture specifications for transparent discovery, donor consent, and human verification.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Pillar 1 */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 shadow-sm hover:border-[#B91C35]/50 transition-all flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-xl bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] flex items-center justify-center font-bold mb-4">
                  <Database className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                  1. Source-Attributed Stock (Planned)
                </h3>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  Designed to ingest reported data feeds with strict freshness timestamps, ensuring caregivers and patients see exactly when and where data was reported before contacting facilities.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border-main)] text-xs text-[#B91C35] font-semibold flex items-center gap-1">
                <span>Planned Ingestion Engine</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Pillar 2 */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 shadow-sm hover:border-[#B91C35]/50 transition-all flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold mb-4">
                  <HeartHandshake className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                  2. Consented Donor Relay (Planned)
                </h3>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  In development: a privacy-preserving notification workflow via Telegram Bot API so opted-in donors receive alerts without ever revealing personal contact numbers publicly.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border-main)] text-xs text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                <span>Architecture Specification</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Pillar 3 */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 shadow-sm hover:border-[#B91C35]/50 transition-all flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold mb-4">
                  <Bot className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                  3. Gemma 4 AI Assistant (Planned)
                </h3>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  Planned integration: lightweight local Gemma 4 / rule-based fallback to extract structured location and urgency parameters, strictly validated by deterministic backend code.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border-main)] text-xs text-indigo-600 dark:text-indigo-400 font-semibold flex items-center gap-1">
                <span>Model & Fallback Design</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Ethical Safeguards & Medical Disclaimer Section */}
      <section id="safeguards" className="py-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/20 p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="space-y-3">
              <h3 className="text-base sm:text-lg font-bold text-amber-950 dark:text-amber-200">
                Ethical Safeguards & Emergency Medical Notice
              </h3>
              <p className="text-xs sm:text-sm text-amber-900/90 dark:text-amber-300/90 leading-relaxed">
                RaktSetu is a student/hackathon technical prototype built to showcase transparent data aggregation and privacy-first coordination. It is <strong>not a certified emergency medical service</strong>.
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-amber-900/80 dark:text-amber-300/80 pt-1">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Never guarantees physical blood inventory without direct bank confirmation.</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>External hospital feeds, scraping tools, and Telegram bots are disconnected in this UI demo.</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Donor participation is strictly opt-in with revocable voluntary consent.</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Always call official emergency services (112 / 108) for acute trauma response.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border-main)] bg-[var(--bg-surface)] py-10 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-[#B91C35] text-white flex items-center justify-center font-bold text-xs">
                R
              </div>
              <span className="font-bold text-sm text-[var(--text-primary)]">
                RaktSetu (रक्तसेतु)
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                • Open-Source Hackathon Prototype
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)]">
              <span>Stack: FastAPI + React + Vite + Tailwind v4</span>
              <span>•</span>
              <span>Target Scope: Delhi & Lucknow</span>
              <span>•</span>
              <a
                href="https://github.com/rayyan-sidd/RaktSetu"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#B91C35] underline"
              >
                GitHub Repository
              </a>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-[var(--border-main)] text-center text-[11px] text-[var(--text-secondary)]">
            © 2026 RaktSetu Maintainers and Contributors. Licensed under the MIT License.
          </div>
        </div>
      </footer>
    </div>
  )
}
