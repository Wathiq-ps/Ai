'use client'
import { useState } from 'react'
import { cn }       from '@/lib/utils'

export function Input({ label, error, iconStart, iconEnd, onIconEndClick, className, ...props }) {
  const [focused, setFocused] = useState(false)

  const inputStyle = {
    width: '100%',
    border: `1.5px solid ${error ? 'var(--color-danger)' : focused ? 'var(--color-brand-navy)' : 'var(--color-border-strong)'}`,
    borderRadius: 12,
    padding: '13px 16px',
    paddingInlineEnd: iconStart ? 48 : 16,
    paddingInlineStart: iconEnd ? 48 : 16,
    fontSize: 14,
    color: 'var(--color-ink)',
    background: error ? 'var(--color-surface-error)' : focused ? 'var(--color-white)' : 'var(--color-surface-input)',
    fontFamily: 'var(--font-family-base)',
    outline: 'none',
    boxShadow: focused ? `0 0 0 3px rgba(0,35,102,${error ? 0 : 0.10})` : error ? '0 0 0 3px rgba(229,62,62,0.12)' : 'none',
    transition: 'all 150ms',
    boxSizing: 'border-box',
  }

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 7 }}>
      {label && (
        <label style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-ink)', fontFamily: 'var(--font-family-base)' }}>
          {label}
        </label>
      )}
      <div style={{ position: 'relative' }}>
        {iconStart && (
          <span style={{ position: 'absolute', insetBlockStart: 0, insetBlockEnd: 0, insetInlineEnd: 14, display: 'flex', alignItems: 'center', color: 'var(--color-ink-faint)', pointerEvents: 'none' }}>
            {iconStart}
          </span>
        )}
        <input
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={inputStyle}
          className={cn('placeholder:text-ink-placeholder', className)}
          {...props}
        />
        {iconEnd && (
          <button
            type="button"
            onClick={onIconEndClick}
            style={{ position: 'absolute', insetBlockStart: 0, insetBlockEnd: 0, insetInlineStart: 14, display: 'flex', alignItems: 'center', color: 'var(--color-ink-faint)', background: 'transparent', border: 'none', cursor: 'pointer', transition: 'color 150ms' }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--color-ink-muted)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--color-ink-faint)'}
          >
            {iconEnd}
          </button>
        )}
      </div>
      {error && (
        <p role="alert" style={{ fontSize: 12, color: 'var(--color-danger)', fontFamily: 'var(--font-family-base)', margin: 0 }}>
          {error}
        </p>
      )}
    </div>
  )
}
