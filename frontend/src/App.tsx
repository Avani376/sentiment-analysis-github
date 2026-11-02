import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import { AuthGate } from "./components/Auth";
import { Layout } from "./components/Layout";
import { AnalyzerPage } from "./pages/AnalyzerPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { ModelsPage } from "./pages/ModelsPage";
import { EmotionsPage } from "./pages/EmotionsPage";
import { AspectsPage } from "./pages/AspectsPage";
import { TopicsPage } from "./pages/TopicsPage";
import { InsightsPage } from "./pages/InsightsPage";
import { OverviewPage } from "./pages/OverviewPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AuthGate>
            <Routes>
              <Route element={<Layout />} path="/">
                <Route index element={<OverviewPage />} />
                <Route path="analyze" element={<AnalyzerPage />} />
                <Route path="explorer" element={<ExplorerPage />} />
                <Route path="models" element={<ModelsPage />} />
              <Route path="emotions" element={<EmotionsPage />} />
              <Route path="aspects" element={<AspectsPage />} />
              <Route path="topics" element={<TopicsPage />} />
              <Route path="insights" element={<InsightsPage />} />
                <Route path="*" element={<Navigate replace to="/" />} />
              </Route>
            </Routes>
          </AuthGate>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
