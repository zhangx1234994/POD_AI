import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Coins, Bell, HelpCircle, Sun, Moon, User, LogOut, Settings, Download } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { useAuth } from '@/contexts/AuthContext';
import { usePoints } from '@/contexts/PointsContext';
import { TopBanner } from './TopBanner';
import { PointsBalance } from '@/pages/Header/PointsBalance';
import { Button } from '@/components/ui/button';

interface HeaderProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
}

export const Header: React.FC<HeaderProps> = ({ darkMode, onToggleDarkMode }) => {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const { fetchPointsStatistics, fetchTransactions, midnightGrantAnimation, submissionToast } = usePoints();
  const navigate = useNavigate();

  

  useEffect(() => {
    // 初始化主题
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  

  const handleLogout = async () => {
    await logout();
    setIsUserMenuOpen(false);
    // 刷新页面以重新加载登录页面
    window.location.reload();
  };

  // 获取用户显示名称，优先显示昵称，其次是用户名
  const getDisplayName = () => {
    if (user?.nickname) {
      return user.nickname;
    }
    if (user?.username) {
      return user.username;
    }
    return '用户';
  };

  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (menuRef.current && !menuRef.current.contains(target)) {
        setIsUserMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <>
      <TopBanner active={submissionToast?.active} variant="success">
        任务已提交! 消耗<span className="font-semibold">{submissionToast?.amount}</span>积分, 剩余<span className="font-semibold">{submissionToast?.remaining}</span>积分
      </TopBanner>

      <TopBanner active={midnightGrantAnimation?.active} variant="success">
        今日临时积分已到账! <span className="font-semibold">+{midnightGrantAnimation?.amount}</span>
      </TopBanner>
      <header className="bg-card border-b border-border sticky top-0 z-20">
        <div className="px-6 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4 ml-auto">
              {/* 积分按钮 */}
              <div className="inline-flex items-center justify-center">
                <Button
                  variant="ghost"
                  title="查看积分明细"
                  onClick={async () => {
                    // 进入积分页面时获取最新统计信息与交易记录
                    fetchPointsStatistics();
                    fetchTransactions({ current: 1 });
                    navigate('/points');
                  }}
                  className={`gap-1 min-w-14 h-12 inline-flex items-center justify-center rounded-md transition-colors`}
                >
                  <Coins size={18} />
                  <PointsBalance />
                </Button>
              </div>

              {/* 通知按钮 */}
              <div className="relative">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div tabIndex={0} className="inline-block">
                      <Button
                        variant="ghost"
                        title="通知"
                        disabled
                        aria-disabled={true}
                        className={`w-12 h-12 inline-flex items-center justify-center rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
                      >
                        <Bell size={20} />
                      </Button>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent
                    sideOffset={-8}
                    side="bottom"
                    align="center"
                    className="help-center-tooltip bg-white text-foreground border border-border shadow-sm" 
                    showArrow={false}
                  >

                    通知中心还在施工中，精彩马上上线 🚧
                  </TooltipContent>
                </Tooltip>
              </div>

              {/* 帮助中心按钮 - 暂时注释掉 */}
              {/*
              <button
                title="帮助中心"
                onClick={() => setIsUserMenuOpen(false)}
                className="w-12 h-12 inline-flex items-center justify-center rounded-full text-gray-600 hover:bg-accent rounded-md dark:text-gray-400 dark:hover:text-white dark:hover:bg-black transition-colors"
              >
                <HelpCircle size={20} />
              </button>
              */}

              {/* 主题切换按钮 */}
              <button
                onClick={() => {
                  setIsUserMenuOpen(false);
                  onToggleDarkMode();
                }}
                title="切换主题"
                className="w-12 h-12 inline-flex items-center justify-center rounded-full hover:bg-accent rounded-md dark:text-muted-foreground dark:hover:text-white dark:hover:bg-black transition-colors"
              >
                {darkMode ? <Sun size={20} /> : <Moon size={20} />}
              </button>

              {/* 我的账户 */}
              <div className="relative" ref={menuRef}>
                <button
                  title="我的账户"
                  onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                  className="h-12 flex items-center space-x-2 p-2 rounded-full hover:bg-accent rounded-md dark:text-muted-foreground dark:hover:text-white dark:hover:bg-black transition-colors"
                >
                  <span className="w-8 h-8 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 inline-flex items-center justify-center">
                    <User size={16} className="text-white" />
                  </span>
                  <h3 className="hidden md:inline px-2">{getDisplayName()}</h3>
                </button>

                {isUserMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-md shadow-lg space-y-1 p-1 border border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">我的账户</p>
                    </div>
                    <button
                      onClick={() => setIsUserMenuOpen(false)}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-accent rounded-md dark:text-gray-300 dark:hover:bg-gray-700"
                    >
                      <User size={16} className="mr-2" />
                      个人信息
                    </button>
                    <button
                      onClick={() => setIsUserMenuOpen(false)}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-accent rounded-md dark:text-gray-300 dark:hover:bg-gray-700"
                    >
                      <Settings size={16} className="mr-2" />
                      个人设置
                    </button>
                    <button
                      onClick={() => setIsUserMenuOpen(false)}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-accent rounded-md dark:text-gray-300 dark:hover:bg-gray-700"
                    >
                      <Download size={16} className="mr-2" />
                      下载记录
                    </button>
                    <div className="border-t border-gray-200 dark:border-gray-700" />
                    <button
                      onClick={handleLogout}
                      className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-accent rounded-md dark:text-gray-300 dark:hover:bg-gray-700"
                    >
                      <LogOut size={16} className="mr-2" />
                      退出登录
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>
    </>
  );
};

export default Header;
