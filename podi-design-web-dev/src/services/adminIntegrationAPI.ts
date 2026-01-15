import axios from 'axios';
import { getToken } from '@/utils/http';

const adminClient = axios.create({
  baseURL: '/api/admin',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

adminClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const adminIntegrationAPI = {
  // Executors
  listExecutors: async () => (await adminClient.get('/executors')).data,
  createExecutor: async (payload: any) => (await adminClient.post('/executors', payload)).data,
  updateExecutor: async (id: string, payload: any) => (await adminClient.put(`/executors/${id}`, payload)).data,
  deleteExecutor: async (id: string) => (await adminClient.delete(`/executors/${id}`)).data,
  // Workflows
  listWorkflows: async () => (await adminClient.get('/workflows')).data,
  createWorkflow: async (payload: any) => (await adminClient.post('/workflows', payload)).data,
  updateWorkflow: async (id: string, payload: any) => (await adminClient.put(`/workflows/${id}`, payload)).data,
  deleteWorkflow: async (id: string) => (await adminClient.delete(`/workflows/${id}`)).data,
  // Workflow bindings
  listBindings: async () => (await adminClient.get('/workflow-bindings')).data,
  createBinding: async (payload: any) => (await adminClient.post('/workflow-bindings', payload)).data,
  updateBinding: async (id: string, payload: any) => (await adminClient.put(`/workflow-bindings/${id}`, payload)).data,
  deleteBinding: async (id: string) => (await adminClient.delete(`/workflow-bindings/${id}`)).data,
  // API Keys
  listApiKeys: async () => (await adminClient.get('/api-keys')).data,
  createApiKey: async (payload: any) => (await adminClient.post('/api-keys', payload)).data,
  updateApiKey: async (id: string, payload: any) => (await adminClient.put(`/api-keys/${id}`, payload)).data,
  deleteApiKey: async (id: string) => (await adminClient.delete(`/api-keys/${id}`)).data,
};
