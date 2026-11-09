const env = import.meta.env;

export const config = {
  apiBase: (env.VITE_API_BASE as string | undefined) ?? "http://localhost:8080",
  authMode: ((env.VITE_AUTH_MODE as string | undefined) ?? "dev") as "dev" | "firebase" | "open",
  devSiteIds: ((env.VITE_DEV_SITE_IDS as string | undefined) ?? "site1").split(",").filter(Boolean),
  mapsKey: (env.VITE_GOOGLE_MAPS_API_KEY as string | undefined) ?? "",
  firebase: {
    apiKey: env.VITE_FIREBASE_API_KEY as string | undefined,
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
    projectId: env.VITE_FIREBASE_PROJECT_ID as string | undefined,
    appId: env.VITE_FIREBASE_APP_ID as string | undefined,
  },
};
