import { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Wand2, ChevronLeft, ChevronRight, HelpCircle } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { AI_ACTIONS, MAIN_MENU } from '@/constants/sidebar';
import { TaskCenterHover } from './TaskCenterHover';

export function Sidebar() {
  const location = useLocation();
  const currentPath = location.pathname;

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('sidebar-collapsed');
      // If a preference exists, respect it; otherwise default to expanded (false).
      return v === '1';
    } catch (e) {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
    } catch (e) {}
  }, [collapsed]);

  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (collapsed) document.documentElement.classList.add('sidebar-collapsed');
    else document.documentElement.classList.remove('sidebar-collapsed');

    const el = rootRef.current;
    const doDispatch = (when = 'transitionend') => {
      try {
        const ev = new CustomEvent('sidebar:toggle', { detail: { collapsed, when } });
        window.dispatchEvent(ev);
      } catch (e) {}
    };

    const onTransitionEnd = (ev: TransitionEvent) => {
      if (ev.propertyName && ev.propertyName.indexOf('width') === -1 && ev.propertyName.indexOf('transform') === -1) return;
      doDispatch('transitionend');
    };

    if (el) el.addEventListener('transitionend', onTransitionEnd as EventListener);

    return () => {
      if (el) el.removeEventListener('transitionend', onTransitionEnd as EventListener);
    };
  }, [collapsed]);

  const isActive = (path: string) => {
    if (path === '/dashboard' && currentPath === '/') return true;
    return currentPath.startsWith(path);
  };

  const navigate = useNavigate();

  const handleHelpCenter = () => {
    console.log('帮助中心');
  };

  // Sidebar width units (Tailwind spacing unit numbers). These are used
  // to compute pixel widths for the sidebar and the toggle button position.
  // Tailwind spacing unit * 4 === pixels (eg. w-56 -> 56 * 4 = 224px).
  const SIDEBAR_EXPANDED_UNITS = 64;
  const SIDEBAR_COLLAPSED_UNITS = 16;
  const HEADER_HEIGHT_UNITS = 24;
  const TOGGLE_BUTTON_WIDTH = 4;
  const TOGGLE_BUTTON_HEIGHT = 4;

  const toggleButtonHalfWidthPx = TOGGLE_BUTTON_WIDTH * 4;
  const headerHeightPx = HEADER_HEIGHT_UNITS * 4;
  const currentSidebarUnits = collapsed ? SIDEBAR_COLLAPSED_UNITS : SIDEBAR_EXPANDED_UNITS;
  const currentSidebarPx = currentSidebarUnits * 4;
  const toggleLeftPx = Math.max(0, currentSidebarPx - toggleButtonHalfWidthPx);
  const toggleTopPx = Math.max(0, headerHeightPx - toggleButtonHalfWidthPx);

  return (
    <div ref={rootRef} className={`${collapsed ? `w-${SIDEBAR_COLLAPSED_UNITS}` : `w-${SIDEBAR_EXPANDED_UNITS}`} h-full bg-card border-r border-border flex flex-col shadow-sm transition-all duration-200`}>
      <div className={`flex items-center ${collapsed ? 'justify-center p-4' : 'justify-between p-5'} border-b border-border bg-gradient-to-br from-background to-muted/30 h-${HEADER_HEIGHT_UNITS}`}>
        <div className="flex items-center gap-3">
          <div className={`${collapsed ? 'w-5 h-5' : 'w-10 h-10'} bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg`}>
            <Wand2 className={`${collapsed ? 'w-3 h-3' : 'w-4 h-4'} text-white`} />
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-lg font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">POD AI Studio</h1>
              <p className="text-xs text-muted-foreground">图片处理工具</p>
            </div>
          )}
        </div>
      </div>

      <div className="relative flex-1 overflow-y-auto p-4 space-y-6">
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className={`text-sm font-medium text-muted-foreground ${collapsed ? 'hidden' : ''}`}>主要功能</h3>
          </div>
          <div className="space-y-1">
            {MAIN_MENU.map((section) => {
              const Icon = section.icon;
              return (
                <Link to={section.path} key={section.id}>
                  <Button
                    variant={isActive(section.path) ? 'secondary' : 'ghost'}
                    className={`w-full px-3 ${collapsed ? 'justify-center' : 'justify-start gap-3'} ${
                      isActive(section.path)
                        ? 'bg-primary/10 text-primary hover:bg-primary/20 font-medium'
                        : 'hover:bg-secondary/80 text-muted-foreground hover:text-foreground'
                    }`}
                    title={section.label}
                  >
                    <Icon className={`w-4 h-4 ${isActive(section.path) ? 'text-primary' : ''}`} />
                    {!collapsed && section.label}
                  </Button>
                </Link>
              );
            })}
          </div>
        </div>

        <Separator className="bg-border/50" />

        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className={`text-sm font-medium text-muted-foreground ${collapsed ? 'hidden' : ''}`}>AI 工具</h3>
            {/* {!collapsed && (
              <span data-slot="badge" className="inline-flex items-center justify-center w-6 h-6 bg-secondary rounded-md text-gray-700 text-xs font-medium">{aiTools.length}</span>
            )} */}
          </div>
          <div className="space-y-1">
            {AI_ACTIONS.map((tool) => {
              const Icon = tool.icon;
              const baseIconClass = `w-4 h-4 ${isActive(tool.path) ? 'text-primary' : ''}`;
              return (
                <Link to={tool.path} key={tool.id}>
                  <Button
                    variant={isActive(tool.path) ? 'secondary' : 'ghost'}
                    className={`w-full ${collapsed ? 'justify-center' : 'justify-start gap-3'} ${
                      isActive(tool.path)
                        ? 'bg-primary/10 text-primary hover:bg-primary/20 font-medium'
                        : 'hover:bg-secondary/80 text-muted-foreground hover:text-foreground'
                    }`}
                    title={tool.label}
                  >
                    <Icon className={baseIconClass} />
                    {!collapsed && tool.label}
                  </Button>
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      <div className="p-2 border-t border-border bg-muted/10">
        <div className={`${collapsed ? 'flex flex-col items-center gap-2 px-2' : 'flex items-center justify-between px-2'}`}>
          {collapsed ? (
            <>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div tabIndex={0} className="inline-block focus:outline-none">
                    <Button
                      variant="ghost"
                      disabled
                      aria-disabled={true}
                      className="h-12 w-full flex items-center justify-center rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-border bg-transparent hover:bg-secondary/80 text-muted-foreground shadow-none"
                    >
                      <HelpCircle className="w-4 h-4 text-muted-foreground" />
                    </Button>
                  </div>
                </TooltipTrigger>
                <TooltipContent
                  sideOffset={-2}
                  side="top"
                  align="center"
                  className="help-center-tooltip bg-white text-foreground border border-border shadow-sm"
                  showArrow={false}
                >
                  帮助中心还在施工中，精彩马上上线 🚧
                </TooltipContent>
              </Tooltip>

              <div className="w-full h-px bg-border my-1" />

              <div className="w-full flex items-center justify-center">
                <TaskCenterHover collapsed={collapsed} />
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div tabIndex={0} className="inline-block focus:outline-none">
                      <Button
                        variant="ghost"
                        disabled
                        aria-disabled={true}
                        className="h-12 flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-border bg-transparent hover:bg-secondary/80 text-muted-foreground shadow-none"
                      >
                        <HelpCircle className="w-4 h-4 text-muted-foreground" />
                        <span className="text-xs text-muted-foreground">帮助中心</span>
                      </Button>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent
                    sideOffset={-2}
                    side="top"
                    align="center"
                    className="help-center-tooltip bg-white text-foreground border border-border shadow-sm"
                    showArrow={false}
                  >
                    帮助中心还在施工中，精彩马上上线 🚧
                  </TooltipContent>
                </Tooltip>
              </div>

              <div className="h-10 w-px bg-border my-1" />

              <div className="flex items-center justify-end">
                <TaskCenterHover collapsed={collapsed} />
              </div>
            </>
          )}
        </div>
      </div>

      <button
        title={collapsed ? '展开侧边栏' : '收起侧边栏'}
        onClick={() => setCollapsed(s => !s)}
        aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
        className="absolute -right-3 top-20 w-8 h-8 bg-background border border-border rounded-full flex items-center justify-center hover:bg-muted transition-colors shadow-md z-20"
        style={{ top: `${toggleTopPx}px`, left: `${toggleLeftPx}px`}}
      >
        {collapsed ? (
          <ChevronRight className={`w-${TOGGLE_BUTTON_WIDTH} h-${TOGGLE_BUTTON_HEIGHT} text-muted-foreground`} />
        ) : (
          <ChevronLeft className={`w-${TOGGLE_BUTTON_WIDTH} h-${TOGGLE_BUTTON_HEIGHT} text-muted-foreground`} />
        )}
      </button>
    </div>
  );
}

export default Sidebar;
