import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Sidebar } from './pages/Sidebar/Sidebar';
import { Header } from './pages/Header/Header';
import { BatchTaskDashboardPage } from './pages/BatchTaskDashboard/BatchTaskDashboardPage';
import { PersonalCenterPage } from './pages/PersonalCenter/PersonalCenterPage';
import { PersonalGalleryPage } from './pages/PersonalGallery/PersonalGalleryPage';
import { PointsHistoryPage } from '@/pages/PointsHistory/PointsHistoryPage';
import { IntegrationDashboard } from '@/pages/Admin/IntegrationDashboard';
import { AIToolsLayout } from './pages/AIToolsLayout/AIToolsLayout';
import { TaskDetailPage } from './pages/TaskDetail/TaskDetailPage';

import { AIToolsPage } from './pages/AIToolsPage/AIToolsPage';
import { LosslessUpscaleProcessor } from './pages/AIProcessorTools/LosslessUpscaleProcessor';
import { ExtensionProcessor } from './pages/AIProcessorTools/ExtensionProcessor';
import { PatternExtractProcessor } from './pages/AIProcessorTools/PatternExtractProcessor';
import { SeamlessProcessor } from './pages/AIProcessorTools/SeamlessProcessor';
import { FissionProcessor } from './pages/AIProcessorTools/FissionProcessor';
import { AIImageEditorPage } from './pages/AIImageEditor/AIImageEditorPage';
import { AbilityLabPage } from './pages/AbilityLab/AbilityLabPage';
import { SSOHandler } from '@/pages/SSO/SSOHandler';

import { LoginPage } from '@/pages/Login/LoginPage';
import { RegisterPage } from '@/pages/Register/RegisterPage';
import { OperationTools } from './components/OperationTools';
import { GalleryManager } from './components/GalleryManager';
import { ImageSourceDemo } from './components/ImageSourceDemo';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';
import { Toaster } from '@/components/ui/sonner';
import { RequireAuth } from '@/components/RequireAuth';

import {
  Users,
  Settings as SettingsIcon,
  Database,
  Shield,
  Clock,
  Download,
  User,
  Key,
  Bell,
  Palette,
} from 'lucide-react';
import { AuthProvider } from '@/contexts/AuthProvider';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { PointsProvider } from '@/contexts/PointsContext';
import { SidebarProvider } from '@/contexts/SidebarContext';
import { useRealtimeNotifications } from '@/hooks/useRealtimeNotifications';

