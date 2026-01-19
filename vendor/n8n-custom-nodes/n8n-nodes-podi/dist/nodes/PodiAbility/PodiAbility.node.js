"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PodiAbility = void 0;
const n8n_workflow_1 = require("n8n-workflow");
class PodiAbility {
    constructor() {
        this.description = {
            displayName: 'Podi Ability',
            name: 'podiAbility',
            icon: 'file:ability.svg',
            group: ['transform'],
            version: 1,
            description: 'Invoke any Podi atomic ability from n8n',
            defaults: {
                name: 'Podi Ability',
            },
            subtitle: 'Invoke any atomic ability',
            inputs: [n8n_workflow_1.NodeConnectionTypes.Main],
            outputs: [n8n_workflow_1.NodeConnectionTypes.Main],
            credentials: [
                {
                    name: 'podiBackendApi',
                    required: true,
                },
            ],
            codex: {
                categories: ['Artificial Intelligence', 'AI'],
                subcategories: {
                    'Artificial Intelligence': ['Podi Capabilities'],
                    AI: ['Podi Capabilities'],
                },
                alias: ['Podi', 'Podi Ability Node'],
            },
            properties: [
                {
                    displayName: 'Resource',
                    name: 'resource',
                    type: 'options',
                    options: [
                        {
                            name: 'Ability',
                            value: 'ability',
                        },
                    ],
                    default: 'ability',
                },
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                        },
                    },
                    options: [
                        {
                            name: 'Invoke',
                            value: 'invoke',
                            action: 'Invoke Podi ability',
                        },
                    ],
                    default: 'invoke',
                },
                {
                    displayName: 'Ability',
                    name: 'abilityId',
                    type: 'options',
                    typeOptions: {
                        loadOptionsMethod: 'getAbilities',
                    },
                    default: '',
                    description: '选择要触发的原子能力，列表实时来自后端',
                    required: true,
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Use Guided Form',
                    name: 'useGuidedForm',
                    type: 'boolean',
                    default: true,
                    description: '启用后可直接在下方表单填写常用字段，无需手写 JSON；若禁用表单，则完全靠 JSON/高级字段',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Prompt',
                    name: 'formPrompt',
                    type: 'string',
                    typeOptions: { rows: 4 },
                    default: '',
                    description: '描述想要生成/处理的内容（若能力支持）',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Negative Prompt',
                    name: 'formNegativePrompt',
                    type: 'string',
                    typeOptions: { rows: 3 },
                    default: '',
                    description: '需要避开的元素或风格',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Reference Image URL',
                    name: 'formImageUrl',
                    type: 'string',
                    default: '',
                    description: '单张参考图 URL，会映射到 image_url',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Reference Image URLs',
                    name: 'formImageUrls',
                    type: 'string',
                    typeOptions: { rows: 3 },
                    default: '',
                    description: '多张参考图 URL，每行一个；会映射到 image_urls 数组',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Output Size',
                    name: 'formSize',
                    type: 'options',
                    options: [
                        { name: '使用默认', value: '' },
                        { name: '1K · 1024px', value: '1K' },
                        { name: '2K · 2048px', value: '2K' },
                        { name: '4K · 4096px', value: '4K' },
                    ],
                    default: '',
                    description: '部分图生图/修复能力支持 1K/2K/4K 等尺寸',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Aspect Ratio',
                    name: 'formRatio',
                    type: 'options',
                    options: [
                        { name: '使用默认', value: '' },
                        { name: '1:1', value: '1:1' },
                        { name: '4:3', value: '4:3' },
                        { name: '3:4', value: '3:4' },
                        { name: '16:9', value: '16:9' },
                        { name: '9:16', value: '9:16' },
                    ],
                    default: '',
                    description: '指定画幅比例，支持的能力会读取该字段',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Custom Width',
                    name: 'formWidth',
                    type: 'number',
                    typeOptions: { minValue: 64 },
                    default: 0,
                    description: '部分能力支持自定义宽度（像素），0 表示不覆盖',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Custom Height',
                    name: 'formHeight',
                    type: 'number',
                    typeOptions: { minValue: 64 },
                    default: 0,
                    description: '部分能力支持自定义高度（像素），0 表示不覆盖',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Watermark',
                    name: 'formWatermark',
                    type: 'options',
                    options: [
                        { name: '遵循能力默认', value: 'default' },
                        { name: '强制开启', value: 'enable' },
                        { name: '强制关闭', value: 'disable' },
                    ],
                    default: 'default',
                    description: '若能力支持，可主动控制是否输出水印',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Model Override',
                    name: 'formModel',
                    type: 'string',
                    default: '',
                    description: '覆盖默认模型 ID。为空则使用能力默认配置',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                            useGuidedForm: [true],
                        },
                    },
                },
                {
                    displayName: 'Executor ID',
                    name: 'executorId',
                    type: 'string',
                    default: '',
                    description: '可选。覆盖默认执行节点，例如指定不同机房的 ComfyUI',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Workflow Run ID',
                    name: 'workflowRunId',
                    type: 'string',
                    default: '={{$execution.id}}',
                    description: '用于日志关联的唯一 ID，建议保留默认表达式',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Ability Inputs (JSON)',
                    name: 'payloadJson',
                    type: 'json',
                    default: '{}',
                    description: '直接手写 JSON 参数，适合复杂/少见字段；若启用 Guided Form，可只填上方表单，JSON 可为空',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Image URL',
                    name: 'imageUrl',
                    type: 'string',
                    default: '',
                    description: '单图入口，适合传公网图片链接（与 inputs.image_url 效果一致）',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Image Base64',
                    name: 'imageBase64',
                    type: 'string',
                    typeOptions: { rows: 4 },
                    default: '',
                    description: '单图入口，Base64 字符串（含 dataURL 或纯 Base64 均可）',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Image List JSON',
                    name: 'imagesJson',
                    type: 'json',
                    default: '',
                    description: '多图入口，JSON 数组格式 [{"url":"https://..."},{"ossUrl":"https://..."}]，与后台 images 字段一致',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Metadata JSON',
                    name: 'metadataJson',
                    type: 'json',
                    default: '',
                    description: '可选，透传自定义 metadata，后台将写入能力日志',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Callback URL',
                    name: 'callbackUrl',
                    type: 'string',
                    default: '',
                    description: '可选。异步场景下可填写 Webhook URL，成功/失败均会回调',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Callback Headers (JSON)',
                    name: 'callbackHeadersJson',
                    type: 'json',
                    default: '',
                    description: '可选，回调请求头 JSON 结构，如 {"Authorization":"Bearer xxx"}',
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
                {
                    displayName: 'Additional Fields',
                    name: 'additionalFields',
                    type: 'collection',
                    placeholder: 'Add Field',
                    default: {},
                    options: [
                        {
                            displayName: 'Base URL (Override)',
                            name: 'baseUrlOverride',
                            type: 'string',
                            default: '',
                            description: '可覆盖 Credential 中的 Base URL（一般无需修改）',
                        },
                        {
                            displayName: 'Access Token (Override)',
                            name: 'accessTokenOverride',
                            type: 'string',
                            typeOptions: { password: true },
                            default: '',
                            description: '可覆盖 Credential 中的 Access Token（一般无需修改）',
                        },
                    ],
                    displayOptions: {
                        show: {
                            resource: ['ability'],
                            operation: ['invoke'],
                        },
                    },
                },
            ],
        };
        this.methods = {
            loadOptions: {
                async getAbilities() {
                    var _a, _b;
                    const credentials = (await this.getCredentials('podiBackendApi'));
                    const credBaseUrl = (_a = credentials === null || credentials === void 0 ? void 0 : credentials.baseUrl) === null || _a === void 0 ? void 0 : _a.trim();
                    if (!credBaseUrl) {
                        throw new n8n_workflow_1.NodeOperationError(this.getNode(), '请先在 Credential 中配置 Base URL');
                    }
                    const baseUrl = credBaseUrl.replace(/\/$/, '');
                    const token = (_b = credentials === null || credentials === void 0 ? void 0 : credentials.accessToken) === null || _b === void 0 ? void 0 : _b.trim();
                    const headers = { Accept: 'application/json' };
                    if (token) {
                        headers.Authorization = `Bearer ${token}`;
                    }
                    const response = await this.helpers.httpRequest.call(this, {
                        method: 'GET',
                        url: `${baseUrl}/api/abilities/options`,
                        headers,
                        json: true,
                    });
                    const items = response === null || response === void 0 ? void 0 : response.items;
                    if (!Array.isArray(items)) {
                        return [];
                    }
                    const abilityMap = {};
                    for (const entry of items) {
                        if (entry === null || entry === void 0 ? void 0 : entry.id) {
                            abilityMap[entry.id] = entry;
                        }
                    }
                    const nodeData = this.getWorkflowStaticData('node');
                    nodeData.podiAbilityCatalog = abilityMap;
                    return items.map((entry) => {
                        var _a, _b;
                        return ({
                            name: `${(_b = (_a = entry.display_name) !== null && _a !== void 0 ? _a : entry.displayName) !== null && _b !== void 0 ? _b : entry.capability_key}`,
                            value: entry.id,
                            description: `${entry.provider}/${entry.capability_key}`,
                        });
                    });
                },
            },
        };
    }
    async execute() {
        var _a, _b, _c, _d, _e;
        const items = this.getInputData();
        const returnItems = [];
        for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
            const resource = this.getNodeParameter('resource', itemIndex);
            const operation = this.getNodeParameter('operation', itemIndex);
            if (resource !== 'ability' || operation !== 'invoke') {
                continue;
            }
            const credentials = (await this.getCredentials('podiBackendApi'));
            const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) || {};
            const overrideBaseUrl = (_a = additionalFields.baseUrlOverride) === null || _a === void 0 ? void 0 : _a.trim();
            const overrideToken = (_b = additionalFields.accessTokenOverride) === null || _b === void 0 ? void 0 : _b.trim();
            const credentialBaseUrl = (_c = credentials === null || credentials === void 0 ? void 0 : credentials.baseUrl) === null || _c === void 0 ? void 0 : _c.trim();
            const baseUrl = (overrideBaseUrl || credentialBaseUrl || '').replace(/\/$/, '');
            const token = overrideToken || ((_d = credentials === null || credentials === void 0 ? void 0 : credentials.accessToken) === null || _d === void 0 ? void 0 : _d.trim());
            if (!baseUrl) {
                throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Backend Base URL 未设置', { itemIndex });
            }
            const abilityId = this.getNodeParameter('abilityId', itemIndex);
            const executorId = this.getNodeParameter('executorId', itemIndex, '').trim();
            const workflowRunId = this.getNodeParameter('workflowRunId', itemIndex, '').trim();
            const payloadJson = this.getNodeParameter('payloadJson', itemIndex);
            const imageUrl = this.getNodeParameter('imageUrl', itemIndex, '').trim();
            const imageBase64 = this.getNodeParameter('imageBase64', itemIndex, '').trim();
            const imagesJson = this.getNodeParameter('imagesJson', itemIndex);
            const metadataJson = this.getNodeParameter('metadataJson', itemIndex);
            const callbackUrl = this.getNodeParameter('callbackUrl', itemIndex, '').trim();
            const callbackHeadersJson = this.getNodeParameter('callbackHeadersJson', itemIndex);
            const useGuidedForm = this.getNodeParameter('useGuidedForm', itemIndex, true);
            if (!baseUrl) {
                throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Backend Base URL 未设置', { itemIndex });
            }
            if (!abilityId) {
                throw new n8n_workflow_1.NodeOperationError(this.getNode(), '请先选择要运行的能力', { itemIndex });
            }
            const nodeData = this.getWorkflowStaticData('node') || {};
            const catalog = nodeData.podiAbilityCatalog || {};
            const abilityDetails = catalog[abilityId];
            const supportedFieldNames = new Set();
            const schemaFields = (_e = abilityDetails === null || abilityDetails === void 0 ? void 0 : abilityDetails.input_schema) === null || _e === void 0 ? void 0 : _e.fields;
            if (Array.isArray(schemaFields)) {
                for (const field of schemaFields) {
                    const fieldName = field === null || field === void 0 ? void 0 : field.name;
                    if (typeof fieldName === 'string') {
                        supportedFieldNames.add(fieldName);
                    }
                }
            }
            const supportsField = (fieldName) => supportedFieldNames.size === 0 || supportedFieldNames.has(fieldName);
            const guidedInputs = {};
            if (useGuidedForm) {
                const formPrompt = this.getNodeParameter('formPrompt', itemIndex, '').trim();
                if (formPrompt && supportsField('prompt')) {
                    guidedInputs.prompt = formPrompt;
                }
                const formNegative = this.getNodeParameter('formNegativePrompt', itemIndex, '').trim();
                if (formNegative && supportsField('negative_prompt')) {
                    guidedInputs.negative_prompt = formNegative;
                }
                const formSingleImage = this.getNodeParameter('formImageUrl', itemIndex, '').trim();
                if (formSingleImage && supportsField('image_url')) {
                    guidedInputs.image_url = formSingleImage;
                }
                const formImageUrlsRaw = this.getNodeParameter('formImageUrls', itemIndex, '').trim();
                if (formImageUrlsRaw && supportsField('image_urls')) {
                    const parsedUrls = formImageUrlsRaw
                        .split(/\r?\n/)
                        .map((entry) => entry.trim())
                        .filter((entry) => entry.length > 0);
                    if (parsedUrls.length > 0) {
                        guidedInputs.image_urls = parsedUrls;
                    }
                }
                const formSize = this.getNodeParameter('formSize', itemIndex, '').trim();
                if (formSize && supportsField('size')) {
                    guidedInputs.size = formSize;
                }
                const formRatio = this.getNodeParameter('formRatio', itemIndex, '').trim();
                if (formRatio && supportsField('ratio')) {
                    guidedInputs.ratio = formRatio;
                }
                const formWidth = this.getNodeParameter('formWidth', itemIndex, 0);
                if (formWidth && formWidth > 0 && supportsField('width')) {
                    guidedInputs.width = formWidth;
                }
                const formHeight = this.getNodeParameter('formHeight', itemIndex, 0);
                if (formHeight && formHeight > 0 && supportsField('height')) {
                    guidedInputs.height = formHeight;
                }
                const watermarkChoice = this.getNodeParameter('formWatermark', itemIndex, 'default').trim();
                if (watermarkChoice === 'enable' && supportsField('watermark')) {
                    guidedInputs.watermark = true;
                }
                else if (watermarkChoice === 'disable' && supportsField('watermark')) {
                    guidedInputs.watermark = false;
                }
                const formModel = this.getNodeParameter('formModel', itemIndex, '').trim();
                if (formModel && supportsField('model')) {
                    guidedInputs.model = formModel;
                }
            }
            let inputs;
            if (payloadJson && payloadJson !== '{}') {
                try {
                    inputs = JSON.parse(payloadJson);
                }
                catch {
                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Ability Inputs 不是有效的 JSON', {
                        itemIndex,
                    });
                }
            }
            if (Object.keys(guidedInputs).length > 0) {
                inputs = { ...(inputs !== null && inputs !== void 0 ? inputs : {}), ...guidedInputs };
            }
            let images;
            if (imagesJson) {
                try {
                    const parsed = JSON.parse(imagesJson);
                    if (Array.isArray(parsed)) {
                        images = parsed;
                    }
                    else {
                        throw new Error('images JSON 必须是数组');
                    }
                }
                catch {
                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Image List JSON 无法解析', {
                        itemIndex,
                    });
                }
            }
            let metadata;
            if (metadataJson) {
                try {
                    metadata = JSON.parse(metadataJson);
                }
                catch {
                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Metadata JSON 无法解析', {
                        itemIndex,
                    });
                }
            }
            let callbackHeaders;
            if (callbackHeadersJson) {
                try {
                    callbackHeaders = JSON.parse(callbackHeadersJson);
                }
                catch {
                    throw new n8n_workflow_1.NodeOperationError(this.getNode(), 'Callback Headers JSON 无效', {
                        itemIndex,
                    });
                }
            }
            const body = {
                executorId: executorId || undefined,
                inputs,
                imageUrl: imageUrl || undefined,
                imageBase64: imageBase64 || undefined,
                images,
                metadata,
                callbackUrl: callbackUrl || undefined,
                callbackHeaders,
                workflowRunId: workflowRunId || undefined,
            };
            const headers = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers.Authorization = `Bearer ${token}`;
            }
            const responseData = await this.helpers.httpRequest({
                method: 'POST',
                url: `${baseUrl}/api/abilities/${encodeURIComponent(abilityId)}/invoke`,
                headers,
                body,
                json: true,
                returnFullResponse: false,
            });
            returnItems.push({
                json: responseData,
            });
        }
        return [returnItems];
    }
}
exports.PodiAbility = PodiAbility;
//# sourceMappingURL=PodiAbility.node.js.map