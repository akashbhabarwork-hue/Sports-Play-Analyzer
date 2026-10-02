// Original abstract illustration: a top-down pitch, player dots with motion trails and a soft
// heat glow. No real teams, crests, players or footage (brief).
export function HeroArt() {
  const players: [number, number, string][] = [
    [120, 90, 'var(--team-a)'], [190, 150, 'var(--team-a)'], [150, 230, 'var(--team-a)'],
    [330, 110, 'var(--team-b)'], [300, 200, 'var(--team-b)'], [390, 250, 'var(--team-b)'],
  ]  // prettier-ignore
  return (
    <svg className="hero-art" viewBox="0 0 520 340" role="img" aria-label="Abstract pitch with tracked players and a heatmap glow">
      <defs>
        <radialGradient id="heat" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#f43f5e" stopOpacity="0.75" />
          <stop offset="0.45" stopColor="#f59e0b" stopOpacity="0.45" />
          <stop offset="1" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="pitch" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#13204a" />
          <stop offset="1" stopColor="#0e1736" />
        </linearGradient>
      </defs>
      <rect x="10" y="10" width="500" height="320" rx="18" fill="url(#pitch)" stroke="#2b3a72" />
      <g fill="none" stroke="#3b4c8c" strokeWidth="2">
        <rect x="30" y="30" width="460" height="280" rx="6" />
        <line x1="260" y1="30" x2="260" y2="310" />
        <circle cx="260" cy="170" r="42" />
        <rect x="30" y="110" width="56" height="120" />
        <rect x="434" y="110" width="56" height="120" />
      </g>
      <ellipse cx="205" cy="175" rx="120" ry="80" fill="url(#heat)" />
      <ellipse cx="350" cy="190" rx="70" ry="55" fill="url(#heat)" opacity="0.7" />
      {players.map(([x, y, colour], i) => (
        <g key={i}>
          <path d={`M${x - 46} ${y + 18} Q ${x - 20} ${y + 22} ${x - 8} ${y + 4}`} stroke={colour} strokeOpacity="0.45" strokeWidth="3" fill="none" strokeLinecap="round" />
          <rect x={x - 10} y={y - 22} width="20" height="40" rx="4" fill="none" stroke={colour} strokeWidth="2.5" />
          <circle cx={x} cy={y} r="5" fill={colour} />
        </g>
      ))}
      <circle cx="232" cy="196" r="6" fill="var(--ball)" stroke="#fff" strokeWidth="1.5" />
    </svg>
  )
}
