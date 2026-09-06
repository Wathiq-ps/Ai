import Image from 'next/image'
import { cn } from '@/lib/utils'

/**
 * WathiqLogo — single centralized logo component.
 * variant:    'full' | 'icon'
 * size:       'xs' | 'sm' | 'md' | 'lg'
 * responsive: shows full on ≥769px, icon on <769px via CSS classes
 */
export function WathiqLogo({ variant = 'full', size = 'md', responsive = false, className }) {
  const iconDim = { xs: 22, sm: 26, md: 32, lg: 44 }[size] ?? 32
  const fullH   = { xs: 20, sm: 24, md: 28, lg: 38 }[size] ?? 28
  const fullW   = Math.round(fullH * 3.4)

  if (responsive) return (
    <>
      <span className={cn('logo-full', className)}>
        <Image src="/logo-official.svg" alt="وثيق – Wathiq" width={fullW} height={fullH} priority style={{ display:'block', objectFit:'contain' }} />
      </span>
      <span className={cn('logo-icon', className)}>
        <Image src="/logo-hand-white.svg" alt="وثيق" width={iconDim} height={iconDim} priority style={{ display:'block', objectFit:'contain' }} />
      </span>
    </>
  )

  if (variant === 'icon') return (
    <Image src="/logo-hand-white.svg" alt="وثيق" width={iconDim} height={iconDim} priority style={{ display:'block', objectFit:'contain' }} className={className} />
  )

  return (
    <Image src="/logo-official.svg" alt="وثيق – Wathiq" width={fullW} height={fullH} priority style={{ display:'block', objectFit:'contain' }} className={className} />
  )
}
