/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ROCKETRIDE_URI?: string
  readonly VITE_ROCKETRIDE_AUTH?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
