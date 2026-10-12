import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built straight into the Python package, so `uvicorn hostelswap.api:app`
// serves the UI with no Node toolchain present. `base` has to match the
// path FastAPI mounts those files under.
export default defineConfig({
  plugins: [react()],
  base: "/webui/",
  build: {
    outDir: "../code/hostelswap/webui",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  server: {
    // `npm run dev` proxies the API to a local uvicorn, so the dev server
    // and the real backend agree on cookies and paths.
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/assets": "http://127.0.0.1:8000",
    },
  },
});
