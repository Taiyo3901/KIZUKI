import { BrowserRouter, Route, Routes } from "react-router-dom";
import CapturePage from "./pages/CapturePage";
import DonePage from "./pages/DonePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/capture/:spotId" element={<CapturePage />} />
        <Route path="/done" element={<DonePage />} />
        <Route path="*" element={<main className="center"><p>QRコードから開いてください</p></main>} />
      </Routes>
    </BrowserRouter>
  );
}
