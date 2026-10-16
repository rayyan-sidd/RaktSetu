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
  Database,
  Sparkles,
  RefreshCw,
  AlertCircle,
  FilterX,
  Users,
  Info,
  Menu,
  X,
  Activity,
  ArrowRight,
} from 'lucide-react'
import {
  fetchBloodBanks,
  formatTimestamp,
  getReportFreshnessInfo,
  filterAndSortBloodBanks,
  getTelegramBotUrl,
  type BloodBank,
} from './services/api'

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
type CityFilter = 'All' | City
type GroupFilter = 'All' | BloodGroup

// Sample donor profiles for presentation preview (clearly labeled as demo mockups)
const SAMPLE_DONOR_PROFILES = [
  {
    alias: '@delhi_donor_o',
    group: 'O+',
    city: 'Delhi',
    status: 'Standby Volunteer',
    badge: 'Sample Profile',
    notes: 'Voluntary ABO/Rh standby demonstration',
  },
  {
    alias: '@lucknow_aid',
    group: 'B+',
    city: 'Lucknow',
    status: 'Standby Volunteer',
    badge: 'Sample Profile',
    notes: 'Community voluntary emergency standby',
  },
  {
    alias: '@delhi_care_a',
    group: 'A-',
    city: 'Delhi',
    status: 'Standby Volunteer',
    badge: 'Sample Profile',
    notes: 'Rare-group voluntary readiness demonstration',
  },
  {
    alias: '@up_plasma_vol',
    group: 'AB+',
    city: 'Lucknow',
    status: 'Standby Volunteer',
    badge: 'Sample Profile',
    notes: 'Component readiness demonstration mockup',
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

  // Navigation & Modal State
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false)
  const [showTelegramModal, setShowTelegramModal] = useState<boolean>(false)

  // Search filter states
  const [selectedCity, setSelectedCity] = useState<CityFilter>('Delhi')
  const [selectedGroup, setSelectedGroup] = useState<GroupFilter>('O+')
  const [includeDemo, setIncludeDemo] = useState<boolean>(false)

  // Interactive "Become a Donor" prototype state
  const [donorGroup, setDonorGroup] = useState<BloodGroup>('O+')
  const [donorCity, setDonorCity] = useState<City>('Delhi')
  const [donorConsent, setDonorConsent] = useState<boolean>(false)
  const [donorSubmitted, setDonorSubmitted] = useState<boolean>(false)
  const [donorError, setDonorError] = useState<string | null>(null)

  // API State
  const [banks, setBanks] = useState<BloodBank[]>([])
  const [dataNotice, setDataNotice] = useState<string>('')
  const [dataTimestamp, setDataTimestamp] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [retryTrigger, setRetryTrigger] = useState<number>(0)

  // Resolve Telegram Bot link
  const telegramBotUrl = getTelegramBotUrl()

  // Filter and sort visible banks: real data first, demo excluded by default (OFF)
  const visibleBanks = filterAndSortBloodBanks(banks, includeDemo)
  const visibleCount = visibleBanks.length

  const hasDemo = visibleBanks.some(b => b.source_type === 'demo')
  const hasExternal = visibleBanks.some(b => b.source_type === 'external_source')

  // Fetch actual discovery records from backend API
  useEffect(() => {
    const controller = new AbortController()
    setIsLoading(true)
    setError(null)

    fetchBloodBanks(
      selectedCity === 'All' ? null : selectedCity,
      selectedGroup === 'All' ? null : selectedGroup,
      controller.signal
    )
      .then(data => {
        setBanks(data.items)
        setDataNotice(data.data_notice)
        setDataTimestamp(data.data_timestamp || null)
        setIsLoading(false)
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(
            err.message ||
              'Unable to connect to blood bank discovery API. Ensure the backend server is running.'
          )
          setIsLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [selectedCity, selectedGroup, retryTrigger])

  const handleRetry = () => {
    setRetryTrigger(prev => prev + 1)
  }

  const handleResetFilters = () => {
    setSelectedCity('All')
    setSelectedGroup('All')
    setIncludeDemo(false)
  }

  const handleDonorSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!donorConsent) {
      setDonorError('Please confirm the opt-in consent box to participate in the demonstration.')
      return
    }
    setDonorError(null)
    setDonorSubmitted(true)
  }

  const handleOpenTelegram = (e: React.MouseEvent) => {
    if (!telegramBotUrl) {
      e.preventDefault()
      setShowTelegramModal(true)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] transition-colors duration-200 font-sans selection:bg-[#B91C35]/15 selection:text-[#B91C35]">
      {/* Top Banner: Restrained, Slim Prototype Notice */}
      <div className="bg-[#142433] text-stone-300 text-[11px] py-1.5 px-4 text-center font-medium tracking-wide flex items-center justify-center gap-2 border-b border-[#23394E]">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
        <span>
          <strong>Prototype Notice:</strong> Demonstrating transparent blood discovery and voluntary donor coordination. Stock counts are source-reported feeds or simulated demo snapshots and do not guarantee physical shelf inventory.
        </span>
      </div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-30 border-b border-[var(--border-main)] bg-[var(--bg-surface)]/85 backdrop-blur-md transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
          {/* Logo & Tagline */}
          <a href="#" className="flex items-center gap-3 group">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#B91C35] to-[#8C1024] text-white shadow-md shadow-[#B91C35]/25 group-hover:scale-105 transition-transform">
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
          </a>

          {/* Visitor-Facing Navigation Links */}
          <nav className="hidden lg:flex items-center gap-7 text-xs font-bold text-[var(--text-secondary)] tracking-wide">
            <a href="#discovery" className="hover:text-[#B91C35] transition-colors">
              Find Blood
            </a>
            <a href="#become-donor" className="hover:text-[#B91C35] transition-colors">
              Become a Donor
            </a>
            <a href="#how-it-works" className="hover:text-[#B91C35] transition-colors">
              How It Works
            </a>
            <a href="#future-scope" className="hover:text-[#B91C35] transition-colors">
              Future Scope
            </a>
          </nav>

          {/* Right Controls: Telegram CTA & Theme Toggle */}
          <div className="flex items-center gap-2.5 sm:gap-3">
            {/* Telegram CTA Button */}
            <a
              href={telegramBotUrl || '#telegram-info'}
              onClick={handleOpenTelegram}
              target={telegramBotUrl ? '_blank' : undefined}
              rel={telegramBotUrl ? 'noopener noreferrer' : undefined}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-xl bg-gradient-to-r from-[#0088cc] to-[#0077b5] text-white hover:opacity-95 transition-all shadow-sm shadow-[#0088cc]/20 cursor-pointer"
            >
              <Bot className="w-4 h-4 shrink-0" />
              <span className="hidden sm:inline">Telegram Bot</span>
            </a>

            {/* Theme Toggle Button */}
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

            {/* Mobile Hamburger Toggle */}
            <button
              onClick={() => setMobileMenuOpen(prev => !prev)}
              aria-label="Toggle Navigation Menu"
              className="lg:hidden p-2 rounded-xl border border-[var(--border-main)] bg-[var(--bg-elevated)] text-[var(--text-primary)]"
            >
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-[var(--border-main)] bg-[var(--bg-surface)] px-4 py-3.5 space-y-2.5">
            <a
              href="#discovery"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 text-sm font-semibold text-[var(--text-primary)] hover:text-[#B91C35]"
            >
              Find Blood
            </a>
            <a
              href="#become-donor"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 text-sm font-semibold text-[var(--text-primary)] hover:text-[#B91C35]"
            >
              Become a Donor
            </a>
            <a
              href="#how-it-works"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 text-sm font-semibold text-[var(--text-primary)] hover:text-[#B91C35]"
            >
              How It Works
            </a>
            <a
              href="#future-scope"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 text-sm font-semibold text-[var(--text-primary)] hover:text-[#B91C35]"
            >
              Future Scope
            </a>
            <a
              href="#trust-safety"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 text-sm font-semibold text-amber-600 dark:text-amber-400"
            >
              Safety & Ethics
            </a>
          </div>
        )}
      </header>

      {/* Hero Section — Headline & Quick Blood Discovery */}
      <section className="relative overflow-hidden pt-8 pb-14 lg:pt-14 lg:pb-20 border-b border-[var(--border-main)]">
        {/* Soft Ambient Radial Glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[750px] h-[400px] bg-gradient-to-tr from-[#B91C35]/10 via-[#FFF1F2]/20 dark:via-[#B91C35]/6 to-transparent blur-3xl pointer-events-none -z-10" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left Column: Headline, Tagline & Quick Search Console */}
            <div className="lg:col-span-7 space-y-6 text-left">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#FFF1F2] dark:bg-[#B91C35]/20 border border-[#B91C35]/25 text-[#B91C35] text-xs font-bold tracking-wide">
                <span className="w-1.5 h-1.5 rounded-full bg-[#B91C35] animate-pulse" />
                <span>RaktSetu • Blood Bank Discovery & Voluntary Donor Platform</span>
              </div>

              {/* Headline & Tagline */}
              <div className="space-y-2">
                <h1 className="text-4xl sm:text-5xl lg:text-[3.65rem] font-extrabold tracking-[-0.035em] text-[var(--text-primary)] leading-[1.08]">
                  Connecting Urgent Need <br className="hidden sm:inline" />
                  <span className="bg-gradient-to-r from-[#B91C35] via-[#D32F4C] to-[#E11D48] bg-clip-text text-transparent">
                    with Verified Help.
                  </span>
                </h1>
                <p className="text-lg sm:text-xl font-semibold text-[#B91C35] tracking-tight">
                  Bridging the gap between need and help.
                </p>
              </div>

              {/* Descriptive Subtitle */}
              <p className="text-sm sm:text-base text-[var(--text-secondary)] leading-relaxed max-w-xl font-normal">
                Discover source-reported hospital blood stocks in Delhi and Lucknow with transparent freshness tracking, and join an opt-in volunteer donor network ready when every minute counts.
              </p>

              {/* Elevated Discovery Console in Hero */}
              <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-5 shadow-sm space-y-3.5 max-w-xl">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#B91C35]">
                    <Search className="w-3.5 h-3.5" />
                    <span>Quick Blood Discovery</span>
                  </div>

                  {/* City Selector Pills */}
                  <div className="flex items-center gap-1 bg-[var(--bg-elevated)] p-1 rounded-xl border border-[var(--border-main)]">
                    {(['All', 'Delhi', 'Lucknow'] as CityFilter[]).map(city => (
                      <button
                        key={city}
                        onClick={() => setSelectedCity(city)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                          selectedCity === city
                            ? 'bg-[#B91C35] text-white shadow-sm'
                            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                        }`}
                      >
                        {city === 'All' ? 'All' : city}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Blood Group Chips */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                      Select Blood Group:
                    </label>
                    {selectedGroup !== 'All' && (
                      <button
                        onClick={() => setSelectedGroup('All')}
                        className="text-[10px] font-semibold text-[#B91C35] hover:underline cursor-pointer"
                      >
                        Show All
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-5 sm:grid-cols-9 gap-1.5">
                    <button
                      onClick={() => setSelectedGroup('All')}
                      className={`py-1.5 px-1.5 rounded-xl font-bold text-xs border transition-all cursor-pointer ${
                        selectedGroup === 'All'
                          ? 'bg-[#B91C35] text-white border-[#B91C35] shadow-sm shadow-[#B91C35]/30'
                          : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border-[var(--border-main)] hover:border-[#B91C35]/40'
                      }`}
                    >
                      All
                    </button>
                    {BLOOD_GROUPS.map(group => {
                      const isSelected = selectedGroup === group
                      return (
                        <button
                          key={group}
                          onClick={() => setSelectedGroup(group)}
                          className={`py-1.5 px-1.5 rounded-xl font-bold text-xs border transition-all cursor-pointer ${
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

                {/* Primary Action Button */}
                <div className="flex flex-col sm:flex-row gap-2.5 pt-1">
                  <a
                    href="#discovery"
                    className="flex-1 py-2.5 rounded-xl bg-[#B91C35] hover:bg-[#A0162D] text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors shadow-md shadow-[#B91C35]/25"
                  >
                    <Search className="w-3.5 h-3.5" />
                    <span>
                      Find Blood for {selectedCity === 'All' ? 'All Cities' : selectedCity} (
                      {selectedGroup === 'All' ? 'All Groups' : selectedGroup})
                    </span>
                  </a>

                  <a
                    href="#become-donor"
                    className="py-2.5 px-4 rounded-xl border border-[#B91C35]/30 hover:border-[#B91C35] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:text-[#B91C35] font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <HeartHandshake className="w-3.5 h-3.5 text-[#B91C35]" />
                    <span>Become a Donor</span>
                  </a>
                </div>
              </div>

              {/* Three Key Telemetry Metrics */}
              <div className="grid grid-cols-3 gap-6 pt-2 max-w-xl border-t border-[var(--border-main)]">
                <div>
                  <div className="text-xl font-extrabold text-[var(--text-primary)] tracking-tight">Delhi & LKO</div>
                  <div className="text-xs text-[var(--text-secondary)] font-medium">Supported Cities</div>
                </div>
                <div>
                  <div className="text-xl font-extrabold text-[#B91C35] tracking-tight">8 Groups</div>
                  <div className="text-xs text-[var(--text-secondary)] font-medium">ABO / Rh Filtered</div>
                </div>
                <div>
                  <div className="text-xl font-extrabold text-blue-600 dark:text-blue-400 tracking-tight">e-RaktKosh</div>
                  <div className="text-xs text-[var(--text-secondary)] font-medium">Official Feed Ingested</div>
                </div>
              </div>
            </div>

            {/* Right Column: 3D Sculptural Droplet Canvas */}
            <div className="lg:col-span-5 flex justify-center relative">
              <div className="relative w-full max-w-[440px] flex items-center justify-center">
                <Suspense fallback={<DropletFallback />}>
                  <HeroDroplet isDark={theme === 'dark'} />
                </Suspense>

                {/* Floating Status Badge 1: Real Source Feed */}
                <div className="absolute top-4 right-1 sm:right-3 z-20 bg-[var(--bg-surface)]/92 border border-[var(--border-main)] rounded-2xl p-3 shadow-lg backdrop-blur-md flex items-center gap-2.5 max-w-[210px]">
                  <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse shrink-0" />
                  <div className="text-left">
                    <p className="text-[11px] font-bold text-[var(--text-primary)] leading-tight">Live Ingestion</p>
                    <p className="text-[10px] text-blue-600 dark:text-blue-400 font-medium">Official e-RaktKosh Feed</p>
                  </div>
                </div>

                {/* Floating Status Badge 2: Telegram Bot Integration */}
                <div className="absolute bottom-4 left-1 sm:left-3 z-20 bg-[var(--bg-surface)]/92 border border-[var(--border-main)] rounded-2xl p-3 shadow-lg backdrop-blur-md flex items-center gap-2.5 max-w-[210px]">
                  <Bot className="w-4 h-4 text-[#0088cc] shrink-0" />
                  <div className="text-left">
                    <p className="text-[11px] font-bold text-[var(--text-primary)] leading-tight">Telegram Assistant</p>
                    <p className="text-[10px] text-[var(--text-secondary)] font-medium">Instant /find Chat Access</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Discovery Section — Search Results & Filters */}
      <section id="discovery" className="py-14 lg:py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-3xl p-6 sm:p-10 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-8 border-b border-[var(--border-main)]">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#B91C35]">
                <Search className="w-4 h-4" />
                <span>Hospital Stock Discovery</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-[var(--text-primary)] mt-1.5 tracking-tight">
                Reported Blood Bank Availability
              </h2>
              <p className="text-sm text-[var(--text-secondary)] mt-1.5 max-w-2xl leading-relaxed">
                Filter official e-RaktKosh hospital records by city and blood group. Always call the blood bank to confirm physical units before traveling.
              </p>
            </div>

            {/* City Selector Pills */}
            <div className="flex items-center gap-1.5 sm:gap-2 bg-[var(--bg-elevated)] p-1.5 rounded-xl border border-[var(--border-main)] shrink-0">
              {(['All', 'Delhi', 'Lucknow'] as CityFilter[]).map(city => (
                <button
                  key={city}
                  onClick={() => setSelectedCity(city)}
                  className={`px-3 sm:px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    selectedCity === city
                      ? 'bg-[#B91C35] text-white shadow-sm'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {city === 'All' ? 'All Cities' : `${city}`}
                </button>
              ))}
            </div>
          </div>

          {/* Blood Group Selector Chips */}
          <div className="pt-6">
            <div className="flex items-center justify-between mb-3">
              <label className="block text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                Select Blood Group:
              </label>
              {selectedGroup !== 'All' && (
                <button
                  onClick={() => setSelectedGroup('All')}
                  className="text-xs font-semibold text-[#B91C35] hover:underline cursor-pointer"
                >
                  Clear Selection (Show All)
                </button>
              )}
            </div>
            <div className="grid grid-cols-5 sm:grid-cols-9 gap-2 sm:gap-3">
              <button
                onClick={() => setSelectedGroup('All')}
                className={`py-2.5 px-2 rounded-xl font-bold text-sm border transition-all cursor-pointer ${
                  selectedGroup === 'All'
                    ? 'bg-[#B91C35] text-white border-[#B91C35] shadow-md shadow-[#B91C35]/25 scale-102'
                    : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border-[var(--border-main)] hover:border-[#B91C35]/40'
                }`}
              >
                All
              </button>
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

          {/* Controls Bar: Toggles & Provenance Note */}
          <div className="mt-8 pt-5 border-t border-[var(--border-main)] flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-5">
              {/* Include demo data toggle */}
              <label
                htmlFor="toggle-include-demo"
                className="flex items-center gap-2.5 cursor-pointer text-xs sm:text-sm font-semibold text-[var(--text-primary)] select-none"
              >
                <input
                  id="toggle-include-demo"
                  type="checkbox"
                  checked={includeDemo}
                  onChange={e => setIncludeDemo(e.target.checked)}
                  className="w-4 h-4 rounded border-[var(--border-main)] text-[#B91C35] focus:ring-[#B91C35] accent-[#B91C35] cursor-pointer"
                />
                <span>Include demo data</span>
                {includeDemo ? (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                    Demo Appended
                  </span>
                ) : (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
                    Real e-RaktKosh Only (Default)
                  </span>
                )}
              </label>
            </div>

            <div className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5 font-medium shrink-0">
              <Database className="w-3.5 h-3.5 text-blue-500" />
              <span>
                {hasExternal && hasDemo
                  ? 'Showing e-RaktKosh feed first, followed by demo dataset'
                  : hasExternal
                  ? 'Official source-reported e-RaktKosh snapshots • Source inventory is unverified'
                  : 'All visible records are synthetic demo data'}
              </span>
            </div>
          </div>
        </div>

        {/* Results Header Strip */}
        <div className="mt-8 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
            <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span>
                Reported Facilities: {selectedCity === 'All' ? 'Delhi & Lucknow' : selectedCity}{' '}
                {selectedGroup !== 'All' ? `(${selectedGroup})` : '(All Groups)'}
              </span>
              {!isLoading && !error && (
                <span className="text-xs font-normal text-[var(--text-secondary)]">
                  ({visibleCount} {visibleCount === 1 ? 'facility' : 'facilities'} reported
                  {dataTimestamp ? ` • Snapshot: ${formatTimestamp(dataTimestamp).localDisplay}` : ''})
                </span>
              )}
            </h3>
            <span className="text-xs text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" />
              {hasExternal && hasDemo
                ? 'Mixed records: e-RaktKosh first, demo data appended'
                : hasExternal
                ? 'Official source-reported snapshots (unverified)'
                : 'Simulated demonstration records only'}
            </span>
          </div>

          {/* Top Data Disclaimer Notice from API */}
          {dataNotice && (
            <div className="bg-amber-500/10 border border-amber-500/25 rounded-2xl p-3.5 text-xs text-amber-800 dark:text-amber-300 flex items-start sm:items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5 sm:mt-0" />
              <span className="font-medium leading-relaxed">{dataNotice}</span>
            </div>
          )}

          {/* Loading Skeleton */}
          {isLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {[1, 2, 3, 4].map(idx => (
                <div
                  key={idx}
                  className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 space-y-4 animate-pulse"
                >
                  <div className="flex justify-between items-start">
                    <div className="space-y-2 w-3/4">
                      <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded-md w-4/5" />
                      <div className="h-3.5 bg-slate-100 dark:bg-slate-800/60 rounded-md w-1/2" />
                    </div>
                    <div className="w-11 h-11 bg-slate-200 dark:bg-slate-800 rounded-xl" />
                  </div>
                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[var(--border-main)]">
                    <div className="h-8 bg-slate-100 dark:bg-slate-800/50 rounded-md" />
                    <div className="h-8 bg-slate-100 dark:bg-slate-800/50 rounded-md" />
                  </div>
                  <div className="h-6 bg-slate-100 dark:bg-slate-800/40 rounded-md pt-3 border-t border-[var(--border-main)]" />
                </div>
              ))}
            </div>
          )}

          {/* Error State */}
          {!isLoading && error && (
            <div className="bg-[var(--bg-surface)] border border-rose-300 dark:border-rose-900/60 rounded-2xl p-8 text-center space-y-4 shadow-sm">
              <div className="w-12 h-12 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-[#B91C35] flex items-center justify-center mx-auto border border-rose-200 dark:border-rose-800/50">
                <AlertCircle className="w-6 h-6 text-[#B91C35]" />
              </div>
              <div className="max-w-md mx-auto space-y-1.5">
                <h4 className="font-extrabold text-base text-[var(--text-primary)]">
                  Unable to Connect to Discovery API
                </h4>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {error}
                </p>
                <p className="text-[11px] text-slate-400">
                  Ensure the local FastAPI backend server is running on <code className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800">http://127.0.0.1:8000</code>.
                </p>
              </div>
              <button
                onClick={handleRetry}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#B91C35] hover:bg-[#A0162D] text-white text-xs font-bold transition-all shadow-sm cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Connection</span>
              </button>
            </div>
          )}

          {/* Empty State */}
          {!isLoading && !error && visibleBanks.length === 0 && (
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-10 text-center space-y-4 shadow-sm">
              <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 text-[var(--text-secondary)] flex items-center justify-center mx-auto">
                <Search className="w-6 h-6 text-slate-400" />
              </div>
              <div className="max-w-md mx-auto space-y-1">
                <h4 className="font-extrabold text-base text-[var(--text-primary)]">
                  No Reported Facilities Found
                </h4>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  No blood bank records matched your criteria for <strong>{selectedCity === 'All' ? 'Delhi & Lucknow' : selectedCity}</strong>{' '}
                  {selectedGroup !== 'All' ? `with blood group ${selectedGroup}` : ''}.
                  {!includeDemo && banks.some(b => b.source_type === 'demo') && (
                    <span className="block mt-1 text-amber-600 dark:text-amber-400">
                      (Synthetic demo records exist for this filter. Enable &ldquo;Include demo data&rdquo; to view them.)
                    </span>
                  )}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-3">
                <button
                  onClick={handleResetFilters}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-[var(--border-main)] bg-[var(--bg-elevated)] text-xs font-bold hover:border-[#B91C35]/50 transition-all cursor-pointer"
                >
                  <FilterX className="w-3.5 h-3.5 text-[#B91C35]" />
                  <span>Reset Filters (Show All)</span>
                </button>
                {!includeDemo && banks.some(b => b.source_type === 'demo') && (
                  <button
                    onClick={() => setIncludeDemo(true)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-300 text-xs font-bold hover:bg-amber-500/20 transition-all cursor-pointer"
                  >
                    <span>Include Demo Data</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Facilities Results Cards */}
          {!isLoading && !error && visibleBanks.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {visibleBanks.map(bank => {
                const activeReport =
                  selectedGroup !== 'All'
                    ? bank.stock_reports.find(r => r.blood_group === selectedGroup) || bank.stock_reports[0]
                    : bank.stock_reports[0]
                const freshness = getReportFreshnessInfo(activeReport)
                const isExternal =
                  bank.source_type === 'external_source' ||
                  activeReport?.verification_status === 'reported_unverified'

                return (
                  <div
                    key={bank.id}
                    className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-6 hover:border-[#B91C35]/50 transition-all shadow-sm hover:shadow-md flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h4 className="font-extrabold text-base text-[var(--text-primary)] leading-snug">
                              {bank.name}
                            </h4>
                            {isExternal ? (
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60">
                                e-RaktKosh Feed
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60">
                                Synthetic Demo
                              </span>
                            )}
                            {bank.category && (
                              <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-main)]">
                                {bank.category}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5 font-medium">
                            <MapPin className="w-3.5 h-3.5 text-[#B91C35]" />
                            <span>{bank.locality ? `${bank.locality} • ` : ''}{bank.city}</span>
                          </p>
                        </div>

                        {/* Blood Group Badge */}
                        <div className="text-right shrink-0">
                          <span className="inline-flex items-center justify-center min-w-11 h-11 px-2.5 rounded-xl bg-[#FFF1F2] dark:bg-[#B91C35]/25 text-[#B91C35] font-extrabold text-base border border-[#B91C35]/35 shadow-sm">
                            {selectedGroup !== 'All' ? selectedGroup : `${bank.stock_reports.length} Groups`}
                          </span>
                        </div>
                      </div>

                      {/* Component Display Strip */}
                      <div className="flex items-center justify-between text-xs py-1.5 px-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-main)]">
                        <span className="text-[var(--text-secondary)] font-medium">Blood Component:</span>
                        <span className="font-bold text-[var(--text-primary)]">
                          {activeReport?.blood_component || (isExternal ? 'Whole Blood (Queried Feed)' : 'Unspecified')}
                        </span>
                      </div>

                      {/* Stock Quantity & Freshness Strip */}
                      <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[var(--border-main)]">
                        <div>
                          <span className="text-[11px] font-semibold text-[var(--text-secondary)] block uppercase tracking-wider">
                            Reported Quantity:
                          </span>
                          <span className="text-sm font-bold text-[var(--text-primary)] block">
                            {activeReport ? (
                              <>
                                {activeReport.units_reported} units{' '}
                                {isExternal ? (
                                  <span className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold">
                                    (Source-Reported)
                                  </span>
                                ) : (
                                  <span className="text-[10px] text-amber-600 dark:text-amber-400 font-semibold">
                                    (Demo Snapshot)
                                  </span>
                                )}
                              </>
                            ) : (
                              <>
                                <span className="text-[var(--text-secondary)] font-semibold">No stock reported</span>{' '}
                                <span className="text-[10px] text-[var(--text-secondary)] font-normal">
                                  (Feed Unstocked)
                                </span>
                              </>
                            )}
                          </span>
                          <span className="text-[10px] text-[var(--text-secondary)] block mt-0.5">
                            {activeReport
                              ? isExternal
                                ? 'Unverified • Availability not guaranteed'
                                : 'Not a physical guarantee'
                              : 'No stock reported in source feed • Not confirmed out of stock'}
                          </span>
                        </div>
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-semibold text-[var(--text-secondary)] block uppercase tracking-wider">
                              {freshness.primaryLabel}:
                            </span>
                            {freshness.isStale && (
                              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                                Stale (&gt;24h)
                              </span>
                            )}
                          </div>
                          {freshness.isLiveBadge ? (
                            <div className="mt-0.5">
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-700 dark:text-blue-300 font-bold text-xs border border-blue-500/20">
                                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                                {freshness.primaryDisplay}
                              </span>
                              <span className="text-[10px] text-[var(--text-secondary)] block mt-0.5 leading-tight">
                                Portal live indicator (unverified) • Not a physical stock guarantee
                              </span>
                            </div>
                          ) : activeReport ? (
                            <div>
                              <span
                                className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1.5 mt-0.5"
                                title={freshness.utcDisplay ? `UTC: ${freshness.utcDisplay}` : undefined}
                              >
                                <Clock className={`w-3.5 h-3.5 shrink-0 ${freshness.isStale ? 'text-amber-500' : 'text-slate-400'}`} />
                                <span className="truncate">{freshness.primaryDisplay}</span>
                              </span>
                              {freshness.utcDisplay && (
                                <span className="text-[10px] text-[var(--text-secondary)] block mt-0.5 font-mono">
                                  UTC: {freshness.utcDisplay}
                                </span>
                              )}
                              {freshness.secondaryNote && (
                                <span className="text-[10px] text-[var(--text-secondary)] block mt-0.5 leading-tight">
                                  {freshness.secondaryNote}
                                </span>
                              )}
                            </div>
                          ) : (
                            <div>
                              <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5 mt-0.5 font-medium">
                                <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                <span>No stock observations</span>
                              </span>
                              <span className="text-[10px] text-[var(--text-secondary)] block mt-0.5 leading-tight">
                                Source feed did not report positive units for this query.
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Facility Card Footer */}
                    <div className="mt-5 pt-3.5 border-t border-[var(--border-main)] flex flex-wrap items-center justify-between text-xs gap-2">
                      <span
                        className="text-[11px] font-medium text-[var(--text-secondary)] bg-[var(--bg-elevated)] px-2.5 py-1 rounded-lg border border-[var(--border-main)] truncate max-w-[200px]"
                        title={activeReport?.source_name || bank.source_name}
                      >
                        {activeReport?.source_name || bank.source_name || (isExternal ? 'e-RaktKosh (MoHFW)' : 'Synthetic demo dataset')}
                      </span>
                      {activeReport?.verification_status === 'demo' || (!isExternal && !activeReport) ? (
                        <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50 px-2.5 py-1 rounded-lg flex items-center gap-1 shrink-0">
                          <AlertTriangle className="w-3 h-3" />
                          Simulated Demo Data (Unverified)
                        </span>
                      ) : isExternal ? (
                        <span className="text-[11px] font-semibold text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/50 px-2.5 py-1 rounded-lg flex items-center gap-1 shrink-0">
                          <ShieldCheck className="w-3 h-3" />
                          Source-Reported Snapshot (Unverified)
                        </span>
                      ) : (
                        <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800/50 px-2.5 py-1 rounded-lg flex items-center gap-1 shrink-0">
                          <AlertTriangle className="w-3 h-3" />
                          {activeReport?.verification_status || 'Unverified'}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>

      {/* "Become a Donor" Interactive Demonstration Section */}
      <section id="become-donor" className="py-16 lg:py-24 border-t border-[var(--border-main)] bg-[var(--bg-elevated)]/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
            {/* Left: Section Narrative & Notice */}
            <div className="lg:col-span-5 space-y-5 text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] text-xs font-bold tracking-wide border border-[#B91C35]/25">
                <HeartHandshake className="w-3.5 h-3.5" />
                <span>Voluntary Donor Community</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-[var(--text-primary)] tracking-tight">
                Be on Standby When <br />
                Every Minute Counts.
              </h2>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                When a hospital faces sudden stock shortages or a critical trauma case, voluntary donors within the same city can bridge the crucial gap before centralized supply arrives.
              </p>

              {/* Privacy Promises Callout */}
              <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-5 space-y-3 shadow-sm">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[#B91C35]" />
                  <span>Privacy-First Architecture</span>
                </h4>
                <ul className="space-y-2 text-xs text-[var(--text-secondary)]">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>No phone numbers stored:</strong> We never request or store phone numbers in our database.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>Per-request consent:</strong> Your Telegram handle is only shared when you explicitly click Accept on a matching alert.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>Instant opt-out:</strong> Send <code>/stopdonor</code> anytime to stop all future notifications immediately.</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Right: Interactive Prototype Form */}
            <div className="lg:col-span-7">
              <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-3xl p-6 sm:p-9 shadow-sm">
                <div className="flex items-center justify-between pb-5 border-b border-[var(--border-main)] mb-6">
                  <div>
                    <h3 className="text-lg font-bold text-[var(--text-primary)]">
                      Donor Registration Demonstration
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      Preview the donor enrollment experience planned for our Telegram bot.
                    </p>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/25">
                    Prototype Form
                  </span>
                </div>

                {donorSubmitted ? (
                  /* Friendly Submission Confirmation State */
                  <div className="py-6 text-center space-y-4">
                    <div className="w-14 h-14 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 flex items-center justify-center mx-auto border border-emerald-200 dark:border-emerald-800/60">
                      <CheckCircle2 className="w-7 h-7" />
                    </div>
                    <div className="space-y-1">
                      <h4 className="text-xl font-extrabold text-[var(--text-primary)]">
                        Volunteer Demonstration Received!
                      </h4>
                      <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-md mx-auto">
                        You simulated enrollment as an <strong>{donorGroup}</strong> donor in <strong>{donorCity}</strong>.
                      </p>
                    </div>

                    <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 text-xs text-amber-800 dark:text-amber-300 max-w-md mx-auto text-left flex items-start gap-3">
                      <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div className="space-y-1">
                        <p className="font-bold">Demonstration Only — Data Not Persisted</p>
                        <p className="leading-relaxed text-[11px]">
                          This web form is an interactive design preview. No personal data was saved to a database. In the planned full release, voluntary registrations will be securely managed via our Telegram bot.
                        </p>
                      </div>
                    </div>

                    <div className="pt-2">
                      <button
                        onClick={() => {
                          setDonorSubmitted(false)
                          setDonorConsent(false)
                        }}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[var(--border-main)] bg-[var(--bg-elevated)] text-xs font-bold hover:border-[#B91C35] transition-colors cursor-pointer"
                      >
                        <RefreshCw className="w-3.5 h-3.5 text-[#B91C35]" />
                        <span>Simulate Another Selection</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Interactive Form */
                  <form onSubmit={handleDonorSubmit} className="space-y-6">
                    {/* Field 1: Blood Group */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                        1. Select Your Blood Group:
                      </label>
                      <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
                        {BLOOD_GROUPS.map(group => (
                          <button
                            key={group}
                            type="button"
                            onClick={() => setDonorGroup(group)}
                            className={`py-2 px-2 text-xs font-bold rounded-xl border transition-all cursor-pointer ${
                              donorGroup === group
                                ? 'bg-[#B91C35] text-white border-[#B91C35] shadow-sm'
                                : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border-[var(--border-main)] hover:border-[#B91C35]/50'
                            }`}
                          >
                            {group}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Field 2: Supported City */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                        2. Select Your City (Supported Scope):
                      </label>
                      <div className="grid grid-cols-2 gap-3">
                        {(['Delhi', 'Lucknow'] as City[]).map(city => (
                          <button
                            key={city}
                            type="button"
                            onClick={() => setDonorCity(city)}
                            className={`py-2.5 px-4 text-xs font-bold rounded-xl border transition-all flex items-center justify-center gap-2 cursor-pointer ${
                              donorCity === city
                                ? 'bg-[#B91C35] text-white border-[#B91C35] shadow-sm'
                                : 'bg-[var(--bg-elevated)] text-[var(--text-primary)] border-[var(--border-main)] hover:border-[#B91C35]/50'
                            }`}
                          >
                            <MapPin className="w-3.5 h-3.5" />
                            <span>{city}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Explicit Consent Notice & Checkbox */}
                    <div className="bg-[var(--bg-elevated)] border border-[var(--border-main)] rounded-2xl p-4 space-y-3">
                      <div className="flex items-start gap-3">
                        <input
                          id="donor-consent-checkbox"
                          type="checkbox"
                          checked={donorConsent}
                          onChange={e => setDonorConsent(e.target.checked)}
                          className="w-4 h-4 mt-0.5 rounded border-[var(--border-main)] text-[#B91C35] focus:ring-[#B91C35] accent-[#B91C35] cursor-pointer shrink-0"
                        />
                        <label
                          htmlFor="donor-consent-checkbox"
                          className="text-xs text-[var(--text-secondary)] leading-relaxed select-none cursor-pointer"
                        >
                          <strong className="text-[var(--text-primary)]">Voluntary Opt-In Agreement:</strong> I consent to receive urgent requirements for my blood group in {donorCity}. I understand that RaktSetu will never store my phone number and that contact sharing requires my explicit acceptance.
                        </label>
                      </div>

                      <div className="pt-2 border-t border-[var(--border-main)] flex items-center gap-2 text-[11px] text-amber-700 dark:text-amber-400">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                        <span>Interactive Prototype: This submission will demonstrate the workflow without persisting data.</span>
                      </div>
                    </div>

                    {donorError && (
                      <p className="text-xs text-rose-600 dark:text-rose-400 font-semibold flex items-center gap-1.5">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{donorError}</span>
                      </p>
                    )}

                    {/* Submit Button */}
                    <button
                      type="submit"
                      className="w-full py-3 rounded-xl bg-[#B91C35] hover:bg-[#A0162D] text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors shadow-md shadow-[#B91C35]/20 cursor-pointer"
                    >
                      <HeartHandshake className="w-4 h-4" />
                      <span>Demonstrate Volunteer Enrollment ({donorGroup} • {donorCity})</span>
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>

          {/* Donor Network Preview Cards */}
          <div className="mt-14 pt-10 border-t border-[var(--border-main)]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
              <div>
                <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                  <Users className="w-4 h-4 text-[#B91C35]" />
                  <span>Illustrative Donor Network Cards</span>
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">
                  Preview of how community volunteer standby cards will be presented to moderators.
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30 shrink-0">
                <AlertTriangle className="w-3 h-3" />
                Sample profiles — demo data
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {SAMPLE_DONOR_PROFILES.map(profile => (
                <div
                  key={profile.alias}
                  className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-2xl p-4 shadow-sm space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-[var(--text-primary)]">
                      {profile.alias}
                    </span>
                    <span className="px-2 py-0.5 rounded-lg bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] font-extrabold text-xs border border-[#B91C35]/25">
                      {profile.group}
                    </span>
                  </div>

                  <div className="text-xs text-[var(--text-secondary)] space-y-1">
                    <p className="flex items-center gap-1 font-medium">
                      <MapPin className="w-3 h-3 text-[#B91C35]" />
                      <span>{profile.city}</span>
                    </p>
                    <p className="text-[11px] text-slate-400">{profile.notes}</p>
                  </div>

                  <div className="pt-2 border-t border-[var(--border-main)] flex items-center justify-between text-[10px]">
                    <span className="text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      {profile.status}
                    </span>
                    <span className="text-amber-600 dark:text-amber-400 font-medium">
                      Mockup Profile
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-[11px] text-center text-[var(--text-secondary)] mt-4">
              * The donor cards above are mockups for demonstration. RaktSetu does not claim active registered donor availability until real coordination is deployed.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works & Future Scope Section */}
      <section id="how-it-works" className="py-16 lg:py-24 border-t border-[var(--border-main)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          {/* Header */}
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#B91C35]">
              System Transparency
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[var(--text-primary)] tracking-tight">
              How RaktSetu Works
            </h2>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              We clearly distinguish features that work today from our upcoming release roadmap.
            </p>
          </div>

          {/* Side-by-Side: Working Today vs Future Scope */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
            {/* Column 1: Working Today */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-[var(--border-main)]">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-extrabold text-base text-[var(--text-primary)]">
                      Working Today
                    </h3>
                    <p className="text-[11px] text-[var(--text-secondary)]">
                      Active features running in this prototype
                    </p>
                  </div>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/25">
                  Live in Prototype
                </span>
              </div>

              <div className="space-y-4 text-xs sm:text-sm">
                <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-main)] space-y-1.5">
                  <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Database className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
                    <span>Real e-RaktKosh Feed Ingestion</span>
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Ingests government portal availability feeds for Delhi and Lucknow hospitals, clearly preserving source timestamps and labeling stale snapshots (&gt;24h old).
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-main)] space-y-1.5">
                  <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Bot className="w-4 h-4 text-[#0088cc] shrink-0" />
                    <span>Telegram Discovery Bot Prototype</span>
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Interactive Telegram assistant supporting <code>/find &lt;Group&gt; &lt;City&gt;</code> commands, inline keyboard queries, and automated emergency disclaimers.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-main)] space-y-1.5">
                  <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-[#B91C35] shrink-0" />
                    <span>Fail-Closed Provenance Isolation</span>
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Demo records are excluded by default. Real hospital data is prioritized, and contact information is strictly scrubbed from raw feeds.
                  </p>
                </div>
              </div>
            </div>

            {/* Column 2: Future Scope */}
            <div id="future-scope" className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-[var(--border-main)]">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-[#FFF1F2] dark:bg-[#B91C35]/20 text-[#B91C35] flex items-center justify-center font-bold">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-extrabold text-base text-[var(--text-primary)]">
                      Future Scope
                    </h3>
                    <p className="text-[11px] text-[var(--text-secondary)]">
                      Planned donor coordination & scale architecture
                    </p>
                  </div>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/25">
                  Roadmap
                </span>
              </div>

              <div className="space-y-4 text-xs sm:text-sm">
                <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-main)] space-y-1.5">
                  <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <HeartHandshake className="w-4 h-4 text-[#B91C35] shrink-0" />
                    <span>Consent-Based Volunteer Matching</span>
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Emergency blood requests verified by community moderators dispatch private Telegram alerts. Donors accept or decline, and handles are shared only with explicit consent.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-main)] space-y-1.5">
                  <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Activity className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                    <span>Specific Blood Component Subtypes</span>
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Granular tracking for Packed Red Blood Cells (PRBC), Single Donor Platelets (SDP), and Fresh Frozen Plasma (FFP) to support oncology and surgical needs.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-main)] space-y-1.5">
                  <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0" />
                    <span>Geographic & Multilingual Expansion</span>
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    Scaling beyond Delhi and Lucknow to tier-2 district centers, paired with voice-assisted accessibility and Hindi language localization.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Telegram Community Call to Action Card */}
      <section className="py-12 bg-gradient-to-r from-[#0088cc]/10 via-[#0077b5]/5 to-transparent border-t border-[var(--border-main)]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-[var(--bg-surface)] border border-[#0088cc]/30 rounded-3xl p-6 sm:p-10 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-6 text-center sm:text-left">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 text-xs font-bold text-[#0088cc] uppercase tracking-wider">
                <Bot className="w-4 h-4" />
                <span>Telegram Integration Prototype</span>
              </div>
              <h3 className="text-2xl font-extrabold text-[var(--text-primary)] tracking-tight">
                Connect Directly via Telegram
              </h3>
              <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-xl leading-relaxed">
                Search nearby hospital stock records right from your messaging app using our lightweight Telegram discovery bot.
              </p>
            </div>

            <div className="shrink-0">
              <a
                href={telegramBotUrl || '#telegram-info'}
                onClick={handleOpenTelegram}
                target={telegramBotUrl ? '_blank' : undefined}
                rel={telegramBotUrl ? 'noopener noreferrer' : undefined}
                className="inline-flex items-center gap-2.5 px-6 py-3 rounded-xl bg-gradient-to-r from-[#0088cc] to-[#0077b5] text-white font-bold text-xs shadow-md shadow-[#0088cc]/25 hover:opacity-95 transition-opacity cursor-pointer"
              >
                <Bot className="w-4 h-4" />
                <span>Chat with RaktSetu on Telegram</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Ethical Safeguards & Medical Notice Section */}
      <section id="trust-safety" className="py-14 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 border-t border-[var(--border-main)]">
        <div className="rounded-3xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/20 p-7 sm:p-10">
          <div className="flex flex-col sm:flex-row items-start gap-5">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="space-y-3.5">
              <h3 className="text-lg sm:text-xl font-extrabold text-amber-950 dark:text-amber-200 tracking-tight">
                Trust, Ethics & Emergency Medical Guidance
              </h3>
              <p className="text-xs sm:text-sm text-amber-900/90 dark:text-amber-300/90 leading-relaxed">
                RaktSetu is an open-source technical prototype built to demonstrate transparent health-data aggregation and privacy-preserving volunteer coordination.
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-amber-900/80 dark:text-amber-300/80 pt-1">
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Never guarantees physical blood inventory without direct hospital verification.</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>External portal stock feeds are unverified snapshots and may be delayed or stale.</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>Donor participation is strictly opt-in with revocable voluntary consent.</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>For acute trauma or life-threatening emergencies, immediately dial <strong>112</strong> (India&apos;s National Emergency Number).</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Telegram Configuration Modal / Information Card */}
      {showTelegramModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-main)] rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl space-y-5 animate-in fade-in duration-200">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-xl bg-[#0088cc]/15 text-[#0088cc] flex items-center justify-center">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-extrabold text-base text-[var(--text-primary)]">
                    Telegram Discovery Bot
                  </h4>
                  <p className="text-xs text-[var(--text-secondary)]">
                    Local prototype configuration
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowTelegramModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-[var(--text-primary)]"
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-[var(--text-secondary)] leading-relaxed">
              <p>
                The RaktSetu Telegram bot currently runs as a local prototype service. To test it locally:
              </p>
              <div className="bg-slate-100 dark:bg-slate-900 rounded-xl p-3 font-mono text-[11px] text-slate-800 dark:text-slate-200">
                python -m backend.app.bot.main
              </div>
              <p>
                To connect this website&apos;s button directly to your live bot, set the environment variable in <code className="px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[var(--text-primary)]">frontend/.env.local</code>:
              </p>
              <div className="bg-slate-100 dark:bg-slate-900 rounded-xl p-3 font-mono text-[11px] text-slate-800 dark:text-slate-200">
                VITE_TELEGRAM_BOT_URL=https://t.me/your_bot_username
              </div>
              <p className="text-[11px] text-slate-400">
                Note: In accordance with our security principles, the bot token is loaded strictly on the backend and is never exposed in frontend code.
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setShowTelegramModal(false)}
                className="px-5 py-2 rounded-xl bg-[#B91C35] text-white text-xs font-bold hover:bg-[#A0162D] transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

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
                • Open-Source Healthcare Initiative
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)] font-medium">
              <span>Delhi & Lucknow Scope</span>
              <span>•</span>
              <a
                href="https://github.com/rayyan-sidd/RaktSetu"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#B91C35] underline"
              >
                GitHub Repository
              </a>
              <span>•</span>
              <a
                href="#trust-safety"
                className="hover:text-[#B91C35] underline"
              >
                Trust & Safety
              </a>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-[var(--border-main)] text-center text-xs text-[var(--text-secondary)]">
            &copy; 2026 RaktSetu Maintainers and Contributors. Licensed under the MIT License.
          </div>
        </div>
      </footer>
    </div>
  )
}
