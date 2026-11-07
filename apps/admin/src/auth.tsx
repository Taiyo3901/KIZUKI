/**
 * Admin sign-in.
 * firebase mode: Google account (the custom claims role / siteIds are set on the server side).
 * dev mode: a fake admin accepted by the local API's X-Dev-User header.
 */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { config } from "./config";

export interface AdminUser {
  uid: string;
  name: string;
}

interface AuthState {
  user: AdminUser | null;
  ready: boolean;
  signInGoogle: () => Promise<void>;
  signInDev: () => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);
const DEV_KEY = "kizuki-admin-dev";
const DEV_USER: AdminUser = { uid: "admin-dev", name: "開発用の管理者" };

type AuthModule = typeof import("firebase/auth");
let fbPromise: Promise<{ mod: AuthModule; auth: import("firebase/auth").Auth }> | null = null;

function firebase() {
  fbPromise ??= (async () => {
    const [{ initializeApp }, mod] = await Promise.all([import("firebase/app"), import("firebase/auth")]);
    const f = config.firebase;
    const auth = mod.getAuth(initializeApp({ apiKey: f.apiKey, authDomain: f.authDomain, projectId: f.projectId, appId: f.appId }));
    return { mod, auth };
  })();
  return fbPromise;
}

/** Headers for API calls. */
export async function authHeaders(): Promise<Record<string, string>> {
  if (config.authMode === "dev") return { "X-Dev-User": `admin:admin-dev:${config.devSiteIds.join(",")}` };
  const { auth } = await firebase();
  if (!auth.currentUser) throw new Error("not signed in");
  return { Authorization: `Bearer ${await auth.currentUser.getIdToken()}` };
}

function devSignedIn(): boolean {
  try {
    return sessionStorage.getItem(DEV_KEY) === "1";
  } catch {
    return false;
  }
}

function setDevSignedIn(on: boolean) {
  try {
    if (on) sessionStorage.setItem(DEV_KEY, "1");
    else sessionStorage.removeItem(DEV_KEY);
  } catch {
    /* storage may be unavailable; the session then lasts until reload */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (config.authMode === "dev") {
      if (devSignedIn()) setUser(DEV_USER);
      setReady(true);
      return;
    }
    let off = () => {};
    void firebase().then(({ mod, auth }) => {
      off = mod.onAuthStateChanged(auth, (u) => {
        setUser(u ? { uid: u.uid, name: u.displayName ?? u.email ?? u.uid } : null);
        setReady(true);
      });
    });
    return () => off();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      signInDev: () => {
        setDevSignedIn(true);
        setUser(DEV_USER);
      },
      signInGoogle: async () => {
        const { mod, auth } = await firebase();
        await mod.signInWithPopup(auth, new mod.GoogleAuthProvider());
      },
      signOut: async () => {
        if (config.authMode === "dev") {
          setDevSignedIn(false);
          setUser(null);
        } else {
          const { mod, auth } = await firebase();
          await mod.signOut(auth);
        }
      },
    }),
    [user, ready],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}
