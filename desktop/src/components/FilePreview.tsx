import { FileText, Film, Music, Archive, FileCode, Image } from 'lucide-react'

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'bmp', 'tiff', 'tif', 'svg', 'avif'])
const VIDEO_EXTS = new Set(['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', 'wmv', 'flv'])
const AUDIO_EXTS = new Set(['mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg', 'wma'])
const ARCHIVE_EXTS = new Set(['zip', 'rar', '7z', 'tar', 'gz', 'bz2'])
const CODE_EXTS = new Set(['js', 'ts', 'py', 'rb', 'go', 'rs', 'java', 'c', 'cpp', 'h', 'css', 'html', 'json', 'xml'])

export function pathToFileUrl(p: string): string {
  const fwd = p.replace(/\\/g, '/')
  return fwd.startsWith('/') ? `file://${fwd}` : `file:///${fwd}`
}

export function getExt(p: string): string {
  return p.split('.').pop()?.toLowerCase() ?? ''
}

export function isImagePath(p: string): boolean {
  return IMAGE_EXTS.has(getExt(p))
}

type Props = {
  path: string
  className?: string
}

export function FilePreview({ path, className = '' }: Props) {
  const ext = getExt(path)

  if (IMAGE_EXTS.has(ext)) {
    return (
      <img
        src={pathToFileUrl(path)}
        alt=""
        className={`object-cover ${className}`}
        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
        draggable={false}
      />
    )
  }

  if (VIDEO_EXTS.has(ext)) {
    return (
      <div className={`flex flex-col items-center justify-center gap-1 ${className}`}
        style={{ background: '#1a1a1d' }}>
        <Film size={22} style={{ color: '#7B61FF' }} />
        <span style={{ color: '#8A8A96', fontSize: 9, fontFamily: 'DM Mono' }}>{ext.toUpperCase()}</span>
      </div>
    )
  }

  if (AUDIO_EXTS.has(ext)) {
    return (
      <div className={`flex flex-col items-center justify-center gap-1 ${className}`}
        style={{ background: '#1a1a1d' }}>
        <Music size={22} style={{ color: '#22C55E' }} />
        <span style={{ color: '#8A8A96', fontSize: 9, fontFamily: 'DM Mono' }}>{ext.toUpperCase()}</span>
      </div>
    )
  }

  if (ARCHIVE_EXTS.has(ext)) {
    return (
      <div className={`flex flex-col items-center justify-center gap-1 ${className}`}
        style={{ background: '#1a1a1d' }}>
        <Archive size={22} style={{ color: '#F59E0B' }} />
        <span style={{ color: '#8A8A96', fontSize: 9, fontFamily: 'DM Mono' }}>{ext.toUpperCase()}</span>
      </div>
    )
  }

  if (CODE_EXTS.has(ext)) {
    return (
      <div className={`flex flex-col items-center justify-center gap-1 ${className}`}
        style={{ background: '#1a1a1d' }}>
        <FileCode size={22} style={{ color: '#7B61FF' }} />
        <span style={{ color: '#8A8A96', fontSize: 9, fontFamily: 'DM Mono' }}>{ext.toUpperCase()}</span>
      </div>
    )
  }

  if (ext === 'pdf') {
    return (
      <div className={`flex flex-col items-center justify-center gap-1 ${className}`}
        style={{ background: '#1a1a1d' }}>
        <FileText size={22} style={{ color: '#FF4D4D' }} />
        <span style={{ color: '#8A8A96', fontSize: 9, fontFamily: 'DM Mono' }}>PDF</span>
      </div>
    )
  }

  return (
    <div className={`flex flex-col items-center justify-center gap-1 ${className}`}
      style={{ background: '#1a1a1d' }}>
      <Image size={22} style={{ color: '#8A8A96' }} />
      <span style={{ color: '#8A8A96', fontSize: 9, fontFamily: 'DM Mono' }}>{ext ? ext.toUpperCase() : 'FILE'}</span>
    </div>
  )
}
