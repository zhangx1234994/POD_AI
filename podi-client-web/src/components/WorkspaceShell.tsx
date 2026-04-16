import WorkspaceFormPanel from './workspace/WorkspaceFormPanel';
import WorkspaceResultPanel from './workspace/WorkspaceResultPanel';
import { useWorkspaceController } from '../hooks/useWorkspaceController';
import type { WorkspaceProps } from '../types/workspace';

export default function WorkspaceShell(props: WorkspaceProps) {
  const controller = useWorkspaceController(props);

  return (
    <div className="client-workspace-grid">
      <WorkspaceFormPanel
        tool={props.tool}
        mode={props.mode}
        runtime={controller.runtime}
        ability={controller.ability}
        abilitiesLoading={controller.abilitiesLoading}
        abilitiesError={controller.abilitiesError}
        isAuthenticated={controller.isAuthenticated}
        uploads={controller.uploads}
        uploading={controller.uploading}
        formValues={controller.formValues}
        submitting={controller.submitting}
        inputRef={controller.inputRef}
        estimatedPoints={controller.estimatedPoints}
        balance={controller.balance}
        recentCandidates={controller.recentCandidates}
        canSubmit={controller.canSubmit}
        onSelectFiles={controller.handleFiles}
        onUseRecentAsset={controller.useRecentAsset}
        onChangeField={(key, value) => controller.setFormValues((prev) => ({ ...prev, [key]: value }))}
        onReset={controller.resetWorkspace}
        onSubmit={controller.handleSubmit}
      />
      <WorkspaceResultPanel
        tool={props.tool}
        mode={props.mode}
        ability={controller.ability}
        result={controller.result}
        resultTitle={controller.resultTitle}
        recentCandidates={controller.recentCandidates}
        onApplyCandidate={controller.applyRecentCandidate}
        onOpenAssets={() => controller.navigate('/assets')}
        onOpenTasks={() => controller.navigate('/tasks')}
        rechargeVisible={controller.rechargeVisible}
        balance={controller.balance}
        estimatedPoints={controller.estimatedPoints}
        onCloseRecharge={controller.closeRechargeDialog}
        onGoRecharge={controller.goRecharge}
      />
    </div>
  );
}
