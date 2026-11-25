import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { LiveTriagePage } from "./pages/LiveTriagePage";
import { OpsPage } from "./pages/OpsPage";
import { PolicyPage } from "./pages/PolicyPage";
import { QueuePage } from "./pages/QueuePage";
import { TicketsPage } from "./pages/TicketsPage";
import { DemoProvider } from "./state/DemoStore";

export default function App() {
  return (
    <DemoProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<LiveTriagePage />} />
            <Route path="tickets" element={<TicketsPage />} />
            <Route path="tickets/:sysId" element={<TicketsPage />} />
            <Route path="queue" element={<QueuePage />} />
            <Route path="ops" element={<OpsPage />} />
            <Route path="policy" element={<PolicyPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DemoProvider>
  );
}
