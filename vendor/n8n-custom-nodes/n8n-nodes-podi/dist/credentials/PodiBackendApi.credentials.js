"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PodiBackendApi = void 0;
class PodiBackendApi {
    constructor() {
        this.name = 'podiBackendApi';
        this.displayName = 'Podi Backend API';
        this.properties = [
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
}
exports.PodiBackendApi = PodiBackendApi;
//# sourceMappingURL=PodiBackendApi.credentials.js.map