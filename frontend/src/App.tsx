import { useState, useEffect, lazy, Suspense } from 'react'
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
  Sparkles,
} from 'lucide-react'

const HeroDroplet = lazy(() => import('./components/HeroDroplet'))

function DropletFallback() {
  return (
    <div className="w-full h-[360px] sm:h-[440px] lg:h-[480px] flex items-center justify-center">
      <div className="w-40 h-40 sm:w-48 sm:h-48 rounded-full bg-gradient-to-tr from-[#8C1024] via-[#B91C35] to-[#E11D48] shadow-xl shadow-[#B91C35]/25 flex items-center justify-center animate-pulse">
        <Droplet className="w-14 h-14 text-white/90 fill-white/80" />
      </div>
    </div>
  )
}

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
      {/* Top Banner: Restrained, Slim Prototype Notice */}
      <div className="bg-[#142433] text-stone-300 text-[11px] py-1 px-4 text-center font-medium tracking-wide flex items-center justify-center gap-2 border-b border-[#23394E]">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
        <span>
          <strong>Prototype Notice:</strong> Demonstrating planned blood discovery and coordination. All stock data is simulated; live external integrations are not connected.
        </span>
      </div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-30 border-b border-[var(--border-main)] bg-[var(--bg-surface)]/85 backdrop-blur-md transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
          {/* Logo & Tagline */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#B91C35] to-[#8C1024] text-white shadow-md shadow-[#B91C35]/25">
              <Droplet className="w-5 h-5 fill-white text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-extrabold tracking-tight text-[var(--text-primary)]">
                  RaktSetu
                </span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#FFF1F2] dark:bg-[#B91C35]/25 text-[#B91C35] border border-[#B91C35]/25">
                  रक्तसेतु
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)] font-medium hidden sm:block">
                Bridging the gap between need and help.
              </p>
            </div>
          </div>

          {/* Center Navigation Links (Editorial Minimalist) */}
          <nav className="hidden md:flex items-center gap-7 text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
            <a href="#discovery" className="hover:text-[#B91C35] transition-colors">
              Discovery Console
            </a>
            <a href="#pillars" className="hover:text-[#B91C35] transition-colors">
              Architecture Plan
            </a>
            <a href="#safeguards" className="hover:text-[#B91C35] transition-colors">
              Safety & Ethics
            </a>
            <span className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 normal-case font-medium">
              <MapPin className="w-3 h-3 text-[#B91C35]" />
              Delhi & Lucknow
            </span>
          </nav>

          {/* Right Controls: Theme Toggle & GitHub */}
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
              className="p-2 rounded-xl border border-[var(--border-main)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:border-[#B91C35]/50 transition-all focus:outline-none focus:ring-2 focus:ring-[#B91C35]/50 cursor-pointer"
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
              className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold rounded-xl bg-[#142433] dark:bg-white text-white dark:text-[#142433] hover:opacity-90 transition-opacity shadow-sm"
            >
              <span>GitHub</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section — Art-Directed Editorial Layout */}
      <section className="relative overflow-hidden pt-8 pb-14 lg:pt-14 lg:pb-20 border-b border-[var(--border-main)]">
        {/* Ambient Soft Blush Radial Lighting */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[750px] h-[400px] bg-gradient-to-tr from-[#B91C35]/10 via-[#FFF1F2]/20 dark:via-[#B91C35]/6 to-transparent blur-3xl pointer-events-none -z-10" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left Column: Headline & Elevated Discovery Console */}
            <div className="lg:col-span-7 space-y-6 text-left">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#FFF1F2] dark:bg-[#B91C35]/20 border border-[#B91C35]/25 text-[#B91C35] text-xs font-bold tracking-wide">
                <span className="w-1.5 h-1.5 rounded-full bg-[#B91C35] animate-pulse" />
                <span>RaktSetu Prototype • Delhi & Lucknow Initiative</span>
              </div>

              {/* Headline in Three Deliberate Lines */}
              <h1 className="text-4xl sm:text-5xl lg:text-[3.65rem] font-extrabold tracking-[-0.035em] text-[var(--text-primary)] leading-[1.06]">
                Bridging the gap <br className="hidden sm:inline" />
                <span className="bg-gradient-to-r from-[#B91C35] via-[#D32F4C] to-[#E11D48] bg-clip-text text-transparent">
                  between urgent need
                </span> <br className="hidden sm:inline" />
                and voluntary help.
              </h1>

              {/* Subtitle */}
              <p className="text-sm sm:text-base text-[var(--text-secondary)] leading-relaxed max-w-xl font-normal">
                An open-source coordination platform designing transparent, source-attributed blood discovery for Delhi and Lucknow, paired with an opt-in voluntary donor notification model.
              </p>

              {/* Elevated Discovery Console in Initial Viewport */}
              <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-5 shadow-sm space-y-3.5 max-w-xl">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#B91C35]">
                    <Search className="w-3.5 h-3.5" />
                    <span>Quick Discovery</span>
                  </div>

                  {/* City Selector Pills */}
                  <div className="flex items-center gap-1 bg-[var(--bg-elevated)] p-1 rounded-xl border border-[var(--border-main)]">
                    {(['Delhi', 'Lucknow'] as City[]).map(city => (
                      <button
                        key={city}
                        onClick={() => setSelectedCity(city)}
                        className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                          selectedCity === city
                            ? 'bg-[#B91C35] text-white shadow-sm'
                            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                        }`}
                      >
                        {city}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Blood Group Chips */}
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">
                    Select Blood Group:
                  </label>
                  <div className="grid grid-cols-4 sm:grid-cols-8 gap-1.5">
                    {BLOOD_GROUPS.map(group => {
                      const isSelected = selectedGroup === group
                      return (
                        <button
                          key={group}
                          onClick={() => setSelectedGroup(group)}
                          className={`py-1.5 px-2 rounded-xl font-bold text-xs border transition-all cursor-pointer ${
                            isSelected
                              ? 'bg-[#B91C35] text-white border-[#B91C35] shadow-sm shadow-[#B91C35]/30 scale-102'
                              : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border-[var(--border-main)] hover:border-[#B91C35]/40'
                          }`}
                        >
                          {group}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <a
                  href="#discovery"
                  className="w-full py-2.5 rounded-xl bg-[#B91C35] hover:bg-[#A0162D] text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors shadow-md shadow-[#B91C35]/25"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Inspect Sample Records for {selectedCity} ({selectedGroup})</span>
                </a>
              </div>

              {/* Hierarchy Metric Cards */}
              <div className="grid grid-cols-3 gap-6 pt-2 max-w-xl border-t border-[var(--border-main)]">
                <div>
                  <div className="text-xl font-extrabold text-[var(--text-primary)] tracking-tight">Delhi & LKO</div>
                  <div className="text-xs text-[var(--text-secondary)] font-medium">Initial Scope</div>
                </div>
                <div>
                  <div className="text-xl font-extrabold text-[#B91C35] tracking-tight">8 Groups</div>
                  <div className="text-xs text-[var(--text-secondary)] font-medium">ABO / Rh Tracked</div>
                </div>
                <div>
                  <div className="text-xl font-extrabold text-amber-600 dark:text-amber-400 tracking-tight">Opt-In</div>
                  <div className="text-xs text-[var(--text-secondary)] font-medium">Planned Consent</div>
                </div>
              </div>
            </div>

            {/* Right Column: 3D Sculptural Ruby Droplet with Balanced Floating Cards */}
            <div className="lg:col-span-5 flex justify-center relative">
              <div className="relative w-full max-w-[440px] flex items-center justify-center">
                {/* 3D Canvas Scene with Suspense */}
                <Suspense fallback={<DropletFallback />}>
                  <HeroDroplet isDark={theme === 'dark'} />
                </Suspense>

                {/* Floating Telemetry Card 1 (Top-Right: Anchored without overlap) */}
                <div className="absolute top-4 right-1 sm:right-3 z-20 bg-[var(--bg-surface)]/92 border border-[var(--border-main)] rounded-2xl p-3 shadow-lg backdrop-blur-md flex items-center gap-2.5 max-w-[200px]">
                  <div className="w-2 h-2 rounded-full bg-amber-500 animate-ping shrink-0" />
                  <div className="text-left">
                    <p className="text-[11px] font-bold text-[var(--text-primary)] leading-tight">Simulated Feed</p>
                    <p className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">Demo Records Only</p>
                  </div>
                </div>

                {/* Floating Telemetry Card 2 (Bottom-Left: Anchored without overlap) */}
                <div className="absolute bottom-4 left-1 sm:left-3 z-20 bg-[var(--bg-surface)]/92 border border-[var(--border-main)] rounded-2xl p-3 shadow-lg backdrop-blur-md flex items-center gap-2.5 max-w-[210px]">
                  <ShieldCheck className="w-4 h-4 text-[#64748B] shrink-0" />
                  <div className="text-left">
                    <p className="text-[11px] font-bold text-[var(--text-primary)] leading-tight">Privacy-First Relay</p>
                    <p className="text-[10px] text-[var(--text-secondary)] font-medium">Planned Telegram Model</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Discovery Interactive Widget */}
      <section id="discovery" className="py-14 lg:py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-3xl p-6 sm:p-10 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-8 border-b border-[var(--border-main)]">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#B91C35]">
                <Search className="w-4 h-4" />
                <span>Simulated Discovery Console</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[var(--text-primary)] mt-1.5 tracking-tight">
                Explore Sample Blood Availability Records
              </h2>
              <p className="text-sm text-[var(--text-secondary)] mt-1.5 max-w-2xl leading-relaxed">
                Filter mock records by target city and ABO/Rh group to preview how source attribution, timestamps, and verification badges will be displayed.
              </p>
            </div>

            {/* City Selector Pills */}
            <div className="flex items-center gap-2 bg-[var(--bg-elevated)] p-1.5 rounded-xl border border-[var(--border-main)]">
              {(['Delhi', 'Lucknow'] as City[]).map(city => (
                <button
                  key={city}
                  onClick={() => setSelectedCity(city)}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
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
            <label className="block text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
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
          <div className="mt-8 pt-5 border-t border-[var(--border-main)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <label className="flex items-center gap-3 cursor-pointer text-xs sm:text-sm text-[var(--text-secondary)]">
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

            <div className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5 font-medium">
              <Database className="w-3.5 h-3.5 text-amber-500" />
              <span>All records below are synthetic demo data • External APIs not connected</span>
            </div>
          </div>
        </div>

        {/* Results Grid */}
        <div className="mt-8 space-y-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span>Sample records for {selectedCity} ({selectedGroup})</span>
              <span className="text-xs font-normal text-[var(--text-secondary)]">
                ({filteredBanks.length} demo items)
              </span>
            </h3>
            <span className="text-xs text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" />
              Simulated demonstration records only
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {filteredBanks.map(bank => (
              <div
                key={bank.id}
                className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 hover:border-[#B91C35]/50 transition-all shadow-sm hover:shadow-md flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="font-extrabold text-base text-[var(--text-primary)] leading-snug">
                        {bank.name}
                      </h4>
                      <p className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5 mt-1 font-medium">
                        <MapPin className="w-3.5 h-3.5 text-[#B91C35]" />
                        {bank.locality} • ~{bank.distanceKm} km (Sample distance)
                      </p>
                    </div>

                    {/* Blood Group Pill */}
                    <span className="inline-flex items-center justify-center w-11 h-11 rounded-xl bg-[#FFF1F2] dark:bg-[#B91C35]/25 text-[#B91C35] font-extrabold text-base border border-[#B91C35]/35 shadow-sm">
                      {bank.bloodGroup}
                    </span>
                  </div>

                  {/* Stock & Freshness Data Strip */}
                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[var(--border-main)]">
                    <div>
                      <span className="text-[11px] font-semibold text-[var(--text-secondary)] block uppercase tracking-wider">
                        Sample Reported Units:
                      </span>
                      <span className="text-sm font-bold text-[var(--text-primary)]">
                        {bank.reportedUnits} units (Demo)
                      </span>
                    </div>
                    <div>
                      <span className="text-[11px] font-semibold text-[var(--text-secondary)] block uppercase tracking-wider">
                        Timestamp Display:
                      </span>
                      <span className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1.5 mt-0.5">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        {bank.freshness}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Footer Tag Strip */}
                <div className="mt-5 pt-3.5 border-t border-[var(--border-main)] flex items-center justify-between text-xs">
                  <span className="text-[11px] font-medium text-[var(--text-secondary)] bg-[var(--bg-elevated)] px-2.5 py-1 rounded-lg border border-[var(--border-main)]">
                    {bank.source}
                  </span>
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50 px-2.5 py-1 rounded-lg flex items-center gap-1">
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
      <section id="pillars" className="py-16 lg:py-24 border-t border-[var(--border-main)] bg-[var(--bg-elevated)]/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <span className="text-xs font-bold uppercase tracking-wider text-[#B91C35]">
              System Architecture
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[var(--text-primary)] mt-1.5 tracking-tight">
              Planned RaktSetu Workflow
            </h2>
            <p className="text-sm sm:text-base text-[var(--text-secondary)] mt-2 leading-relaxed">
              Architecture specifications for transparent discovery, donor consent, and human verification before dispatch.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Pillar 1 */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-7 shadow-sm hover:border-[#B91C35]/50 transition-all flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-xl bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] flex items-center justify-center font-bold mb-5">
                  <Database className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                  1. Source-Attributed Stock (Planned)
                </h3>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  Designed to ingest reported data feeds with strict freshness timestamps, ensuring caregivers and patients see exactly when and where data was reported before contacting facilities.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border-main)] text-xs text-[#B91C35] font-bold flex items-center gap-1">
                <span>Planned Ingestion Engine</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Pillar 2 */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-7 shadow-sm hover:border-[#B91C35]/50 transition-all flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 text-[#142433] dark:text-slate-200 flex items-center justify-center font-bold mb-5">
                  <HeartHandshake className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                  2. Consented Donor Relay (Planned)
                </h3>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  In development: a privacy-preserving notification workflow via Telegram Bot API so opted-in donors receive alerts without ever revealing personal contact numbers publicly.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border-main)] text-xs text-[#64748B] dark:text-slate-400 font-bold flex items-center gap-1">
                <span>Architecture Specification</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Pillar 3 */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-7 shadow-sm hover:border-[#B91C35]/50 transition-all flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 text-[#142433] dark:text-slate-200 flex items-center justify-center font-bold mb-5">
                  <Bot className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                  3. Gemma 4 AI Assistant (Planned)
                </h3>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  Planned integration: lightweight local Gemma 4 / rule-based fallback to extract structured location and urgency parameters, strictly validated by deterministic backend code.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-[var(--border-main)] text-xs text-[#64748B] dark:text-slate-400 font-bold flex items-center gap-1">
                <span>Model & Fallback Design</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Ethical Safeguards & Medical Disclaimer Section */}
      <section id="safeguards" className="py-14 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/20 p-7 sm:p-10">
          <div className="flex flex-col sm:flex-row items-start gap-5">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="space-y-3.5">
              <h3 className="text-lg sm:text-xl font-extrabold text-amber-950 dark:text-amber-200 tracking-tight">
                Ethical Safeguards & Emergency Medical Notice
              </h3>
              <p className="text-xs sm:text-sm text-amber-900/90 dark:text-amber-300/90 leading-relaxed">
                RaktSetu is a student/hackathon technical prototype built to showcase transparent data aggregation and privacy-first coordination. It is <strong>not a certified emergency medical service</strong>.
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-amber-900/80 dark:text-amber-300/80 pt-1">
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Never guarantees physical blood inventory without direct bank confirmation.</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>External hospital feeds, scraping tools, and Telegram bots are disconnected in this UI demo.</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Donor participation is strictly opt-in with revocable voluntary consent.</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Always call official emergency services (112 / 108) for acute trauma response.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border-main)] bg-[var(--bg-surface)] py-12 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#B91C35] text-white flex items-center justify-center font-bold text-xs">
                R
              </div>
              <span className="font-extrabold text-base text-[var(--text-primary)]">
                RaktSetu (रक्तसेतु)
              </span>
              <span className="text-xs text-[var(--text-secondary)] font-medium">
                • Open-Source Hackathon Prototype
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)] font-medium">
              <span>Stack: FastAPI + React + Three.js + Tailwind v4</span>
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

          <div className="mt-8 pt-6 border-t border-[var(--border-main)] text-center text-xs text-[var(--text-secondary)]">
            © 2026 RaktSetu Maintainers and Contributors. Licensed under the MIT License.
          </div>
        </div>
      </footer>
    </div>
  )
}
