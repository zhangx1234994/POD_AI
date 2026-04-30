import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type { JsonRecord, JsonValue, Workflow, WorkflowFormState } from '../../../types/admin';

type ComfyInputMapItem = {
  field: string;
  nodeId: string;
  inputKey: string;
  valueType?: string;
};

type ComfyNode = {
  id: string;
  title: string;
  classType: string;
  inputs: string[];
};

type JsonParseResult = {
  ok: boolean;
  value: JsonRecord;
};

type ComfyDefinitionInfo = {
  ok: boolean;
  source: 'prompt' | 'ui' | 'unknown';
  graph: JsonRecord;
  payload: JsonRecord;
  hasGraphContainer: boolean;
};

const bumpWorkflowVersion = (version?: string | null): string => {
  const raw = (version || '').trim();
  if (!raw) return 'v2';
  const match = raw.match(/^v(\d+)$/i);
  if (match) {
    const next = Number(match[1]) + 1;
    return `v${Number.isNaN(next) ? 2 : next}`;
  }
  const tail = raw.match(/(\d+)(?:\.(\d+))?$/);
  if (tail) {
    const major = Number(tail[1]);
    const minor = tail[2] ? Number(tail[2]) : null;
    if (!Number.isNaN(major)) {
      if (minor !== null && !Number.isNaN(minor)) {
        return raw.replace(/(\d+)\.(\d+)$/, `${major}.${minor + 1}`);
      }
      return raw.replace(/(\d+)$/, String(major + 1));
    }
  }
  return `${raw}-copy`;
};

const buildWorkflowClonePayload = (workflow: Workflow) => {
  const nextVersion = bumpWorkflowVersion(workflow.version);
  const definition = workflow.definition && typeof workflow.definition === 'object'
    ? JSON.parse(JSON.stringify(workflow.definition))
    : workflow.definition;
  const metadata = workflow.metadata && typeof workflow.metadata === 'object'
    ? JSON.parse(JSON.stringify(workflow.metadata))
    : {};
  const currentKey = typeof metadata.workflow_key === 'string' ? metadata.workflow_key.trim() : '';
  const versionSuffix = nextVersion.replace(/[^a-zA-Z0-9]/g, '_');
  const trimmedKey = currentKey ? currentKey.replace(/([_-])v\d+$/i, '') : '';
  const nextKeyBase = trimmedKey || workflow.action || workflow.name || 'comfyui_workflow';
  const nextWorkflowKey = `${nextKeyBase}_${versionSuffix}`;
  metadata.workflow_key = nextWorkflowKey;
  if (definition && typeof definition === 'object' && 'workflow_key' in definition) {
    (definition as JsonRecord).workflow_key = nextWorkflowKey;
  }
  return {
    nextVersion,
    definition,
    metadata,
  };
};

interface WorkflowTemplateActionsParams {
  comfyWorkflowNodes: ComfyNode[];
  defaultWorkflowForm: WorkflowFormState;
  extractAllowedExecutorIds: (metadata?: string | JsonRecord | null) => string[];
  extractErrorMessage: (error: unknown) => string;
  load: () => void | Promise<void>;
  normalizeInputNodeMap: (metadata?: JsonRecord | null) => ComfyInputMapItem[];
  normalizeOutputNodeIds: (metadata?: JsonRecord | null) => string[];
  parseJSON: (value?: string | JsonRecord) => JsonRecord;
  resolveComfyuiDefinition: (definition?: string | JsonRecord) => ComfyDefinitionInfo;
  serializeInputNodeMap: (items: ComfyInputMapItem[]) => JsonRecord[];
  setWorkflowForm: Dispatch<SetStateAction<WorkflowFormState>>;
  setWorkflowFormAllowedExecutors: Dispatch<SetStateAction<string[]>>;
  setWorkflowFormErrors: Dispatch<SetStateAction<string[]>>;
  setWorkflowInputMap: Dispatch<SetStateAction<ComfyInputMapItem[]>>;
  setWorkflowOutputNodeIds: Dispatch<SetStateAction<string[]>>;
  setWorkflowOutputPickerNodeId: Dispatch<SetStateAction<string>>;
  setWorkflowOutputShowAll: Dispatch<SetStateAction<boolean>>;
  stringifyJSON: (value?: string | JsonRecord) => string;
  workflowDefinitionError: string;
  workflowDefinitionInfo: ComfyDefinitionInfo;
  workflowDefinitionParse: JsonParseResult;
  workflowForm: WorkflowFormState;
  workflowFormAllowedExecutors: string[];
  workflowInputMap: ComfyInputMapItem[];
  workflowInputPickerKeys: string[];
  workflowInputPickerNodeId: string;
  workflowMappingErrors: string[];
  workflowMetadataError: string;
  workflowMetadataParse: JsonParseResult;
  workflowOutputNodeIds: string[];
  workflowOutputPickerNodeId: string;
}

