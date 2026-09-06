import { cn } from '@/lib/utils'

/**
 * Text — eliminates font-[Alexandria,sans-serif] repetition everywhere.
 * The font is already set on body, so this component is mainly for
 * semantic size/weight/color variants.
 */

const SIZE = {
  xs:  'text-[11.5px]',
  sm:  'text-[12.5px]',
  md:  'text-[13px]',
  base:'text-[13.5px]',
  lg:  'text-[15px]',
  xl:  'text-[16px]',
  '2xl':'text-[22px]',
}

const WEIGHT = {
  normal:    'font-normal',
  medium:    'font-medium',
  semibold:  'font-semibold',
  bold:      'font-bold',
}

const COLOR = {
  ink:    'text-ink',
  muted:  'text-ink-muted',
  faint:  'text-ink-faint',
  navy:   'text-brand-navy',
  gold:   'text-brand-gold',
  white:  'text-white',
  success:'text-success',
  danger: 'text-danger',
  warning:'text-warning',
}

export function Text({
  as: Tag = 'span',
  size = 'md',
  weight = 'normal',
  color = 'ink',
  className,
  children,
  ...props
}) {
  return (
    <Tag
      className={cn(
        SIZE[size]   ?? SIZE.md,
        WEIGHT[weight] ?? WEIGHT.normal,
        COLOR[color] ?? COLOR.ink,
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  )
}
