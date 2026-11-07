import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { config } from "../config";

export default function LoginPage() {
  const { user, ready, signInGoogle, signInDev } = useAuth();
  const [error, setError] = useState("");
  if (ready && user) return <Navigate to="/map" replace />;

  return (
    <main className="login">
      <span className="brand-mark" aria-hidden />
      <h1>文化財見守り</h1>
      {config.authMode === "dev" ? (
        <button className="primary" onClick={signInDev}>開発用ログイン</button>
      ) : (
        <button className="primary" onClick={() => signInGoogle().catch(() => setError("ログインできませんでした"))}>
          Google アカウントでログイン
        </button>
      )}
      {error && <p role="alert" className="error">{error}</p>}
    </main>
  );
}
