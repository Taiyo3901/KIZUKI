import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { listDetections } from "./api";
import { AuthProvider, useAuth } from "./auth";
import DetectionPage from "./pages/DetectionPage";
import LayoutPage from "./pages/LayoutPage";
import LoginPage from "./pages/LoginPage";
import MapPage from "./pages/MapPage";
import QueuePage from "./pages/QueuePage";
import ReferencesPage from "./pages/ReferencesPage";
import SpotNewPage from "./pages/SpotNewPage";

/** Number of detections waiting for a human, shown on the nav so the queue is never out of sight. */
function useWaitingCount(): number | null {
  const [n, setN] = useState<number | null>(null);
  const { pathname } = useLocation(); // refresh after every navigation, e.g. after confirming a decision
  useEffect(() => {
    listDetections({ status: "needs_review" }).then((r) => setN(r.length)).catch(() => setN(null));
  }, [pathname]);
  return n;
}

function Shell() {
  const { user, ready, signOut } = useAuth();
  const waiting = useWaitingCount();
  if (!ready) return <p className="pad">読み込み中…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <>
      <header className="bar">
        <span className="brand"><span className="brand-mark" aria-hidden />文化財見守り</span>
        <nav aria-label="メイン">
          <NavLink to="/map">地図</NavLink>
          <NavLink to="/queue">
            要確認
            {waiting ? <span className="count" aria-label={`${waiting}件`}>{waiting}</span> : null}
          </NavLink>
        </nav>
        <span className="grow" />
        <button onClick={() => void signOut()}>ログアウト</button>
      </header>
      <Outlet />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Shell />}>
            <Route path="/map" element={<MapPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/detections/:id" element={<DetectionPage />} />
            <Route path="/spots/new" element={<SpotNewPage />} />
            <Route path="/spots/:id/layout" element={<LayoutPage />} />
            <Route path="/spots/:id/references" element={<ReferencesPage />} />
            <Route path="*" element={<Navigate to="/map" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
