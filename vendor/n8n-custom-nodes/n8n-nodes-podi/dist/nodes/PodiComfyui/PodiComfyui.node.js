"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PodiComfyui = void 0;
const n8n_workflow_1 = require("n8n-workflow");
class PodiComfyui {
    constructor() {
        this.description = {
            displayName: 'Podi ComfyUI',
            name: 'podiComfyui',
            icon: { light: 'file:example.svg', dark: 'file:example.dark.svg' },
            group: ['transform'],
            version: 1,
            description: 'Invoke internal ComfyUI workflows via Podi backend',
            defaults: {
                name: 'Podi ComfyUI',
            },
            inputs: [n8n_workflow_1.NodeConnectionTypes.Main],
            outputs: [n8n_workflow_1.NodeConnectionTypes.Main],
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
    }
    async execute() {
        var _a;
        const items = this.getInputData();
        const returnItems = [];
        for (let i = 0; i < items.length; i++) {
            const baseUrl = this.getNodeParameter('baseUrl', i);
            const apiToken = this.getNodeParameter('apiToken', i, '');
            const executorId = this.getNodeParameter('executorId', i);
            const workflowKey = this.getNodeParameter('workflow', i);
            const payload = this.getNodeParameter('payload', i, {}) || {};
            const abilityId = this.getNodeParameter('abilityId', i, '');
            const requestedRunId = this.getNodeParameter('workflowRunId', i, '');
            const fallbackRunId = ((_a = this.getExecutionId) === null || _a === void 0 ? void 0 : _a.call(this)) || `manual-${Date.now()}`;
            const workflowRunId = requestedRunId || fallbackRunId;
            const body = {
                executorId,
                workflowKey,
                workflowParams: payload,
                abilityId: abilityId || undefined,
                workflowRunId,
                source: 'n8n-workflow',
            };
            const headers = {
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
            const result = responseData;
            result.workflowRunId = workflowRunId;
            returnItems.push({ json: result });
        }
        return [returnItems];
    }
}
exports.PodiComfyui = PodiComfyui;
//# sourceMappingURL=PodiComfyui.node.js.map