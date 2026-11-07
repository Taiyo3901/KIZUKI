import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const shared = fileURLToPath(new URL("../../shared/schemas", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@shared": shared } },
  server: { port: 5174, fs: { allow: ["../.."] } },
  test: { environment: "node" },
});
