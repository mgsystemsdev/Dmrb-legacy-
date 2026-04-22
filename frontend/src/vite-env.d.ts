/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Full API origin including /api path, e.g. https://dmrb.up.railway.app/api */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
