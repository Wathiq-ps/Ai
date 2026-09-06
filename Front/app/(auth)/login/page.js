'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { Mail } from 'lucide-react'
import { AuthLayout } from '@/components/auth/AuthLayout'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useLang } from '@/context/LanguageContext'
import { requestOtp } from '@/features/auth/services/authService'

export default function LoginPage() {
  const { t } = useLang(); const router = useRouter(); const isRtl = t.dir === 'rtl'
  const [loading, setLoading] = useState(false); const [apiError, setApiError] = useState('')
  const { register, handleSubmit, formState: { errors } } = useForm()
  const onSubmit = async ({ email }) => {
    setLoading(true); setApiError('')
    try { await requestOtp(email); router.push(`/verify-otp?email=${encodeURIComponent(email)}`) }
    catch (e) { setApiError(e.message) } finally { setLoading(false) }
  }
  return <AuthLayout>
    <div style={{ marginBottom: 36, textAlign: isRtl ? 'right' : 'left' }}>
      <h2 style={{ fontSize: 30, fontWeight: 700, color: 'var(--color-ink)', lineHeight: 1.2, marginBottom: 10, fontFamily: 'var(--font-family-base)' }}>{t.loginTitle}</h2>
      <p style={{ fontSize: 15, color: 'var(--color-ink-subtle)', fontFamily: 'var(--font-family-base)' }}>{t.loginSub}</p>
    </div>
    {apiError && <div role="alert" style={{ marginBottom: 18, padding: '11px 14px', borderRadius: 12, background: 'var(--color-danger-bg)', color: 'var(--color-danger)', fontSize: 13, fontFamily: 'var(--font-family-base)', textAlign: isRtl ? 'right' : 'left' }}>{apiError}</div>}
    <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <Input label={t.email} type="email" placeholder={t.emailPh} iconStart={<Mail size={17} />} error={errors.email?.message} {...register('email', { required: isRtl ? 'البريد مطلوب' : 'Email is required', pattern: { value: /^\S+@\S+\.\S+$/, message: isRtl ? 'بريد غير صحيح' : 'Invalid email' } })} />
      <div style={{ marginTop: 6 }}><Button type="submit" size="full" disabled={loading}>{loading ? <><Spinner size={16} /> {t.sendingOtp}</> : t.continueBtn}</Button></div>
    </form>
  </AuthLayout>
}
