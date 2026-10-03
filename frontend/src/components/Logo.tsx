import { brand } from '../assets/brand'

// Brand mark from the owner's asset sheet; the name stays live text so it is crisp, readable
// in both themes and read out by screen readers.
export function LogoMark({ size = 32 }: { size?: number }) {
  return <img className="logo-mark" src={brand.logoMark} width={size} height={size} alt="" />
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="logo">
      <LogoMark />
      {!compact && <span className="logo-word">Sports Play Analyzer</span>}
    </span>
  )
}
