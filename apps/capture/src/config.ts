/** Settings from environment variables (CLAUDE.md section 7). Thresholds are config, not constants. */
const env = import.meta.env;

export const config = {
  apiBase: (env.VITE_API_BASE as string | undefined) ?? "http://localhost:8080",
  authMode: ((env.VITE_AUTH_MODE as string | undefined) ?? "dev") as "dev" | "firebase",
  autoShutterScore: Number(env.VITE_AUTO_SHUTTER_SCORE ?? 0.8),
  autoShutterHoldMs: Number(env.VITE_AUTO_SHUTTER_HOLD_MS ?? 1200),
  /** Farther than this from the spot, the visitor gets a gentle notice (never blocked). CLAUDE.md leaves the value open. */
  nearSpotM: Number(env.VITE_NEAR_SPOT_M ?? 100),
  maxUploadEdgePx: Number(env.VITE_MAX_UPLOAD_EDGE_PX ?? 2048),
  firebase: {
    apiKey: env.VITE_FIREBASE_API_KEY as string | undefined,
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
    projectId: env.VITE_FIREBASE_PROJECT_ID as string | undefined,
    appId: env.VITE_FIREBASE_APP_ID as string | undefined,
    recaptchaSiteKey: env.VITE_RECAPTCHA_ENTERPRISE_SITE_KEY as string | undefined,
  },
};
