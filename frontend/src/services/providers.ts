import type { ProviderConfig } from '../types';
import { mockProviders } from './mock-data';

// ── Mock state ──

let providers = [...mockProviders];
const delay = (ms = 300) => new Promise((r) => setTimeout(r, ms));

// ── API Functions ──

export async function fetchProviders(): Promise<ProviderConfig[]> {
  await delay();
  return [...providers];
}

export async function createProvider(
  data: Omit<ProviderConfig, 'id' | 'created_at' | 'updated_at'>,
): Promise<ProviderConfig> {
  await delay(500);
  const provider: ProviderConfig = {
    ...data,
    id: `p-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  providers.push(provider);
  return provider;
}

export async function updateProvider(
  id: string,
  data: Partial<Pick<ProviderConfig, 'provider_type' | 'base_url' | 'model_name' | 'api_key' | 'temperature' | 'max_tokens' | 'timeout_seconds'>>,
): Promise<ProviderConfig> {
  await delay(500);
  const idx = providers.findIndex((p) => p.id === id);
  if (idx === -1) throw new Error('供应商不存在');
  providers[idx] = {
    ...providers[idx],
    ...data,
    updated_at: new Date().toISOString(),
  };
  return providers[idx];
}

export async function testProvider(
  id: string,
): Promise<{ success: boolean; message: string }> {
  await delay(1500); // Simulate network latency
  const provider = providers.find((p) => p.id === id);
  if (!provider) throw new Error('供应商不存在');
  // Simulate: OpenAI always succeeds, others may vary
  if (provider.api_key.includes('****')) {
    return { success: true, message: '连接成功' };
  }
  return { success: true, message: '连接成功' };
}

export async function setDefaultProvider(id: string): Promise<void> {
  await delay();
  providers = providers.map((p) => ({
    ...p,
    is_default: p.id === id,
    updated_at: p.id === id ? new Date().toISOString() : p.updated_at,
  }));
}

export async function deleteProvider(id: string): Promise<void> {
  await delay();
  const provider = providers.find((p) => p.id === id);
  if (provider?.is_default) throw new Error('无法删除默认供应商，请先设置其他供应商为默认');
  providers = providers.filter((p) => p.id !== id);
}
