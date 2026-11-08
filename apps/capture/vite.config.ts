import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

const shared = fileURLToPath(new URL("../../shared/schemas", import.meta.url));

// `npm run dev:phone` (mode "phone"): a phone's camera only works on https, so serve https with a self-signed
// certificate, listen on the LAN, and forward /api to the local API so the page never calls http from https.
export default defineConfig(({ mode }) => {
  const phone = mode === "phone";
  return {
    plugins: [
      react(),
      ...(phone ? [basicSsl()] : []),
      VitePWA({
        registerType: "autoUpdate",
        manifest: {
          name: "文化財見守り 撮影",
          short_name: "見守り撮影",
          lang: "ja",
          display: "standalone",
          start_url: "/",
          background_color: "#111111",
          theme_color: "#111111",
          icons: [
            { src: "icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          ],
        },
      }),
    ],
    resolve: { alias: { "@shared": shared } },
    server: {
      port: 5173,
      fs: { allow: ["../.."] },
      ...(phone
        ? { host: true, proxy: {
              "/api": {
                target: process.env.API_PROXY_TARGET ?? "http://localhost:8080",
                rewrite: (p: string) => p.replace(/^\/api/, ""),
                // tell the API which address the phone used, so image links it hands back work from the phone
                configure: (proxy) => {
                  proxy.on("proxyReq", (proxyReq, req) => {
                    // A phone talks HTTP/2, where the address arrives as ":authority" and there is no Host header.
                    const authority = req.headers.host ?? (req.headers[":authority"] as string | undefined);
                    if (authority) proxyReq.setHeader("x-dev-public-base", `https://${authority}/api`);
                  });
                },
              },
            },
          }
        : {}),
    },
    test: { environment: "node" },
  };
});
