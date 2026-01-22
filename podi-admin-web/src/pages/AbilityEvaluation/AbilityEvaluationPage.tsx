import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../../services/adminApi';
import type { EvalDatasetItem, EvalRun, EvalWorkflowVersion } from '../../types/eval';
import { EvaluationInputPanel } from './components/EvaluationInputPanel';
import { EvaluationResultPanel } from './components/EvaluationResultPanel';
import { EvaluationSidebar } from './components/EvaluationSidebar';

export function AbilityEvaluationPage() {
  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [datasetItems, setDatasetItems] = useState<EvalDatasetItem[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<EvalWorkflowVersion | null>(null);
  const [selectedDatasetItem, setSelectedDatasetItem] = useState<EvalDatasetItem | null>(null);
  const [inputImages, setInputImages] = useState<string[]>([]);
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [evaluationResults, setEvaluationResults] = useState<EvalRun[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const activeCategory = selectedWorkflow?.category || '';
  const filteredDatasetItems = useMemo(
    () => (activeCategory ? datasetItems.filter((item) => item.category === activeCategory) : datasetItems),
    [datasetItems, activeCategory],
  );

  const refreshRuns = async (workflowId?: string) => {
    const wfId = workflowId ?? selectedWorkflow?.id;
    if (!wfId) return;
    const res = await adminApi.listEvalRuns({ workflow_version_id: wfId, limit: 50, offset: 0 });
    setEvaluationResults(res.items || []);
  };

  useEffect(() => {
    (async () => {
      try {
        const wfs = await adminApi.listEvalWorkflowVersions({ status: 'active' });
        setWorkflows(wfs || []);
        if (wfs && wfs.length > 0) {
          setSelectedWorkflow(wfs[0]);
        }
      } catch (err) {
        console.error(err);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const items = await adminApi.listEvalDatasetItems(activeCategory ? { category: activeCategory } : undefined);
        setDatasetItems(items || []);
        if (items && items.length > 0) {
          setSelectedDatasetItem(items[0]);
          setInputImages([items[0].oss_url]);
        } else {
          setSelectedDatasetItem(null);
        }
      } catch (err) {
        console.error(err);
      }
    })();
  }, [activeCategory]);

  useEffect(() => {
    if (!selectedWorkflow) return;
    void refreshRuns(selectedWorkflow.id);
    const timer = window.setInterval(() => {
      const hasRunning = evaluationResults.some((r) => r.status === 'queued' || r.status === 'running');
      if (hasRunning) {
        void refreshRuns(selectedWorkflow.id);
      }
    }, 2000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkflow?.id, evaluationResults.length]);

  const handleWorkflowSelect = (workflow: EvalWorkflowVersion) => {
    setSelectedWorkflow(workflow);
    setParameters({});
    setInputImages([]);
    setSelectedDatasetItem(null);
    void refreshRuns(workflow.id);
  };

  const handleDatasetItemSelect = (datasetItem: EvalDatasetItem) => {
    setSelectedDatasetItem(datasetItem);
    setInputImages([datasetItem.oss_url]);
  };

  const handleImageChange = (url: string) => setInputImages([url]);

  const handleParameterChange = (newParameters: Record<string, any>) => {
    setParameters(newParameters);
  };

  const handleRunEvaluation = async () => {
    if (!selectedWorkflow) return;
    const url = inputImages[0];
    if (!url) return;
    setIsRunning(true);
    try {
      const run = await adminApi.createEvalRun({
        workflow_version_id: selectedWorkflow.id,
        dataset_item_id: selectedDatasetItem?.id ?? null,
        input_oss_urls_json: [url],
        parameters_json: { ...parameters, url },
      });
      setEvaluationResults((prev) => [run, ...prev]);
      await refreshRuns(selectedWorkflow.id);
    } catch (error) {
      console.error('Failed to run evaluation:', error);
    } finally {
      setIsRunning(false);
    }
  };

  const handleAnnotate = async (runId: string, annotation: { rating: number; comment?: string }) => {
    try {
      await adminApi.createEvalAnnotation(runId, annotation);
      if (selectedWorkflow) await refreshRuns(selectedWorkflow.id);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="flex h-[720px] overflow-hidden rounded-3xl border border-slate-800 bg-slate-950/30">
      <EvaluationSidebar workflows={workflows} selectedWorkflow={selectedWorkflow} onWorkflowSelect={handleWorkflowSelect} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <EvaluationInputPanel
          selectedWorkflow={selectedWorkflow}
          selectedDatasetItem={selectedDatasetItem}
          datasetItems={filteredDatasetItems}
          inputImages={inputImages}
          parameters={parameters}
          isRunning={isRunning}
          onDatasetItemSelect={handleDatasetItemSelect}
          onImageChange={handleImageChange}
          onParameterChange={handleParameterChange}
          onRunEvaluation={handleRunEvaluation}
        />

        <EvaluationResultPanel results={evaluationResults} onAnnotate={handleAnnotate} />
      </div>
    </div>
  );
}
