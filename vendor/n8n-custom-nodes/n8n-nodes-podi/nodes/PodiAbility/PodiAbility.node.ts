import type {
	ICredentialDataDecryptedObject,
	IDataObject,
	IExecuteFunctions,
	ILoadOptionsFunctions,
	INodeExecutionData,
	INodePropertyOptions,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

export class PodiAbility implements INodeType {
	description: INodeTypeDescription = {
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
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
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
				description:
					'直接手写 JSON 参数，适合复杂/少见字段；若启用 Guided Form，可只填上方表单，JSON 可为空',
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
				description:
					'多图入口，JSON 数组格式 [{"url":"https://..."},{"ossUrl":"https://..."}]，与后台 images 字段一致',
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

	methods = {
		loadOptions: {
			async getAbilities(this: ILoadOptionsFunctions) {
				const credentials = (await this.getCredentials('podiBackendApi')) as ICredentialDataDecryptedObject;
				const credBaseUrl = (credentials?.baseUrl as string | undefined)?.trim();
				if (!credBaseUrl) {
					throw new NodeOperationError(this.getNode(), '请先在 Credential 中配置 Base URL');
				}
				const baseUrl = credBaseUrl.replace(/\/$/, '');
				const token = (credentials?.accessToken as string | undefined)?.trim();

				const headers: IDataObject = { Accept: 'application/json' };
				if (token) {
					headers.Authorization = `Bearer ${token}`;
				}

				const response = await this.helpers.httpRequest.call(this, {
					method: 'GET',
					url: `${baseUrl}/api/abilities/options`,
					headers,
					json: true,
				});

				const items = response?.items;
				if (!Array.isArray(items)) {
					return [];
				}

				const abilityMap: Record<string, IDataObject> = {};
				for (const entry of items as IDataObject[]) {
					if (entry?.id) {
						abilityMap[entry.id as string] = entry;
					}
				}
				const nodeData = this.getWorkflowStaticData('node') as IDataObject;
				nodeData.podiAbilityCatalog = abilityMap;

				return items.map((entry: IDataObject) => ({
					name: `${entry.display_name ?? entry.displayName ?? entry.capability_key}`,
					value: entry.id,
					description: `${entry.provider}/${entry.capability_key}`,
				})) as INodePropertyOptions[];
			},
		},
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnItems: INodeExecutionData[] = [];

		for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
			const resource = this.getNodeParameter('resource', itemIndex) as string;
			const operation = this.getNodeParameter('operation', itemIndex) as string;

			if (resource !== 'ability' || operation !== 'invoke') {
				continue;
			}

			const credentials = (await this.getCredentials('podiBackendApi')) as ICredentialDataDecryptedObject;
			const additionalFields = (this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject) || {};
			const overrideBaseUrl = (additionalFields.baseUrlOverride as string | undefined)?.trim();
			const overrideToken = (additionalFields.accessTokenOverride as string | undefined)?.trim();

			const credentialBaseUrl = (credentials?.baseUrl as string | undefined)?.trim();
			const baseUrl = (overrideBaseUrl || credentialBaseUrl || '').replace(/\/$/, '');
			const token = overrideToken || (credentials?.accessToken as string | undefined)?.trim();

			if (!baseUrl) {
				throw new NodeOperationError(this.getNode(), 'Backend Base URL 未设置', { itemIndex });
			}

			const abilityId = this.getNodeParameter('abilityId', itemIndex) as string;
			const executorId = (this.getNodeParameter('executorId', itemIndex, '') as string).trim();
			const workflowRunId = (this.getNodeParameter('workflowRunId', itemIndex, '') as string).trim();
			const payloadJson = this.getNodeParameter('payloadJson', itemIndex) as string;
			const imageUrl = (this.getNodeParameter('imageUrl', itemIndex, '') as string).trim();
			const imageBase64 = (this.getNodeParameter('imageBase64', itemIndex, '') as string).trim();
			const imagesJson = this.getNodeParameter('imagesJson', itemIndex) as string;
			const metadataJson = this.getNodeParameter('metadataJson', itemIndex) as string;
			const callbackUrl = (this.getNodeParameter('callbackUrl', itemIndex, '') as string).trim();
			const callbackHeadersJson = this.getNodeParameter('callbackHeadersJson', itemIndex) as string;
			const useGuidedForm = this.getNodeParameter('useGuidedForm', itemIndex, true) as boolean;

			if (!baseUrl) {
				throw new NodeOperationError(this.getNode(), 'Backend Base URL 未设置', { itemIndex });
			}
			if (!abilityId) {
				throw new NodeOperationError(this.getNode(), '请先选择要运行的能力', { itemIndex });
			}

			const nodeData = (this.getWorkflowStaticData('node') as IDataObject) || {};
			const catalog = (nodeData.podiAbilityCatalog as Record<string, IDataObject> | undefined) || {};
			const abilityDetails = catalog[abilityId];
			const supportedFieldNames = new Set<string>();
			const schemaFields = (abilityDetails?.input_schema as IDataObject | undefined)?.fields;
			if (Array.isArray(schemaFields)) {
				for (const field of schemaFields) {
					const fieldName = (field as IDataObject)?.name;
					if (typeof fieldName === 'string') {
						supportedFieldNames.add(fieldName);
					}
				}
			}
			const supportsField = (fieldName: string) =>
				supportedFieldNames.size === 0 || supportedFieldNames.has(fieldName);

			const guidedInputs: IDataObject = {};
			if (useGuidedForm) {
				const formPrompt = (this.getNodeParameter('formPrompt', itemIndex, '') as string).trim();
				if (formPrompt && supportsField('prompt')) {
					guidedInputs.prompt = formPrompt;
				}
				const formNegative = (this.getNodeParameter('formNegativePrompt', itemIndex, '') as string).trim();
				if (formNegative && supportsField('negative_prompt')) {
					guidedInputs.negative_prompt = formNegative;
				}
				const formSingleImage = (this.getNodeParameter('formImageUrl', itemIndex, '') as string).trim();
				if (formSingleImage && supportsField('image_url')) {
					guidedInputs.image_url = formSingleImage;
				}
				const formImageUrlsRaw = (this.getNodeParameter('formImageUrls', itemIndex, '') as string).trim();
				if (formImageUrlsRaw && supportsField('image_urls')) {
					const parsedUrls = formImageUrlsRaw
						.split(/\r?\n/)
						.map((entry) => entry.trim())
						.filter((entry) => entry.length > 0);
					if (parsedUrls.length > 0) {
						guidedInputs.image_urls = parsedUrls;
					}
				}
				const formSize = (this.getNodeParameter('formSize', itemIndex, '') as string).trim();
				if (formSize && supportsField('size')) {
					guidedInputs.size = formSize;
				}
				const formRatio = (this.getNodeParameter('formRatio', itemIndex, '') as string).trim();
				if (formRatio && supportsField('ratio')) {
					guidedInputs.ratio = formRatio;
				}
				const formWidth = this.getNodeParameter('formWidth', itemIndex, 0) as number;
				if (formWidth && formWidth > 0 && supportsField('width')) {
					guidedInputs.width = formWidth;
				}
				const formHeight = this.getNodeParameter('formHeight', itemIndex, 0) as number;
				if (formHeight && formHeight > 0 && supportsField('height')) {
					guidedInputs.height = formHeight;
				}
				const watermarkChoice = (this.getNodeParameter('formWatermark', itemIndex, 'default') as string).trim();
				if (watermarkChoice === 'enable' && supportsField('watermark')) {
					guidedInputs.watermark = true;
				} else if (watermarkChoice === 'disable' && supportsField('watermark')) {
					guidedInputs.watermark = false;
				}
				const formModel = (this.getNodeParameter('formModel', itemIndex, '') as string).trim();
				if (formModel && supportsField('model')) {
					guidedInputs.model = formModel;
				}
			}

			let inputs: IDataObject | undefined;
			if (payloadJson && payloadJson !== '{}') {
				try {
					inputs = JSON.parse(payloadJson);
				} catch {
					throw new NodeOperationError(this.getNode(), 'Ability Inputs 不是有效的 JSON', {
						itemIndex,
					});
				}
			}
			if (Object.keys(guidedInputs).length > 0) {
				inputs = { ...(inputs ?? {}), ...guidedInputs };
			}

			let images: IDataObject[] | undefined;
			if (imagesJson) {
				try {
					const parsed = JSON.parse(imagesJson);
					if (Array.isArray(parsed)) {
						images = parsed as IDataObject[];
					} else {
						throw new Error('images JSON 必须是数组');
					}
				} catch {
					throw new NodeOperationError(this.getNode(), 'Image List JSON 无法解析', {
						itemIndex,
					});
				}
			}

			let metadata: IDataObject | undefined;
			if (metadataJson) {
				try {
					metadata = JSON.parse(metadataJson);
				} catch {
					throw new NodeOperationError(this.getNode(), 'Metadata JSON 无法解析', {
						itemIndex,
					});
				}
			}

			let callbackHeaders: IDataObject | undefined;
			if (callbackHeadersJson) {
				try {
					callbackHeaders = JSON.parse(callbackHeadersJson);
				} catch {
					throw new NodeOperationError(this.getNode(), 'Callback Headers JSON 无效', {
						itemIndex,
					});
				}
			}

			const body: IDataObject = {
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

			const headers: IDataObject = {
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
				json: responseData as IDataObject,
			});
		}

		return [returnItems];
	}
}
