'use client'
import { Suspense, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthLayout } from '@/components/auth/AuthLayout'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useLang } from '@/context/LanguageContext'
import { requestOtp, verifyOtp } from '@/features/auth/services/authService'

function VerifyOtpContent() {
  const { t } = useLang(); const isRtl = t.dir === 'rtl'; const router = useRouter(); const params = useSearchParams()
  const email = params.get('email') || ''; const [code, setCode] = useState(''); const [loading, setLoading] = useState(false); const [resending, setResending] = useState(false); const [error, setError] = useState(''); const [seconds, setSeconds] = useState(0); const inputRef = useRef(null)
  useEffect(() => { inputRef.current?.focus() }, [])
  useEffect(() => { if (!seconds) return; const timer = setInterval(() => setSeconds(v => v - 1), 1000); return () => clearInterval(timer) }, [seconds])
  const submit = async e => { e.preventDefault(); if (code.length !== 6) return; setLoading(true); setError(''); try { await verifyOtp(email, code); router.replace(new URLSearchParams(window.location.search).get('next') || '/dashboard') } catch (e) { setError(e.message) } finally { setLoading(false) } }
  const resend = async () => { if (seconds || !email) return; setResending(true); setError(''); try { await requestOtp(email); setSeconds(60) } catch (e) { setError(e.message) } finally { setResending(false) } }
  return <AuthLayout>
    <div style={{ marginBottom: 36, textAlign: isRtl ? 'right' : 'left' }}>
      <h2 style={{ fontSize: 30, fontWeight: 700, color: 'var(--color-ink)', lineHeight: 1.2, marginBottom: 10, fontFamily: 'var(--font-family-base)' }}>{t.otpTitle}</h2>
      <p style={{ fontSize: 15, color: 'var(--color-ink-subtle)', lineHeight: 1.8, fontFamily: 'var(--font-family-base)', margin: 0 }}>{t.otpSub} <strong style={{ color: 'var(--color-brand-navy)' }}>{email}</strong></p>
    </div>
    {error && <div role="alert" style={{ marginBottom: 18, padding: '11px 14px', borderRadius: 12, background: 'var(--color-danger-bg)', color: 'var(--color-danger)', fontSize: 13, fontFamily: 'var(--font-family-base)', textAlign: isRtl ? 'right' : 'left' }}>{error}</div>}
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label htmlFor="otp" style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-ink)', fontFamily: 'var(--font-family-base)' }}>{t.otpLabel}</label>
        <input id="otp" ref={inputRef} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="••••••" style={{ width: '100%', boxSizing: 'border-box', border: `1.5px solid ${error ? 'var(--color-danger)' : 'var(--color-border-strong)'}`, borderRadius: 12, padding: '14px 16px', fontSize: 22, letterSpacing: '0.35em', textAlign: 'center', color: 'var(--color-ink)', background: 'var(--color-surface-input)', outline: 'none', fontFamily: 'var(--font-family-base)' }} />
      </div>
      <Button type="submit" size="full" disabled={loading || code.length !== 6}>{loading ? <><Spinner size={16} /> {t.verifyingOtp}</> : t.verifyBtn}</Button>
      <div style={{ textAlign: 'center', fontFamily: 'var(--font-family-base)', fontSize: 13.5, color: 'var(--color-ink-subtle)' }}>
        <button type="button" onClick={resend} disabled={resending || seconds > 0} style={{ border: 0, background: 'transparent', color: seconds ? 'var(--color-ink-faint)' : 'var(--color-brand-navy)', fontWeight: 600, cursor: seconds ? 'default' : 'pointer', fontFamily: 'inherit' }}>{resending ? t.sendingOtp : seconds ? `${t.resendOtp} (${seconds})` : t.resendOtp}</button>
        <span style={{ margin: '0 8px' }}>·</span><button type="button" onClick={() => router.push('/login')} style={{ border: 0, background: 'transparent', color: 'var(--color-ink-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>{t.changeEmail}</button>
      </div>
    </form>
  </AuthLayout>
}
export default function VerifyOtpPage() {
  return (
    <Suspense fallback={null}>
      <VerifyOtpContent />
    </Suspense>
  )
}