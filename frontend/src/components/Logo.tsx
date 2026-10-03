import { brand } from '../assets/brand'

const NAME = 'Sports Play Analyzer'

/** The brand mark alone (decorative: use it next to the product name in text). */
export function LogoMark({ size = 32 }: { size?: number }) {
  return <img className="logo-mark" src={brand.logoMark} width={size} height={size} alt="" />
}

/** The full wordmark. The image carries the name, so it is the accessible label. `onDark`
 *  forces the light-text version (the landing hero is always dark); otherwise it follows the
 *  system theme like the rest of the app. */
export function Logo({ onDark = false, height = 36 }: { onDark?: boolean; height?: number }) {
  const width = Math.round(height * (602 / 180)) // intrinsic aspect of the wordmark files
  if (onDark) {
    return <img className="logo" src={brand.logoDark} width={width} height={height} alt={NAME} />
  }
  return (
    <picture className="logo">
      <source srcSet={brand.logoDark} media="(prefers-color-scheme: dark)" />
      <img src={brand.logoLight} width={width} height={height} alt={NAME} />
    </picture>
  )
}
