// Products featured in the carousels: a mix of types, all in stock in every size.
export const FEATURED_IDS = [
  'basic-hoodie-big-yale',
  '2025-yale-vs-harvard-t-shirt',
  'branford-1-4-zip',
  'super-heavyweight-crewneck-arched-yale-crest',
  'divinity-school-fleece-sweater',
  'yale-dad-hoodie',
  'tri-blend-sports-football-t-shirt',
  'hype-and-vice-yale-university-offside-crewneck',
  'yale-law-school-1-4-zip',
  'champion-full-zip-hood',
  'yale-mom-crewneck',
  'grace-hopper-logo-t-shirt',
]

export function pickFeatured<T extends { product_id: string }>(products: T[]): T[] {
  const byId = new Map(products.map((p) => [p.product_id, p]))
  const picks = FEATURED_IDS.map((id) => byId.get(id)).filter((p): p is T => p !== undefined)
  return picks.length ? picks : products.slice(0, 12)
}
