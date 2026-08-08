/**
 * Frontend Runtime Environment Validation
 * Validates required runtime configuration at application startup.
 * Fails fast with clear error messages if configuration is missing/invalid.
 */

// Application configuration loaded from environment.
// Vite exposes VITE_* variables at build time; runtime overrides are applied
// via window.__APP_CONFIG__ when present (e.g., injected by a config server).
const runtimeConfig = typeof window !== 'undefined' ? window.__APP_CONFIG__ || {} : {}

function getEnvValue(key, fallback) {
  // Prefer runtime-injected config, then build-time VITE_*, then fallback.
  if (runtimeConfig[key] !== undefined && runtimeConfig[key] !== null && runtimeConfig[key] !== '') {
    return runtimeConfig[key]
  }
  if (import.meta.env[key] !== undefined && import.meta.env[key] !== '') {
    return import.meta.env[key]
  }
  return fallback
}

const config = {
  apiBase: getEnvValue('VITE_API_BASE', 'http://localhost:8000'),
  appName: getEnvValue('VITE_APP_NAME', 'AI Cyber Scam Detector'),
  enableAnalytics: getEnvValue('VITE_ENABLE_ANALYTICS', 'false').toLowerCase() === 'true',
}

// Validate configuration and fail fast with actionable messages.
export function validateConfig() {
  const errors = []

  if (!config.apiBase || typeof config.apiBase !== 'string') {
    errors.push('VITE_API_BASE is required. Set it to the backend API URL.')
  } else {
    // Validate it's a parseable URL (http/https)
    try {
      const parsed = new URL(config.apiBase)
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        errors.push('VITE_API_BASE must be an http(s) URL.')
      }
    } catch {
      errors.push('VITE_API_BASE is not a valid URL.')
    }
  }

  if (errors.length > 0) {
    // eslint-disable-next-line no-console
    console.error('[Config] Invalid application configuration:')
    errors.forEach((e) => console.error(`  - ${e}`))
    if (import.meta.env.PROD) {
      throw new Error(`Invalid application configuration:\n${errors.join('\n')}`)
    }
  }

  return { valid: errors.length === 0, errors, config }
}

export default config
