import React from 'react';
import type { ReactNode } from 'react';

interface AIProcessorTitleProps {
  toolIcon?: ReactNode;
  toolName: string;
}

export const AIProcessorTitle: React.FC<AIProcessorTitleProps> = ({ toolIcon, toolName }) => {
  return (
    <div className="flex items-center gap-3 mb-6">
      {toolIcon && (
        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg">
          {toolIcon}
        </div>
      )}
      <div>
        <h1 className="text-lg font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
          {toolName}
        </h1>
        <p className="text-xs text-muted-foreground">AI智能处理工具</p>
      </div>
    </div>
  );
};

export default AIProcessorTitle;
