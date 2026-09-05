import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import config, { validateConfig } from './config'

// Validate runtime configuration at startup (throws in production if invalid).
validateConfig()
const API_BASE = config.apiBase

const exampleMessages = [
  { label: 'Scam Example', text: 'Congratulations! You won £1000 cash. Call now to claim your prize.' },
  { label: 'Safe Example', text: 'Hey, are you free this evening? Let\'s meet tomorrow.' },
  { label: 'Phishing Example', text: 'Your account has been selected for a reward. Click the link immediately to claim.' },
  { label: 'Normal Message', text: 'Can you send me the project report before 5 PM?' },
]

function App() {
  const [text, setText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [authMode, setAuthMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [dashboard, setDashboard] = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [systemStatus, setSystemStatus] = useState('checking')
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)

  // Fetch system status, model info, and dashboard on mount
  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        const [healthRes, modelRes] = await Promise.all([
          axios.get(`${API_BASE}/health`),
          axios.get(`${API_BASE}/api/model-info`),
        ])
        setSystemStatus(healthRes.data.status === 'ok' ? 'online' : 'degraded')
        setModelInfo(modelRes.data)
      } catch {
        setSystemStatus('offline')
      }
    }
    fetchSystemInfo()
  }, [])

  // Fetch dashboard when token changes
  useEffect(() => {
    if (!token) return
    axios.get(`${API_BASE}/dashboard`, { headers: { Authorization: `Bearer ${token}` } })
      .then(({ data }) => setDashboard(data))
      .catch(() => {})
  }, [token])

  // Fetch the authenticated user's scan history when token changes
  useEffect(() => {
    if (!token) {
      setHistory(null)
      return
    }
    let cancelled = false
    setHistoryLoading(true)
    axios
      .get(`${API_BASE}/history`, { headers: { Authorization: `Bearer ${token}` } })
      .then(({ data }) => {
        if (!cancelled) setHistory(data)
      })
      .catch(() => {
        if (!cancelled) setHistory([])
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const handleScan = async () => {
    if (!text.trim()) {
      setError('Please enter a message to analyze.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const { data } = await axios.post(`${API_BASE}/api/detect`, { text, source: 'ui' }, { headers })
      setResult(data)
      if (token) {
        const dash = await axios.get(`${API_BASE}/dashboard`, { headers })
        setDashboard(dash.data)
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze message. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setText('')
    setResult(null)
    setError(null)
  }

  const handleAuth = async (event) => {
    event.preventDefault()
    setError(null)
    try {
      const endpoint = authMode === 'login' ? '/auth/login' : '/auth/signup'
      const form = new URLSearchParams({ username: email, password })
      const { data } = await axios.post(`${API_BASE}${endpoint}`, form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      setToken(data.access_token)
      localStorage.setItem('token', data.access_token)
      setEmail('')
      setPassword('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed')
    }
  }

  const handleLogout = () => {
    setToken('')
    localStorage.removeItem('token')
    setDashboard(null)
    setHistory(null)
  }

  const stats = useMemo(() => [
    { label: 'Messages Analyzed', value: dashboard?.total_scans ?? 0, icon: '📊' },
    { label: 'Scams Detected', value: dashboard?.scam_percentage ? `${dashboard.scam_percentage}%` : '0%', icon: '🚨' },
    { label: 'Safe Messages', value: dashboard?.safe_percentage ? `${dashboard.safe_percentage}%` : '0%', icon: '✅' },
  ], [dashboard])

  const resultStyles = {
    scam: {
      badge: 'bg-rose-500/20 text-rose-200 border-rose-500/30',
      icon: '🚨',
      title: 'SCAM DETECTED',
      bar: 'bg-rose-500',
    },
    suspicious: {
      badge: 'bg-amber-500/20 text-amber-200 border-amber-500/30',
      icon: '⚠️',
      title: 'SUSPICIOUS',
      bar: 'bg-amber-500',
    },
    safe: {
      badge: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
      icon: '✅',
      title: 'SAFE MESSAGE',
      bar: 'bg-emerald-500',
    },
  }

  const resultStyle = result ? resultStyles[result.prediction.toLowerCase()] || resultStyles.safe : null

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.25),_transparent_30%),linear-gradient(135deg,_#07111f,_#1f1842)] text-slate-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 md:px-8 lg:px-10">
        {/* Header */}
        <header className="rounded-3xl border border-white/10 bg-white/10 p-6 shadow-2xl backdrop-blur-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-violet-600 text-2xl shadow-lg">
                🛡️
              </div>
              <div>
                <p className="mb-1 text-sm uppercase tracking-[0.3em] text-cyan-300">AI Cyber Scam Detector</p>
                <h1 className="text-2xl font-semibold sm:text-3xl">Enterprise Scam Intelligence Platform</h1>
                <p className="mt-2 max-w-2xl text-sm text-slate-300">
                  Detect suspicious SMS, email, WhatsApp, and phishing content with explainable AI.
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <div className={`rounded-2xl border px-4 py-3 text-sm ${
                systemStatus === 'online'
                  ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-100'
                  : systemStatus === 'degraded'
                    ? 'border-amber-400/30 bg-amber-500/10 text-amber-100'
                    : 'border-rose-400/30 bg-rose-500/10 text-rose-100'
              }`}>
                <p className="font-medium">System Status</p>
                <p className="capitalize">{systemStatus === 'online' ? '● Online' : systemStatus === 'degraded' ? '● Degraded' : '● Offline'}</p>
              </div>
              {modelInfo && (
                <div className="rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
                  <p className="font-medium">Model: {modelInfo.model_name}</p>
                  <p className="text-cyan-300">
                    {modelInfo.classes.join(' • ')}
                    {modelInfo.accuracy ? ` • Accuracy: ${(modelInfo.accuracy * 100).toFixed(1)}%` : ''}
                  </p>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Main Content */}
        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          {/* Scanner Panel */}
          <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Message Scanner</h2>
              <span className="rounded-full bg-violet-500/20 px-3 py-1 text-xs uppercase tracking-[0.25em] text-violet-200">Realtime</span>
            </div>

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              placeholder="Paste a suspicious message here to analyze it..."
              className="w-full rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-sm outline-none ring-0 placeholder:text-slate-500 focus:border-cyan-400/50"
            />

            {/* Example messages */}
            <div className="mt-4">
              <p className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-400">Try an example</p>
              <div className="flex flex-wrap gap-2">
                {exampleMessages.map((example) => (
                  <button
                    key={example.label}
                    onClick={() => setText(example.text)}
                    className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-white/20"
                  >
                    {example.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                onClick={handleScan}
                disabled={loading || !text.trim()}
                className="rounded-2xl bg-gradient-to-r from-cyan-500 to-violet-500 px-6 py-3 font-semibold text-white shadow-lg transition hover:opacity-90 disabled:opacity-50"
              >
                {loading ? 'Analyzing...' : '🔍 Detect Scam'}
              </button>
              <button
                onClick={handleClear}
                className="rounded-2xl border border-white/10 bg-white/10 px-6 py-3 font-semibold text-slate-200 transition hover:bg-white/20"
              >
                Clear
              </button>
            </div>

            {/* Error state */}
            {error && (
              <div className="mt-6 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
                <p className="font-medium">⚠️ {error}</p>
              </div>
            )}

            {/* Loading state */}
            {loading && (
              <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/70 p-6 text-center">
                <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent"></div>
                <p className="mt-3 text-sm text-slate-300">Analyzing message with ML model...</p>
              </div>
            )}

            {/* Result section */}
            {result && resultStyle && (
              <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/70 p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">{resultStyle.icon}</span>
                    <div>
                      <h3 className="text-lg font-semibold">{resultStyle.title}</h3>
                      <p className="text-sm text-slate-400">{result.message}</p>
                    </div>
                  </div>
                  <span className={`rounded-full border px-4 py-1.5 text-sm font-bold ${resultStyle.badge}`}>
                    {result.prediction}
                  </span>
                </div>

                {/* Confidence bar */}
                <div className="mt-5">
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-slate-400">Confidence</span>
                    <span className="font-semibold text-slate-200">{(result.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full rounded-full ${resultStyle.bar} transition-all duration-500`}
                      style={{ width: `${Math.min(result.confidence * 100, 100)}%` }}
                    ></div>
                  </div>
                </div>

                {/* Risk level */}
                <div className="mt-4 flex items-center gap-2">
                  <span className="text-sm text-slate-400">Risk Level:</span>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    result.risk_level === 'HIGH'
                      ? 'bg-rose-500/20 text-rose-200'
                      : result.risk_level === 'MEDIUM'
                        ? 'bg-amber-500/20 text-amber-200'
                        : 'bg-emerald-500/20 text-emerald-200'
                  }`}>
                    {result.risk_level}
                  </span>
                </div>

                {/* Explanation */}
                {result.explanation && (
                  <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
                    <p className="text-sm text-slate-300">{result.explanation.reason}</p>
                    {result.explanation.simple_explanation && (
                      <p className="mt-2 text-sm text-slate-400">{result.explanation.simple_explanation}</p>
                    )}
                    {result.explanation.safety_advice && (
                      <p className="mt-2 text-sm text-cyan-300">💡 {result.explanation.safety_advice}</p>
                    )}
                    {result.explanation.keywords && result.explanation.keywords.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {result.explanation.keywords.map((keyword) => (
                          <span key={keyword} className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-200">
                            {keyword}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Auth Panel */}
            <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl font-semibold">{token ? 'Account' : 'Secure Access'}</h2>
                {!token && (
                  <button
                    onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')}
                    className="text-sm text-cyan-300 hover:text-cyan-200"
                  >
                    {authMode === 'login' ? 'Create account' : 'Log in'}
                  </button>
                )}
              </div>
              {token ? (
                <div className="space-y-3">
                  <p className="text-sm text-slate-300">You are signed in. Scans will be saved to your history.</p>
                  <button
                    onClick={handleLogout}
                    className="w-full rounded-2xl border border-white/10 bg-white/10 px-4 py-3 font-semibold text-slate-200 transition hover:bg-white/20"
                  >
                    Log out
                  </button>
                </div>
              ) : (
                <form onSubmit={handleAuth} className="space-y-3">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-sm outline-none placeholder:text-slate-500 focus:border-cyan-400/50"
                    placeholder="Email"
                    required
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-sm outline-none placeholder:text-slate-500 focus:border-cyan-400/50"
                    placeholder="Password"
                    required
                  />
                  <button
                    type="submit"
                    className="w-full rounded-2xl bg-slate-100 px-4 py-3 font-semibold text-slate-900 transition hover:bg-white"
                  >
                    {authMode === 'login' ? 'Log in' : 'Sign up'}
                  </button>
                  <p className="text-center text-xs text-slate-500">
                    {authMode === 'login' ? 'Sign in to save your scan history' : 'Create an account to track your scans'}
                  </p>
                </form>
              )}
            </div>

            {/* Dashboard Stats */}
            <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
              <h2 className="text-xl font-semibold">Dashboard</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {stats.map((stat) => (
                  <div key={stat.label} className="rounded-2xl border border-white/10 bg-white/10 p-3 text-center">
                    <p className="text-xl">{stat.icon}</p>
                    <p className="mt-1 text-2xl font-semibold">{stat.value}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">{stat.label}</p>
                  </div>
                ))}
              </div>

              {dashboard?.recent_scans?.length > 0 && (
                <>
                  <p className="mt-5 mb-2 text-xs uppercase tracking-[0.2em] text-slate-400">Recent Scans</p>
                  <ul className="space-y-2 text-sm text-slate-300">
                    {dashboard.recent_scans.slice(0, 4).map((scan) => (
                      <li key={scan.id} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
                        <span className="truncate pr-2">{scan.input_text}</span>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                          scan.result === 'scam'
                            ? 'bg-rose-500/20 text-rose-200'
                            : scan.result === 'suspicious'
                              ? 'bg-amber-500/20 text-amber-200'
                              : 'bg-emerald-500/20 text-emerald-200'
                        }`}>
                          {scan.result.toUpperCase()}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {!token && (
                <p className="mt-4 text-center text-xs text-slate-500">
                  Sign in to see your scan history and statistics
                </p>
              )}
            </div>

            {/* Model Info */}
            {modelInfo && (
              <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
                <h2 className="text-xl font-semibold">ML Model</h2>
                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Type</span>
                    <span className="text-slate-200">{modelInfo.model_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Classes</span>
                    <span className="text-slate-200">{modelInfo.classes.join(', ')}</span>
                  </div>
                  {modelInfo.accuracy && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Accuracy</span>
                      <span className="text-emerald-300">{(modelInfo.accuracy * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {modelInfo.precision && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Precision</span>
                      <span className="text-slate-200">{(modelInfo.precision * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {modelInfo.recall && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Recall</span>
                      <span className="text-slate-200">{(modelInfo.recall * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-slate-400">Status</span>
                    <span className={`font-medium ${modelInfo.status === 'loaded' ? 'text-emerald-300' : 'text-amber-300'}`}>
                      {modelInfo.status}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-white/10 pt-4 text-center text-xs text-slate-500">
          <p>AI Cyber Scam Detector — Enterprise Edition | Powered by TF-IDF + Logistic Regression</p>
        </footer>
      </div>
    </div>
  )
}

export default App