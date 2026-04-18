import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";
import { RequireAuth } from "./components/RequireAuth";
import { Sidebar } from "./components/Sidebar";
import { AdminPage } from "./pages/AdminPage";
import { AiAgentPage } from "./pages/AiAgentPage";
import { BoardPage } from "./pages/BoardPage";
import { FlagBridgePage } from "./pages/FlagBridgePage";
import { LoginPage } from "./pages/LoginPage";
import { MorningWorkflowPage } from "./pages/MorningWorkflowPage";
import { OperationsSchedulePage } from "./pages/OperationsSchedulePage";
import { ReportOperationsPage } from "./pages/ReportOperationsPage";
import { RiskRadarPage } from "./pages/RiskRadarPage";
import { TurnoverDetailPage } from "./pages/TurnoverDetailPage";

function AppLayout() {
  return (
    <div className="min-h-screen bg-canvas text-text lg:grid lg:grid-cols-[280px_minmax(0,1fr)]">
      <Sidebar />
      <main className="min-w-0">
        <Outlet />
      </main>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/board" replace /> },
      { path: "/morning-workflow", element: <MorningWorkflowPage /> },
      { path: "/board", element: <BoardPage /> },
      { path: "/flag-bridge", element: <FlagBridgePage /> },
      { path: "/risk-radar", element: <RiskRadarPage /> },
      { path: "/operations-schedule", element: <OperationsSchedulePage /> },
      { path: "/report-operations", element: <ReportOperationsPage /> },
      { path: "/unit/:turnoverId", element: <TurnoverDetailPage /> },
      { path: "/turnovers/:turnoverId", element: <TurnoverDetailPage /> },
      { path: "/ai-agent", element: <AiAgentPage /> },
      { path: "/admin", element: <AdminPage /> },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/board" replace />,
  },
]);
