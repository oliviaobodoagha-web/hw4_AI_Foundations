// Catalogue color names → swatch colors for the little color dots on product cards.
const SWATCH: Record<string, string> = {
  'navy blue': '#1c2a4a', navy: '#1c2a4a', 'royal blue': '#2a52be', blue: '#2f5fa7', 'light blue': '#8db8e6',
  white: '#ffffff', ivory: '#fbf7ea', cream: '#f3ead3',
  'heather gray': '#b9bbbe', gray: '#9a9da1', 'light gray': '#d5d7da', 'dark heather gray': '#5d6166',
  'charcoal gray': '#43474d', 'heather charcoal gray': '#4d5157', 'dark heather charcoal': '#3b3e43',
  black: '#111111', red: '#b8232f', yellow: '#f2c230', gold: '#c9a227', green: '#2e7d4f', 'dusty coral': '#d9897a',
  multicolor: 'conic-gradient(#b8232f, #f2c230, #2e7d4f, #2f5fa7, #b8232f)',
}

export function swatchFor(color: string): string {
  return SWATCH[color.toLowerCase()] ?? '#cccccc'
}
