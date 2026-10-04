import type { Photo } from '../lifestyle'

export default function PhotoCredit({ photo }: { photo: Photo }) {
  return (
    <a className="photo-credit" href={photo.page} target="_blank" rel="noreferrer">
      Photo: {photo.credit} / Unsplash
    </a>
  )
}
