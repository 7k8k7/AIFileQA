import type { ProviderConfig } from '../types';
import api from './api';

export async function fetchProviders(): Promise<ProviderConfig[]> {
  const { data } = await api.get<ProviderConfig[]>('/providers');
  return data;
}

export async function fetchProvider(id: string): Promise<ProviderConfig> {
  const { data } = await api.get<ProviderConfig>(`/providers/${id}`);
  return data;
}

export async function createProvider(
  body: Omit<ProviderConfig, 'id' | 'created_at' | 'updated_at'>,
): Promise<ProviderConfig> {
  const { data } = await api.post<ProviderConfig>('/providers', body);
  return data;
}

export async function updateProvider(
  id: string,
  body: Partial<Pick<ProviderConfig, 'provider_type' | 'base_url' | 'model_name' | 'api_key' | 'temperature' | 'max_tokens' | 'timeout_seconds'>>,
): Promise<ProviderConfig> {
  const { data } = await api.put<ProviderConfig>(`/providers/${id}`, body);
  return data;
}

export async function testProvider(
  id: string,
): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post<{ success: boolean; message: string }>(`/providers/${id}/test`);
  return data;
}

export async function setDefaultProvider(id: string): Promise<void> {
  await api.post(`/providers/${id}/set-default`);
}

export async function deleteProvider(id: string): Promise<void> {
  await api.delete(`/providers/${id}`);
}
