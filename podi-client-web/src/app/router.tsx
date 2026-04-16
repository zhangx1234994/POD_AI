import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import ClientLayout from '../layouts/ClientLayout';

const HomePage = lazy(() => import('../pages/HomePage'));
const WorkbenchPage = lazy(() => import('../pages/WorkbenchPage'));
const DesignPage = lazy(() => import('../pages/DesignPage'));
const ToolboxPage = lazy(() => import('../pages/ToolboxPage'));
const ShootPage = lazy(() => import('../pages/ShootPage'));
const TasksPage = lazy(() => import('../pages/TasksPage'));
const AssetsPage = lazy(() => import('../pages/AssetsPage'));
const ProjectDetailPage = lazy(() => import('../pages/ProjectDetailPage'));
const WalletPage = lazy(() => import('../pages/WalletPage'));

function RouteFallback() {
  return (
    <div className="client-route-fallback">
      <div className="client-route-fallback__card">
        <span>正在载入页面</span>
        <strong>Style3D 客户端</strong>
      </div>
    </div>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<ClientLayout />}>
            <Route index element={<Navigate to="/home" replace />} />
            <Route path="home" element={<HomePage />} />
            <Route path="studio" element={<WorkbenchPage />} />
            <Route path="design/:tool?" element={<DesignPage />} />
            <Route path="toolbox/:tool?" element={<ToolboxPage />} />
            <Route path="shoot/:tool?" element={<ShootPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="assets" element={<AssetsPage />} />
            <Route path="projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="wallet" element={<WalletPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