function UserManagement() {
  return (
    <div className="p-4 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">用户管理</h1>
        <p className="text-muted-foreground text-sm">管理用户权限和下载限制</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              用户统计
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span>总用户数:</span>
                <Badge variant="secondary">1,234</Badge>
              </div>
              <div className="flex justify-between">
                <span>活跃用户:</span>
                <Badge variant="secondary">856</Badge>
              </div>
              <div className="flex justify-between">
                <span>VIP用户:</span>
                <Badge>127</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="w-5 h-5" />
              下载统计
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span>今日下载:</span>
                <Badge variant="secondary">2,456</Badge>
              </div>
              <div className="flex justify-between">
                <span>本月下载:</span>
                <Badge variant="secondary">67,890</Badge>
              </div>
              <div className="flex justify-between">
                <span>超限用户:</span>
                <Badge variant="destructive">23</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              权限设置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="outline" className="w-full justify-start">
                <Shield className="w-4 h-4 mr-2" />
                权限配置
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Download className="w-4 h-4 mr-2" />
                下载限制
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <User className="w-4 h-4 mr-2" />
                用户等级
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Settings() {
  return (
    <div className="p-4 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">系统设置</h1>
        <p className="text-muted-foreground text-sm">配置系统参数和安全设置</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5" />
              数据库设置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="outline" className="w-full justify-start">
                <Database className="w-4 h-4 mr-2" />
                数据备份
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Shield className="w-4 h-4 mr-2" />
                安全配置
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Clock className="w-4 h-4 mr-2" />
                定时任务
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="w-5 h-5" />
              API设置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="outline" className="w-full justify-start">
                <Key className="w-4 h-4 mr-2" />
                API密钥
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Shield className="w-4 h-4 mr-2" />
                访问控制
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Bell className="w-4 h-4 mr-2" />
                通知设置
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="w-5 h-5" />
              界面设置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="outline" className="w-full justify-start">
                <Palette className="w-4 h-4 mr-2" />
                主题配色
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <SettingsIcon className="w-4 h-4 mr-2" />
                布局设置
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              安全中心
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="outline" className="w-full justify-start">
                <Shield className="w-4 h-4 mr-2" />
                安全日志
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Key className="w-4 h-4 mr-2" />
                登录记录
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MainLayout() {
  const [darkMode, setDarkMode] = useState(false);
  const location = useLocation();

  // 初始化darkMode状态
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    const isDarkMode = savedTheme === 'dark';
    setDarkMode(isDarkMode);

    // 应用主题到DOM
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const handleToggleDarkMode = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);

    // 更新DOM和localStorage
    if (newDarkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  };

  // 在路由切换时清理参数和图片内容
  useEffect(() => {
    // 清理本地存储中的图片相关数据
    localStorage.removeItem('uploadedImages');
    localStorage.removeItem('processedImages');
    localStorage.removeItem('currentImageData');

    // 清理可能存在的其他临时数据
    localStorage.removeItem('tempCanvas');
    localStorage.removeItem('editorState');
  }, [location.pathname]);

  return (
    <div className="h-screen flex bg-background">
      {/* 侧边栏 */}
      <Sidebar />

      {/* 主内容区 */}
      <div id="main-layout-content" className="flex-1 flex flex-col overflow-hidden">
        {/* 顶部导航 */}
        <Header darkMode={darkMode} onToggleDarkMode={handleToggleDarkMode} />

        {/* 主内容 */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function LoginPageWrapper() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as any)?.from?.pathname || '/dashboard';

  return (
    <LoginPage
      onSuccess={() => navigate(from, { replace: true })}
    />
  );
}

function RegisterPageWrapper() {
  const navigate = useNavigate();

  return (
    <RegisterPage
      onSuccess={() => navigate('/dashboard', { replace: true })}
      onSwitchLogin={() => navigate('/login')}
    />
  );
}

export default function App() {
  useRealtimeNotifications(import.meta.env.VITE_API_BASE_URL);
  return (
    <AuthProvider>
      <NotificationProvider>
        <PointsProvider>
          <SidebarProvider>
            <Routes>
              <Route path="/login" element={<LoginPageWrapper />} />
              <Route path="/register" element={<RegisterPageWrapper />} />
              <Route path="/sso" element={<SSOHandler />} />
              <Route
                element={
                  <RequireAuth>
                    <MainLayout />
                  </RequireAuth>
                }
              >
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<BatchTaskDashboardPage />} />
                <Route path="/profile" element={<PersonalCenterPage />} />
                <Route path="/personal-gallery" element={<PersonalGalleryPage />} />

                {/* AI Tools */}
                <Route path="/aitl" element={<AIToolsPage />} />
                <Route path="/aitl/hires" element={<AIToolsLayout><LosslessUpscaleProcessor action="hires" /></AIToolsLayout>} />
                <Route path="/aitl/fission" element={<AIToolsLayout><FissionProcessor action="fission" /></AIToolsLayout>} />
                <Route path="/aitl/pattern-extract" element={<AIToolsLayout><PatternExtractProcessor action="pattern-extract" /></AIToolsLayout>}/>
                <Route path="/aitl/seamless" element={<AIToolsLayout><SeamlessProcessor action="seamless" /></AIToolsLayout>} />
                <Route path="/aitl/extend" element={<AIToolsLayout><ExtensionProcessor action="extend" /></AIToolsLayout>} />
                <Route path="/aitl/edit" element={<AIToolsLayout><AIImageEditorPage action="edit" /></AIToolsLayout>} />
                <Route path="/aitl/ability-lab" element={<AIToolsLayout><AbilityLabPage /></AIToolsLayout>} />

                {/* <Route path="/aitl/cutout" element={<CutoutProcessor />} /> */}
                {/* <Route path="/aitl/merge" element={<AIToolsLayout><ImageMergeProcessor action="merge" /></AIToolsLayout>} /> */}
                {/* <Route path="/aitl/style" element={<StyleTransferProcessor />} /> */}
                {/* <Route path="/aitl/replace" element={<LocalReplaceProcessor />} /> */}
                {/* <Route path="/aitl/img2img" element={<AIToolsLayout><Img2ImgProcessor action="img2img" /></AIToolsLayout>} />  */}     
                {/* <Route path="/aitl/txt2img" element={<Txt2ImgProcessor />} /> */}
                {/* <Route path="/aitl/crop" element={<PatternCropProcessor />} /> */}
                {/* <Route path="/aitl/template" element={<TemplateProcessor />} /> */}
                {/* <Route path="/aitl/workflow" element={<WorkflowManager />} /> */}
                <Route path="/task-detail/:taskId" element={<TaskDetailPage />} />
                {/* Points History */}
                <Route path="/points" element={<PointsHistoryPage />} />
                {/* Operation Tools */}
                <Route
                  path="/operation/calculator"
                  element={<OperationTools activeSection="calculator" />}
                />
                <Route path="/operation/collect" element={<OperationTools activeSection="collect" />} />
                <Route path="/operation/video" element={<OperationTools activeSection="video" />} />

                {/* Admin */}
                <Route path="/admin/gallery" element={<GalleryManager />} />
                <Route path="/admin/users" element={<UserManagement />} />
                <Route path="/admin/settings" element={<Settings />} />
                <Route path="/admin/integrations" element={<IntegrationDashboard />} />

                {/* Demo */}
                <Route path="/demo/image-source" element={<ImageSourceDemo />} />

                {/* Fallback */}
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Routes>
          </SidebarProvider>
        </PointsProvider>

        {/* 全局 Toaster（sonner）用于展示 toast 提示 */}
        <Toaster />
      </NotificationProvider>
    </AuthProvider>
  );
}
