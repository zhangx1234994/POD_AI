import React from 'react';
import WorkspaceSidebar from './WorkspaceSidebar';
import WorkspaceForm from './WorkspaceForm';
import WorkspacePreview from './WorkspacePreview';
import type { WorkspaceProps } from '../../types/workspace';

export default function WorkspaceLayout(props: WorkspaceProps) {
  return (
    <div className="client-workspace-layout">
      {/* 左侧业务导航栏 */}
      <WorkspaceSidebar
        tool={props.tool}
        mode={props.mode}
      />

      {/* 中间工作表单区 */}
      <div className="client-workspace-layout__main">
        <WorkspaceForm
          tool={props.tool}
          mode={props.mode}
        />
      </div>

      {/* 右侧案例与结果预览区 */}
      <div className="client-workspace-layout__preview">
        <WorkspacePreview
          tool={props.tool}
          mode={props.mode}
        />
      </div>
    </div>
  );
}
