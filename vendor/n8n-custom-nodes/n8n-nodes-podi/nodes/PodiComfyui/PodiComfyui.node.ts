import type {
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';

export class PodiComfyui implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Podi ComfyUI',
		name: 'podiComfyui',
		icon: { light: 'file:example.svg', dark: 'file:example.dark.svg' },
		group: ['transform'],
		version: 1,
		description: 'Invoke internal ComfyUI workflows via Podi backend',
		defaults: {
			name: 'Podi ComfyUI',
		},
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		properties: [
			{
				displayName: 'Backend Base URL',
				name: 'baseUrl',
				type: 'string',
				default: 'http://127.0.0.1:8099',
				description: 'Podi 后端地址（包含端口），例如 http://backend:8099',
			},
			{
				displayName: 'API Token',
				name: 'apiToken',
				type: 'string',
				typeOptions: { password: true },
				default: '',
				description: 'Optional bearer token for backend authentication',
			},
			{
				displayName: 'Executor ID',
				name: 'executorId',
				type: 'string',
				default: '',
				description: '指定后端要调用的执行节点 ID',
			},
			{
				displayName: 'Workflow Key',
				name: 'workflow',
				type: 'options',
				options: [
					{ name: '印花提取', value: 'yinhua_tiqu' },
					{ name: '四方连续', value: 'sifang_lianxu' },
					{ name: '花纹扩图', value: 'huawen_kuotu' },
				],
				default: 'yinhua_tiqu',
				description: 'Matches backend ability workflow_key',
			},
			{
				displayName: 'Payload',
				name: 'payload',
				type: 'json',
				default: '{}',
				description: 'JSON fields to override workflow inputs (比如图片 URL、参数等)',
			},
			{
				displayName: 'Ability ID',
				name: 'abilityId',
				type: 'string',
				default: '',
				description: '可选：若填写则后台会关联到对应 ability 日志',
			},
			{
				displayName: 'Workflow Run ID',
				name: 'workflowRunId',
				type: 'string',
				default: '={{$execution.id}}',
				description: '可传入 n8n execution id 便于日志追踪',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnItems: INodeExecutionData[] = [];

		for (let i = 0; i < items.length; i++) {
			const baseUrl = this.getNodeParameter('baseUrl', i) as string;
			const apiToken = this.getNodeParameter('apiToken', i, '') as string;
			const executorId = this.getNodeParameter('executorId', i) as string;
			const workflowKey = this.getNodeParameter('workflow', i) as string;
			const payload = (this.getNodeParameter('payload', i, {}) as IDataObject) || {};
			const abilityId = this.getNodeParameter('abilityId', i, '') as string;
			const requestedRunId = this.getNodeParameter('workflowRunId', i, '') as string;
			const fallbackRunId = (this.getExecutionId?.() as string | undefined) || `manual-${Date.now()}`;
			const workflowRunId = requestedRunId || fallbackRunId;

			const body = {
				executorId,
				workflowKey,
				workflowParams: payload,
				abilityId: abilityId || undefined,
				workflowRunId,
				source: 'n8n-workflow',
			};

			const headers: IDataObject = {
				'Content-Type': 'application/json',
				'X-Podi-Workflow-Run-Id': workflowRunId,
			};
			if (apiToken) {
				headers.Authorization = `Bearer ${apiToken}`;
			}

			const responseData = await this.helpers.httpRequest({
				method: 'POST',
				url: `${baseUrl.replace(/\/$/, '')}/api/admin/workflows/comfyui/trigger`,
				headers,
				body,
				json: true,
				returnFullResponse: false,
			});

			const result = responseData as IDataObject;
			result.workflowRunId = workflowRunId;
			returnItems.push({ json: result });
		}

		return [returnItems];
	}
}
