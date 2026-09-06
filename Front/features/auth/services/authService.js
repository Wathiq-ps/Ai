export async function requestOtp(email) {
  const response = await fetch('/api/auth/otp/request', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ email }) })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) { const error = new Error(data.message || 'Unable to send verification code.'); error.status = response.status; throw error }
  return data
}

export async function verifyOtp(email, code) {
  const response = await fetch('/api/auth/otp/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ email, code }) })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) { const error = new Error(data.message || 'Invalid verification code.'); error.status = response.status; throw error }
  return data
}

export async function refreshSession() {
  const response = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
  if (!response.ok) return null
  return response.json().catch(() => ({}))
}

export async function getSession() {
  const response = await fetch('/api/auth/session', { credentials: 'include', cache: 'no-store' })
  if (!response.ok) return null
  return response.json().catch(() => null)
}

export async function logout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
}
