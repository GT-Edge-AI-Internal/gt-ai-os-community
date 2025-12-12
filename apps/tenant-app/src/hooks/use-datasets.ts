import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { datasetService, getUserDatasetSummary, type Dataset, type AccessFilter } from '@/services';

export const datasetKeys = {
  all: ['datasets'] as const,
  lists: () => [...datasetKeys.all, 'list'] as const,
  list: (filter?: AccessFilter) => [...datasetKeys.lists(), { filter }] as const,
  summary: () => [...datasetKeys.all, 'summary'] as const,
  detail: (id: string) => [...datasetKeys.all, 'detail', id] as const,
};

export function useDatasets(accessFilter: AccessFilter = 'all') {
  return useQuery({
    queryKey: datasetKeys.list(accessFilter),
    queryFn: async () => {
      const response = await datasetService.listDatasets({ access_filter: accessFilter });
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data || [];
    },
    staleTime: 60000, // 60 seconds
  });
}

export function useDatasetSummary() {
  return useQuery({
    queryKey: datasetKeys.summary(),
    queryFn: async () => {
      const response = await getUserDatasetSummary();
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data;
    },
    staleTime: 60000, // 60 seconds
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (datasetData: any) => {
      const response = await datasetService.createDataset(datasetData);
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all dataset queries to refresh lists and summary
      queryClient.invalidateQueries({ queryKey: datasetKeys.all });
    },
  });
}

export function useUpdateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ datasetId, updateData }: { datasetId: string; updateData: any }) => {
      const response = await datasetService.updateDataset(datasetId, updateData);
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate all dataset queries
      queryClient.invalidateQueries({ queryKey: datasetKeys.all });
      // Also invalidate the specific dataset detail
      queryClient.invalidateQueries({ queryKey: datasetKeys.detail(variables.datasetId) });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (datasetId: string) => {
      const response = await datasetService.deleteDataset(datasetId);
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all dataset queries
      queryClient.invalidateQueries({ queryKey: datasetKeys.all });
    },
  });
}
