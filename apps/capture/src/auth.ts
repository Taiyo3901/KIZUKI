/** Request headers that identify the tourist: anonymous Firebase user (+ App Check), or a fake id in dev mode. */
import { config } from "./config";

let firebaseReady: Promise<{ getToken: () => Promise<string>; getAppCheck: () => Promise<string> }> | null = null;

function initFirebase() {
  firebaseReady ??= (async () => {
    const [{ initializeApp }, { getAuth, signInAnonymously }, { initializeAppCheck, ReCaptchaEnterpriseProvider, getToken }] =
      await Promise.all([import("firebase/app"), import("firebase/auth"), import("firebase/app-check")]);
    const f = config.firebase;
    const app = initializeApp({ apiKey: f.apiKey, authDomain: f.authDomain, projectId: f.projectId, appId: f.appId });
    // App Check only when a site key is configured (the API accepts requests without it while APP_CHECK=off)
    const appCheck = f.recaptchaSiteKey
      ? initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(f.recaptchaSiteKey), isTokenAutoRefreshEnabled: true })
      : null;
    const auth = getAuth(app);
    return {
      getToken: async () => {
        if (!auth.currentUser) await signInAnonymously(auth);
        return auth.currentUser!.getIdToken();
      },
      getAppCheck: async () => (appCheck ? (await getToken(appCheck)).token : ""),
    };
  })();
  return firebaseReady;
}

function devUid(): string {
  try {
    let uid = localStorage.getItem("kizuki-dev-uid");
    if (!uid) localStorage.setItem("kizuki-dev-uid", (uid = crypto.randomUUID().slice(0, 8)));
    return uid;
  } catch {
    return "dev-anon";
  }
}

export async function authHeaders(): Promise<Record<string, string>> {
  if (config.authMode === "dev") return { "X-Dev-User": `anon:${devUid()}` };
  const fb = await initFirebase();
  const appCheck = await fb.getAppCheck();
  return { Authorization: `Bearer ${await fb.getToken()}`, ...(appCheck ? { "X-Firebase-AppCheck": appCheck } : {}) };
}
