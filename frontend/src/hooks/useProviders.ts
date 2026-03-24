import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchProvider,
  fetchProviders,
  createProvider,
  updateProvider,
  testProvider,
  setDefaultProvider,
  deleteProvider,
} from '../services';
import type { ProviderConfig } from '../types';

const PROVIDERS_KEY = ['providers'] as const;

export function useProviders() {
  return useQuery({
    queryKey: PROVIDERS_KEY,
    queryFn: fetchProviders,
  });
}

export function useProvider(providerId: string | null) {
  return useQuery({
    queryKey: [...PROVIDERS_KEY, providerId],
    queryFn: () => fetchProvider(providerId!),
    enabled: !!providerId,
  });
}

export function useCreateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<ProviderConfig, 'id' | 'created_at' | 'updated_at'>) =>
      createProvider(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useUpdateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<Pick<ProviderConfig, 'provider_type' | 'base_url' | 'model_name' | 'api_key' | 'embedding_model' | 'enable_embedding' | 'temperature' | 'max_tokens' | 'timeout_seconds'>>;
    }) => updateProvider(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useTestProvider() {
  return useMutation({
    mutationFn: (id: string) => testProvider(id),
  });
}

export function useSetDefaultProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => setDefaultProvider(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useDeleteProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteProvider(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}
