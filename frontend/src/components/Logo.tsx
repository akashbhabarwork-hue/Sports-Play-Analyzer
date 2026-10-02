// Original mark: a rounded tile with a forward "play" arrow made of two motion strokes.
// No real crests, league marks or likenesses (brief).
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#logo-g)" />
      <path d="M12 9.5 22.5 16 12 22.5Z" fill="#fff" />
      <path d="M6.5 12h3M5 16h4.5M6.5 20h3" stroke="#c7d2fe" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="logo">
      <LogoMark />
      {!compact && <span className="logo-word">Sports Play Analyzer</span>}
    </span>
  )
}
