import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Skeleton } from "@/components/feedback/states";
import { ApiError, api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { LoginPage } from "@/modules/auth/LoginPage";
import { DashboardPage } from "@/modules/dashboard/DashboardPage";
import { VerifyPage } from "@/modules/certificates/CertificatesPage";
import { AppShell } from "./AppShell";

const NeuralPage = lazy(() => import("@/modules/neural-visualizer/NeuralPage").then((m) => ({ default: m.NeuralPage })));
const CoursesPage = lazy(() => import("@/modules/courses/CoursesPage").then((m) => ({ default: m.CoursesPage })));
const CourseDetailPage = lazy(() => import("@/modules/courses/CoursesPage").then((m) => ({ default: m.CourseDetailPage })));
const PathsPage = lazy(() => import("@/modules/learning-paths/PathsPage").then((m) => ({ default: m.PathsPage })));
const AnalyticsPage = lazy(() => import("@/modules/analytics/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })));
const TutorPage = lazy(() => import("@/modules/ai-tutor/TutorPage").then((m) => ({ default: m.TutorPage })));
const AssessmentsPage = lazy(() => import("@/modules/assessments/AssessmentsPage").then((m) => ({ default: m.AssessmentsPage })));
const CertificatesPage = lazy(() => import("@/modules/certificates/CertificatesPage").then((m) => ({ default: m.CertificatesPage })));
const CommunityPage = lazy(() => import("@/modules/community/CommunityPage").then((m) => ({ default: m.CommunityPage })));
const SkillsPage = lazy(() => import("@/modules/skill-mastery/SkillsPage").then((m) => ({ default: m.SkillsPage })));
const RecommendationsPage = lazy(() => import("@/modules/recommendations/RecommendationsPage").then((m) => ({ default: m.RecommendationsPage })));
const AdminPage = lazy(() => import("@/modules/administration/AdminPages").then((m) => ({ default: m.AdminPage })));
const ActivityPage = lazy(() => import("@/modules/administration/AdminPages").then((m) => ({ default: m.ActivityPage })));
const SettingsPage = lazy(() => import("@/modules/administration/AdminPages").then((m) => ({ default: m.SettingsPage })));

const qc = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: (n, e) => !(e instanceof ApiError && [401, 403, 404].includes(e.status)) && n < 2 },
  },
});

/** Guardia de ruta: requiere sesión y (opcionalmente) un permiso. La autorización real está en el backend. */
function RoleGuard({ children, perm }: { children: ReactNode; perm?: string }) {
  const { accessToken, me, setMe, logout } = useAuth();
  const loc = useLocation();
  const q = useQuery({ queryKey: ["me", accessToken], queryFn: async () => { const m = await api("/auth/me"); setMe(m); return m; }, enabled: !!accessToken && !me, retry: false });
  if (!accessToken) return <Navigate to="/login" state={{ from: loc }} replace />;
  if (q.error) { logout(); return <Navigate to="/login" replace />; }
  if (!me) return <div className="p-8"><Skeleton className="h-[80vh]" /></div>;
  if (perm && !me.permissions.includes(perm)) return <div className="panel m-6 p-8 text-center"><p className="font-display text-lg">No tienes acceso a este módulo</p><p className="mt-1 text-mist">Pide a administración el permiso «{perm}».</p></div>;
  return <>{children}</>;
}

const page = (el: ReactNode, perm?: string) => <RoleGuard perm={perm}><Suspense fallback={<Skeleton className="mt-4 h-[70vh]" />}>{el}</Suspense></RoleGuard>;

export function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/verificar/:code" element={<VerifyPage />} />
          <Route element={<RoleGuard><AppShell /></RoleGuard>}>
            <Route index element={page(<DashboardPage />)} />
            <Route path="rutas" element={page(<PathsPage />, "paths:read")} />
            <Route path="cursos" element={page(<CoursesPage />, "courses:read")} />
            <Route path="cursos/:id" element={page(<CourseDetailPage />, "courses:read")} />
            <Route path="analisis" element={page(<AnalyticsPage />, "analytics:read")} />
            <Route path="tutor" element={page(<TutorPage />)} />
            <Route path="evaluaciones" element={page(<AssessmentsPage />, "assessments:read")} />
            <Route path="certificados" element={page(<CertificatesPage />, "certificates:read")} />
            <Route path="comunidad" element={page(<CommunityPage />, "community:read")} />
            <Route path="habilidades" element={page(<SkillsPage />, "analytics:read")} />
            <Route path="redes" element={page(<NeuralPage />, "ml:read")} />
            <Route path="recomendaciones" element={page(<RecommendationsPage />, "recommendations:read")} />
            <Route path="actividad" element={page(<ActivityPage />)} />
            <Route path="administracion" element={page(<AdminPage />)} />
            <Route path="configuracion" element={page(<SettingsPage />)} />
            <Route path="*" element={<div className="panel mt-6 p-10 text-center"><p className="font-display text-xl">Página no encontrada</p></div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
