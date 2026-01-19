import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class PodiBackendApi implements ICredentialType {
	name = 'podiBackendApi';
	displayName = 'Podi Backend API';

	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'http://127.0.0.1:8099',
			placeholder: 'http://backend:8099',
			description: 'Podi 后端地址（包括协议和端口）',
		},
		{
			displayName: 'Access Token',
			name: 'accessToken',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: 'please-change-me',
			description: '内部服务 Token，默认值即可；如需覆盖可在此填写新的 Access Token',
		},
	];
}
