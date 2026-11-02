import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// In dev, `npm run dev` proxies API calls to a local PocketBase (scripts/dev.sh
// starts one on :8090). In production PocketBase serves the built files itself.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8090",
      "/_": "http://127.0.0.1:8090",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
