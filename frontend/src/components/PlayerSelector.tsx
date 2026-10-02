import type { Option } from '../logic/heatmap'

/** Native <select>: keyboard and screen-reader friendly without extra code. */
export function PlayerSelector({
  options,
  value,
  onChange,
}: {
  options: Option[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="field inline">
      <span>Show heatmap for</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}
