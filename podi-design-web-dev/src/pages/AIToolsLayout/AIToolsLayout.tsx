import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AI_ACTIONS } from '@/constants/sidebar';

interface Props {
  children: React.ReactNode;
}

export const AIToolsLayout: React.FC<Props> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const matched = AI_ACTIONS.find((t) => location.pathname.startsWith(t.path));
  const ToolIcon = matched?.icon;
  const title = matched?.label || '';

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b flex items-center gap-4">
        {/* <Button
          onClick={() => navigate('/aitl')}
          className="border bg-background text-foreground hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 h-8 rounded-md gap-1.5 px-3"
        >
          ← 返回工具列表
        </Button> */}

        <div className="flex items-center gap-3">
          <div className="w-5 h-5 flex items-center gap-2">
            {ToolIcon ? <ToolIcon className="w-4 h-4" /> : null}
          </div>
          <h2 className="text-base font-medium">{title}</h2>
        </div>
      </div>

      {/* page content */}
      <div className="pt-3 flex-1 overflow-auto">{children}</div>
    </div>
  );
};

export default AIToolsLayout;
