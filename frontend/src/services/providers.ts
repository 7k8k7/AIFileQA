import type { ProviderConfig, ProviderTestResult } from '../types';
import api from './api';

type ProviderPayload = Omit<
  ProviderConfig,
  'id' | 'created_at' | 'updated_at' | 'last_test_success' | 'last_test_message' | 'last_test_at'
>;

export async function fetchProviders(): Promise<ProviderConfig[]> {
  const { data } = await api.get<ProviderConfig[]>('/providers');
  return data;
}

export async function fetchProvider(id: string): Promise<ProviderConfig> {
  const { data } = await api.get<ProviderConfig>(`/providers/${id}`);
  return data;
}

export async function createProvider(
  body: ProviderPayload,
): Promise<ProviderConfig> {
  const { data } = await api.post<ProviderConfig>('/providers', body);
  return data;
}

export async function updateProvider(
  id: string,
  body: Partial<Pick<ProviderConfig, 'provider_type' | 'base_url' | 'model_name' | 'api_key' | 'embedding_model' | 'enable_embedding' | 'temperature' | 'max_tokens' | 'timeout_seconds'>>,
): Promise<ProviderConfig> {
  const { data } = await api.put<ProviderConfig>(`/providers/${id}`, body);
  return data;
}

export async function testProvider(
  id: string,
): Promise<ProviderTestResult> {
  const { data } = await api.post<ProviderTestResult>(`/providers/${id}/test`);
  return data;
}

export async function setDefaultProvider(id: string): Promise<void> {
  await api.post(`/providers/${id}/set-default`);
}

export async function deleteProvider(id: string): Promise<void> {
  await api.delete(`/providers/${id}`);
}
