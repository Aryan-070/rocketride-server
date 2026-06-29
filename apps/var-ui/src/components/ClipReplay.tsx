/* Copyright 2026 Aparavi Software AG. MIT License. */
import { useRef, useState } from 'react'
import { Upload, Gauge, Film } from 'lucide-react'

/** Left-column clip player: drop/upload a video, scrub, slow-mo. */
export default function ClipReplay({ onFile }: { onFile?: (f: File) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [src, setSrc] = useState<string | null>(null)
  const [slow, setSlow] = useState(false)
  const [drag, setDrag] = useState(false)

  function loadFile(file?: File | null) {
    if (!file) return
    setSrc(URL.createObjectURL(file))
    setSlow(false)
    onFile?.(file)
  }

  function toggleSlow() {
    const v = videoRef.current
    if (!v) return
    const next = !slow
    setSlow(next)
    v.playbackRate = next ? 0.35 : 1
  }

  return (
    <div
      className={`clip ${drag ? 'clip--drag' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        loadFile(e.dataTransfer.files?.[0])
      }}
    >
      {src ? (
        <>
          <video ref={videoRef} className="clip-video" src={src} controls loop playsInline />
          <button className={`pill ${slow ? 'pill--on' : ''}`} onClick={toggleSlow}>
            <Gauge size={14} /> {slow ? 'Slow-mo 0.35×' : 'Slow-mo'}
          </button>
        </>
      ) : (
        <label className="dropzone">
          <Film size={34} strokeWidth={1.4} />
          <div className="dropzone-title">Drop the match clip</div>
          <div className="dropzone-sub">
            <Upload size={13} /> or click to choose a video
          </div>
          <input
            type="file"
            accept="video/*"
            hidden
            onChange={(e) => loadFile(e.target.files?.[0])}
          />
        </label>
      )}
    </div>
  )
}
