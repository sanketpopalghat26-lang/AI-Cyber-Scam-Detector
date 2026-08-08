import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import config, { validateConfig } from './config'

// Validate runtime configuration at startup (throws in production if invalid).
validateConfig()
const API_BASE = config.apiBase

const starterMessages = [
  'Urgent: verify your bank account now or it will be locked.',
  'You won a prize! Click the link to claim your reward.',
  'Hi, please review the attached invoice before payment.',
]

function App() {
  const [text, setText] = useState(starterMessages[0])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [authMode, setAuthMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [dashboard, setDashboard] = useState(null)

  useEffect(() => {
    if (!token) return
    axios.get(`${API_BASE}/dashboard`, { headers: { Authorization: `Bearer ${token}` } })
      .then(({ data }) => setDashboard(data))
      .catch(() => {})
  }, [token])

  const handleScan = async () => {
    setLoading(true)
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const { data } = await axios.post(`${API_BASE}/predict`, { text, source: 'ui' }, { headers })
      setResult(data)
      if (token) {
        const dash = await axios.get(`${API_BASE}/dashboard`, { headers })
        setDashboard(dash.data)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleAuth = async (event) => {
    event.preventDefault()
    try {
      const endpoint = authMode === 'login' ? '/auth/login' : '/auth/signup'
      const form = new URLSearchParams({ username: email, password })
      const { data } = await axios.post(`${API_BASE}${endpoint}`, form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      setToken(data.access_token)
      localStorage.setItem('token', data.access_token)
    } catch (error) {
      alert(error.response?.data?.detail || 'Authentication failed')
    }
  }

  const stats = useMemo(() => [
    { label: 'Total Scans', value: dashboard?.total_scans ?? 0 },
    { label: 'Scam %', value: `${dashboard?.scam_percentage ?? 0}%` },
    { label: 'Safe %', value: `${dashboard?.safe_percentage ?? 0}%` },
  ], [dashboard])

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.25),_transparent_30%),linear-gradient(135deg,_#07111f,_#1f1842)] text-slate-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 md:px-8 lg:px-10">
        <header className="rounded-3xl border border-white/10 bg-white/10 p-6 shadow-2xl backdrop-blur-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="mb-2 text-sm uppercase tracking-[0.3em] text-cyan-300">AI Cyber Scam Detector</p>
              <h1 className="text-3xl font-semibold sm:text-4xl">Production-grade scam intelligence for modern teams.</h1>
              <p className="mt-3 max-w-2xl text-sm text-slate-300 sm:text-base">Detect suspicious SMS, email, WhatsApp, URLs, and fake job content with explainable AI and real-time reporting.</p>
            </div>
            <div className="rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
              <p className="font-medium">Live risk model</p>
              <p className="text-cyan-300">Safe • Suspicious • Scam</p>
            </div>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Scanner</h2>
              <span className="rounded-full bg-violet-500/20 px-3 py-1 text-xs uppercase tracking-[0.25em] text-violet-200">Realtime</span>
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} className="w-full rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-sm outline-none ring-0" />
            <div className="mt-4 flex flex-wrap gap-3">
              {starterMessages.map((message) => (
                <button key={message} onClick={() => setText(message)} className="rounded-full border border-white/10 bg-white/10 px-3 py-2 text-sm text-slate-200 hover:bg-white/20">{message}</button>
              ))}
            </div>
            <button onClick={handleScan} disabled={loading} className="mt-5 rounded-2xl bg-gradient-to-r from-cyan-500 to-violet-500 px-5 py-3 font-semibold text-white shadow-lg transition hover:opacity-90 disabled:opacity-60">
              {loading ? 'Scanning...' : 'Analyze content'}
            </button>
            {result && (
              <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Prediction</h3>
                  <span className={`rounded-full px-3 py-1 text-sm font-medium ${result.label === 'scam' ? 'bg-rose-500/20 text-rose-200' : result.label === 'suspicious' ? 'bg-amber-500/20 text-amber-200' : 'bg-emerald-500/20 text-emerald-200'}`}>{result.label.toUpperCase()}</span>
                </div>
                <p className="mt-3 text-sm text-slate-300">Confidence: {(result.confidence * 100).toFixed(1)}%</p>
                <p className="mt-3 text-sm text-slate-300">{result.explanation.reason}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {result.explanation.keywords.map((keyword) => (
                    <span key={keyword} className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-200">{keyword}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-6">
            <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl font-semibold">Secure Access</h2>
                <button onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')} className="text-sm text-cyan-300">{authMode === 'login' ? 'Create account' : 'Log in'}</button>
              </div>
              <form onSubmit={handleAuth} className="space-y-3">
                <input value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-sm" placeholder="Email" />
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-sm" placeholder="Password" />
                <button type="submit" className="w-full rounded-2xl bg-slate-100 px-4 py-3 font-semibold text-slate-900">{authMode === 'login' ? 'Log in' : 'Sign up'}</button>
              </form>
            </div>

            <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl backdrop-blur-xl">
              <h2 className="text-xl font-semibold">Dashboard Snapshot</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {stats.map((stat) => (
                  <div key={stat.label} className="rounded-2xl border border-white/10 bg-white/10 p-3">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">{stat.label}</p>
                    <p className="mt-2 text-2xl font-semibold">{stat.value}</p>
                  </div>
                ))}
              </div>
              <ul className="mt-4 space-y-2 text-sm text-slate-300">
                {(dashboard?.recent_scans || []).slice(0, 4).map((scan) => (
                  <li key={scan.id} className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">{scan.input_text} · {scan.result}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

export default App

