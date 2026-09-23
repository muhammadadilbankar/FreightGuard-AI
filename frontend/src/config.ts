type ExplanationMode = 'template' | 'replay' | 'live'

const required = (name: string, fallback?: string): string => {
  const environment: Record<string, unknown> = import.meta.env
  const value = environment[name] ?? fallback
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Missing required build setting: ${name}`)
  }
  return value.trim()
}

const mode = required('VITE_DEFAULT_EXPLANATION_MODE', 'template')
if (!['template', 'replay', 'live'].includes(mode)) {
  throw new Error('VITE_DEFAULT_EXPLANATION_MODE is invalid')
}

export const config = Object.freeze({
  apiBaseUrl: required('VITE_API_BASE_URL', 'http://127.0.0.1:8000').replace(/\/+$/, ''),
  appName: required('VITE_APP_NAME', 'FreightGuard AI'),
  defaultExplanationMode: mode as ExplanationMode,
  enableLiveMode: required('VITE_ENABLE_LIVE_MODE', 'false').toLowerCase() === 'true',
})
