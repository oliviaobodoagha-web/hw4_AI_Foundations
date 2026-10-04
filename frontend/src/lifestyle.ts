// Lifestyle photography from Unsplash (free license: https://unsplash.com/license).
// Images load straight from Unsplash's CDN (hotlinked, as Unsplash asks) and every photo is credited.

export interface Photo {
  id: string // Unsplash image id (the part after "photo-")
  alt: string
  credit: string
  page: string // the photo's Unsplash page, for the credit link
}

export const PHOTOS = {
  harkness: { id: '1774214458548-06dc5dc5237b', alt: 'Gothic stone tower on Yale’s campus', credit: 'Bee', page: 'https://unsplash.com/photos/YqZBXXCTsOA' },
  lawn: { id: '1730703896322-bcd7df25c397', alt: 'A Yale library across a green lawn under summer clouds', credit: 'Bee', page: 'https://unsplash.com/photos/lfBv5_y5zw8' },
  gate: { id: '1784076641581-54d5a10557fc', alt: 'Ornate iron gate on campus after a snowfall', credit: 'Jerome Cha', page: 'https://unsplash.com/photos/EH8kSx0bUMY' },
  sunset: { id: '1719931940737-e188b149d5e8', alt: 'Sunset over a Yale residential college', credit: 'Ethan Yoo', page: 'https://unsplash.com/photos/vNYG-Bn4kgs' },
  sails: { id: '1777404380697-6b0725b148a7', alt: 'Two sailors trimming the sails on a sunny day', credit: 'Margo Evardson', page: 'https://unsplash.com/photos/hAK4VakkqQA' },
  harbor: { id: '1751912840075-814a53ffc2d0', alt: 'Sailboats moored in a New England harbor', credit: 'Peregrine Photography', page: 'https://unsplash.com/photos/n-ZQEwlUOvk' },
  lighthouse: { id: '1654615348054-b54ee8ff158d', alt: 'A lighthouse at sunset', credit: 'Keenan Shepard', page: 'https://unsplash.com/photos/rc3k-IMqNtk' },
  autumn: { id: '1780817612650-4b4569f0a00b', alt: 'An old brick building framed by autumn leaves', credit: 'Cloris Ying', page: 'https://unsplash.com/photos/M9VhxlGuyRw' },
} satisfies Record<string, Photo>

export function photoUrl(photo: Photo, width: number, height?: number): string {
  const size = height ? `&h=${height}` : ''
  return `https://images.unsplash.com/photo-${photo.id}?w=${width}${size}&q=75&auto=format&fit=crop`
}

// ---------- Models wearing our pieces (Problem 10) ----------
// Real Unsplash model photos in a plain garment of the same type and color as one of our
// products, with that product's real print laid on the chest (cut from the product photo by
// backend/prepare_images.py). Positions are percentages of the 900×1125 crop below.

export interface ModelLook {
  photo: Photo
  productId: string // the real product being shown
  setting: string
  print: {
    left: number // % from the left of the photo
    top: number // % from the top
    width: number // % of the photo's width
    rotate: number // degrees, to follow the body
    blend: 'normal' | 'multiply' // multiply lets fabric folds show through colored ink
    opacity: number
  }
}

export const MODEL_CROP = { width: 900, height: 1125 }

export const MODEL_LOOKS: ModelLook[] = [
  {
    photo: { id: '1711964429491-a8200d660b6d', alt: 'A man in a navy YALE hoodie sitting outdoors on a sunny day', credit: 'Mushvig Niftaliyev', page: 'https://unsplash.com/photos/qHcuInNL-lM' },
    productId: 'basic-hoodie-big-yale',
    setting: 'Saturday in the sun',
    print: { left: 33.5, top: 47, width: 37, rotate: -3, blend: 'normal', opacity: 0.9 },
  },
  {
    photo: { id: '1716393810972-0014eff53cab', alt: 'A woman in a heather-gray quarter-zip walking along a wooded path', credit: 'Rydale Clothing', page: 'https://unsplash.com/photos/T7vd6sqJ0lg' },
    productId: 'benjamin-franklin-1-4-zip',
    setting: 'A walk in the woods',
    print: { left: 71, top: 39.5, width: 6, rotate: 4, blend: 'multiply', opacity: 0.95 },
  },
  {
    photo: { id: '1771477126784-19e5372cea62', alt: 'A woman in a navy YALE BASEBALL crewneck and sunglasses against a sunlit wall', credit: 'Trương Tuyết Ly', page: 'https://unsplash.com/photos/gp349m3e8zc' },
    productId: 'baseball-left-chest-crewneck',
    setting: 'Off to the game',
    print: { left: 69, top: 47.5, width: 12, rotate: -2, blend: 'normal', opacity: 0.88 },
  },
  {
    photo: { id: '1692558588261-124d6c60f872', alt: 'A smiling woman in a gray YALE bulldog crewneck by the river', credit: 'Polina Shirokova', page: 'https://unsplash.com/photos/cUJGaMNfqzQ' },
    productId: 'super-heavyweight-crewneck-arched-yale-crest',
    setting: 'Golden hour by the water',
    print: { left: 62.5, top: 59, width: 19, rotate: 6, blend: 'multiply', opacity: 0.9 },
  },
  {
    photo: { id: '1601663494865-259764d7bf88', alt: 'A smiling woman in a gray YALE crewneck on the beach at dusk', credit: 'Marcelina Pawlikowska', page: 'https://unsplash.com/photos/58OB2jCMieU' },
    productId: 'champion-reverse-weave-crewneck',
    setting: 'By the shore',
    print: { left: 40.5, top: 58.5, width: 19, rotate: 0, blend: 'multiply', opacity: 0.95 },
  },
]

export function modelPhotoUrl(look: ModelLook): string {
  // Always the same crop, so the print positions above line up at any display size.
  return `https://images.unsplash.com/photo-${look.photo.id}?w=${MODEL_CROP.width}&h=${MODEL_CROP.height}&fit=crop&q=75&auto=format`
}