export const useWorkflowTemplateActions = ({
  comfyWorkflowNodes,
  defaultWorkflowForm,
  extractAllowedExecutorIds,
  extractErrorMessage,
  load,
  normalizeInputNodeMap,
  normalizeOutputNodeIds,
  parseJSON,
  resolveComfyuiDefinition,
  serializeInputNodeMap,
  setWorkflowForm,
  setWorkflowFormAllowedExecutors,
  setWorkflowFormErrors,
  setWorkflowInputMap,
  setWorkflowOutputNodeIds,
  setWorkflowOutputPickerNodeId,
  setWorkflowOutputShowAll,
  stringifyJSON,
  workflowDefinitionError,
  workflowDefinitionInfo,
  workflowDefinitionParse,
  workflowForm,
  workflowFormAllowedExecutors,
  workflowInputMap,
  workflowInputPickerKeys,
  workflowInputPickerNodeId,
  workflowMappingErrors,
  workflowMetadataError,
  workflowMetadataParse,
  workflowOutputNodeIds,
  workflowOutputPickerNodeId,
}: WorkflowTemplateActionsParams) => {
  const syncWorkflowMetadata = useCallback(
    (options?: {
      inputMap?: ComfyInputMapItem[];
      outputNodeIds?: string[];
      allowedExecutorIds?: string[];
    }) => {
      setWorkflowForm((prev) => {
        const base = prev.metadata ? parseJSON(prev.metadata) : {};
        const metadata: Record<string, unknown> = { ...(base || {}) };
        const allowed = options?.allowedExecutorIds ?? workflowFormAllowedExecutors;
        if (allowed && allowed.length > 0) {
          metadata.allowed_executor_ids = allowed;
        } else {
          delete metadata.allowed_executor_ids;
        }
        const inputMap = options?.inputMap ?? workflowInputMap;
        if (inputMap && inputMap.length > 0) {
          metadata.input_node_map = serializeInputNodeMap(inputMap);
        } else {
          delete metadata.input_node_map;
        }
        const outputIds = options?.outputNodeIds ?? workflowOutputNodeIds;
        if (outputIds && outputIds.length > 0) {
          metadata.output_node_ids = outputIds;
        } else {
          delete metadata.output_node_ids;
        }
        return { ...prev, metadata: stringifyJSON(metadata as JsonRecord) };
      });
    },
    [
      parseJSON,
      serializeInputNodeMap,
      setWorkflowForm,
      stringifyJSON,
      workflowFormAllowedExecutors,
      workflowInputMap,
      workflowOutputNodeIds,
    ],
  );

  const updateWorkflowInputMap = useCallback(
    (index: number, patch: Partial<ComfyInputMapItem>) => {
      const next = workflowInputMap.map((item, idx) => (idx === index ? { ...item, ...patch } : item));
      setWorkflowInputMap(next);
      syncWorkflowMetadata({ inputMap: next });
    },
    [setWorkflowInputMap, syncWorkflowMetadata, workflowInputMap],
  );

  const addWorkflowInputMap = useCallback(() => {
    const next = [...workflowInputMap, { field: '', nodeId: '', inputKey: '', valueType: '' }];
    setWorkflowInputMap(next);
    syncWorkflowMetadata({ inputMap: next });
  }, [setWorkflowInputMap, syncWorkflowMetadata, workflowInputMap]);

  const addWorkflowInputMapEntry = useCallback(
    (nodeId: string, inputKey: string, fieldName?: string) => {
      const next = [...workflowInputMap];
      const signature = `${nodeId}::${inputKey}`;
      const exists = next.some((item) => `${item.nodeId}::${item.inputKey}` === signature);
      if (!exists) {
        next.push({ field: fieldName?.trim() || inputKey, nodeId, inputKey, valueType: '' });
        setWorkflowInputMap(next);
        syncWorkflowMetadata({ inputMap: next });
      }
    },
    [setWorkflowInputMap, syncWorkflowMetadata, workflowInputMap],
  );

  const removeWorkflowInputMap = useCallback(
    (index: number) => {
      const next = workflowInputMap.filter((_, idx) => idx !== index);
      setWorkflowInputMap(next);
      syncWorkflowMetadata({ inputMap: next });
    },
    [setWorkflowInputMap, syncWorkflowMetadata, workflowInputMap],
  );

  const updateWorkflowOutputNodes = useCallback(
    (next: string[]) => {
      setWorkflowOutputNodeIds(next);
      syncWorkflowMetadata({ outputNodeIds: next });
    },
    [setWorkflowOutputNodeIds, syncWorkflowMetadata],
  );

  const addWorkflowOutputNodeById = useCallback(
    (nodeId: string) => {
      if (!nodeId) return;
      if (workflowOutputNodeIds.includes(nodeId)) return;
      updateWorkflowOutputNodes([...workflowOutputNodeIds, nodeId]);
    },
    [updateWorkflowOutputNodes, workflowOutputNodeIds],
  );

  const updateWorkflowNodeInputValue = useCallback(
    (nodeId: string, inputKey: string, value: unknown) => {
      const info = resolveComfyuiDefinition(workflowForm.definition);
      if (!info.ok || !info.graph) return;
      const graph = { ...(info.graph as JsonRecord) };
      const rawNode = graph[nodeId];
      if (!rawNode || typeof rawNode !== 'object' || Array.isArray(rawNode)) return;
      const node = { ...(rawNode as JsonRecord) };
      const inputs =
        node.inputs && typeof node.inputs === 'object'
          ? { ...(node.inputs as JsonRecord) }
          : {};
      inputs[inputKey] = value as JsonValue;
      node.inputs = inputs;
      graph[nodeId] = node as JsonValue;
      const payload = info.payload || {};
      const workflowKey =
        typeof (payload as Record<string, unknown>).workflow_key === 'string'
          ? String((payload as Record<string, unknown>).workflow_key).trim()
          : '';
      let nextRecord: JsonRecord;
      if (info.source === 'ui') {
        nextRecord = workflowKey ? { workflow_key: workflowKey, graph } : { graph };
      } else if (info.hasGraphContainer) {
        nextRecord = { ...(payload as JsonRecord), graph };
      } else {
        nextRecord = graph;
      }
      setWorkflowForm((prev) => ({ ...prev, definition: stringifyJSON(nextRecord) }));
    },
    [resolveComfyuiDefinition, setWorkflowForm, stringifyJSON, workflowForm.definition],
  );

  const addWorkflowOutputNode = useCallback(() => {
    if (!workflowOutputPickerNodeId) return;
    if (workflowOutputNodeIds.includes(workflowOutputPickerNodeId)) return;
    updateWorkflowOutputNodes([...workflowOutputNodeIds, workflowOutputPickerNodeId]);
  }, [updateWorkflowOutputNodes, workflowOutputNodeIds, workflowOutputPickerNodeId]);

  const removeWorkflowOutputNode = useCallback(
    (nodeId: string) => {
      updateWorkflowOutputNodes(workflowOutputNodeIds.filter((id) => id !== nodeId));
    },
    [updateWorkflowOutputNodes, workflowOutputNodeIds],
  );

  const addWorkflowInputMappingsForNode = useCallback(() => {
    const nodeId = workflowInputPickerNodeId;
    if (!nodeId || workflowInputPickerKeys.length === 0) return;
    const next = [...workflowInputMap];
    const existing = new Set(next.map((item) => `${item.nodeId}::${item.inputKey}`));
    workflowInputPickerKeys.forEach((key) => {
      const signature = `${nodeId}::${key}`;
      if (existing.has(signature)) return;
      next.push({ field: key, nodeId, inputKey: key, valueType: '' });
      existing.add(signature);
    });
    setWorkflowInputMap(next);
    syncWorkflowMetadata({ inputMap: next });
  }, [
    setWorkflowInputMap,
    syncWorkflowMetadata,
    workflowInputMap,
    workflowInputPickerKeys,
    workflowInputPickerNodeId,
  ]);

  const handleWorkflowSubmit = useCallback(async () => {
    const errors: string[] = [];
    if (!workflowForm.action || !workflowForm.action.trim()) {
      errors.push('请填写 Action');
    }
    if (!workflowForm.name || !workflowForm.name.trim()) {
      errors.push('请填写名称');
    }
    if (!workflowForm.definition || !workflowForm.definition.trim()) {
      errors.push('请先导入或粘贴工作流 JSON');
    }
    if (workflowDefinitionError) {
      errors.push(workflowDefinitionError);
    }
    if (workflowMetadataError) {
      errors.push(workflowMetadataError);
    }
    if (workflowMappingErrors.length > 0) {
      errors.push(...workflowMappingErrors);
    }
    if (errors.length > 0) {
      setWorkflowFormErrors(errors);
      return;
    }
    setWorkflowFormErrors([]);
    const { definition, metadata, ...rest } = workflowForm;
    let definitionPayload = definition && workflowDefinitionParse.ok ? workflowDefinitionParse.value : undefined;
    if (definitionPayload && workflowDefinitionInfo.ok && workflowDefinitionInfo.source === 'ui') {
      const workflowKey =
        typeof (workflowDefinitionInfo.payload as Record<string, unknown>).workflow_key === 'string'
          ? String((workflowDefinitionInfo.payload as Record<string, unknown>).workflow_key).trim()
          : '';
      definitionPayload = workflowKey
        ? { workflow_key: workflowKey, graph: workflowDefinitionInfo.graph }
        : { graph: workflowDefinitionInfo.graph };
    }
    const metadataPayload = metadata && workflowMetadataParse.ok ? workflowMetadataParse.value : {};
    if (workflowFormAllowedExecutors.length > 0) {
      metadataPayload.allowed_executor_ids = workflowFormAllowedExecutors;
    } else {
      delete metadataPayload.allowed_executor_ids;
    }
    const inputMapPayload = serializeInputNodeMap(workflowInputMap);
    if (inputMapPayload.length > 0) {
      metadataPayload.input_node_map = inputMapPayload;
    } else {
      delete metadataPayload.input_node_map;
    }
    if (workflowOutputNodeIds.length > 0) {
      metadataPayload.output_node_ids = workflowOutputNodeIds;
    } else {
      delete metadataPayload.output_node_ids;
    }
    const payload: Partial<Workflow> = {
      ...rest,
      ...(definitionPayload ? { definition: definitionPayload } : {}),
      ...(Object.keys(metadataPayload).length > 0 ? { metadata: metadataPayload } : {}),
    };
    try {
      if (workflowForm.id) {
        await adminApi.updateWorkflow(workflowForm.id, payload);
      } else {
        await adminApi.createWorkflow(payload);
      }
      setWorkflowForm(defaultWorkflowForm);
      setWorkflowFormAllowedExecutors([]);
      setWorkflowInputMap([]);
      setWorkflowOutputNodeIds([]);
      setWorkflowOutputPickerNodeId('');
      setWorkflowOutputShowAll(false);
      setWorkflowFormErrors([]);
      void load();
    } catch (error) {
      console.error('save workflow failed', error);
      setWorkflowFormErrors([extractErrorMessage(error) || '保存失败，请检查网络或参数']);
    }
  }, [
    defaultWorkflowForm,
    extractErrorMessage,
    load,
    serializeInputNodeMap,
    setWorkflowForm,
    setWorkflowFormAllowedExecutors,
    setWorkflowFormErrors,
    setWorkflowInputMap,
    setWorkflowOutputNodeIds,
    setWorkflowOutputPickerNodeId,
    setWorkflowOutputShowAll,
    workflowDefinitionError,
    workflowDefinitionInfo,
    workflowDefinitionParse,
    workflowForm,
    workflowFormAllowedExecutors,
    workflowInputMap,
    workflowMappingErrors,
    workflowMetadataError,
    workflowMetadataParse,
    workflowOutputNodeIds,
  ]);

  const handleWorkflowClone = useCallback(
    (workflow: Workflow) => {
      const { definition, metadata, nextVersion } = buildWorkflowClonePayload(workflow);
      const parsedMeta = (metadata ? parseJSON(metadata) : {}) as JsonRecord;
      const { definition: _ignoredDef, metadata: _ignoredMeta, ...rest } = workflow;
      setWorkflowForm({
        ...rest,
        id: undefined,
        version: nextVersion,
        status: 'inactive',
        definition: stringifyJSON(definition),
        metadata: stringifyJSON(metadata),
      });
      setWorkflowFormAllowedExecutors(extractAllowedExecutorIds(parsedMeta));
      setWorkflowInputMap(normalizeInputNodeMap(parsedMeta));
      setWorkflowOutputNodeIds(normalizeOutputNodeIds(parsedMeta));
      setWorkflowOutputPickerNodeId('');
      setWorkflowOutputShowAll(false);
      setWorkflowFormErrors([]);
    },
    [
      extractAllowedExecutorIds,
      normalizeInputNodeMap,
      normalizeOutputNodeIds,
      parseJSON,
      setWorkflowForm,
      setWorkflowFormAllowedExecutors,
      setWorkflowFormErrors,
      setWorkflowInputMap,
      setWorkflowOutputNodeIds,
      setWorkflowOutputPickerNodeId,
      setWorkflowOutputShowAll,
      stringifyJSON,
    ],
  );

  const handleWorkflowFile = useCallback(
    (files: FileList | null) => {
      if (!files || !files[0]) return;
      const file = files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const json = JSON.parse(event.target?.result as string);
          setWorkflowForm((prev) => ({
            ...prev,
            definition: JSON.stringify(json, null, 2),
          }));
        } catch (error) {
          console.error(error);
        }
      };
      reader.readAsText(file);
    },
    [setWorkflowForm],
  );

  return {
    addWorkflowInputMap,
    addWorkflowInputMapEntry,
    addWorkflowInputMappingsForNode,
    addWorkflowOutputNode,
    addWorkflowOutputNodeById,
    handleWorkflowClone,
    handleWorkflowFile,
    handleWorkflowSubmit,
    removeWorkflowInputMap,
    removeWorkflowOutputNode,
    syncWorkflowMetadata,
    updateWorkflowInputMap,
    updateWorkflowNodeInputValue,
    updateWorkflowOutputNodes,
  };
};
