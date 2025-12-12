import { useState, useEffect } from 'react';
import { modelsService, type ModelsResponse, type ModelOption } from '@/services/models-service';

interface UseModelsReturn {
  models: ModelOption[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  isFallback: boolean;
  selectOptions: Array<{value: string, label: string, description: string}>;
}

export function useModels(): UseModelsReturn {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFallback, setIsFallback] = useState(false);

  const fetchModels = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response: ModelsResponse = await modelsService.getAvailableModels();
      
      setModels(response.models);
      setIsFallback(response.fallback || false);
      
      if (response.fallback && response.message) {
        console.warn('Using fallback models:', response.message);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch models';
      setError(errorMessage);
      console.error('Error fetching models:', err);
      
      // Set fallback models on error
      const fallbackResponse = await modelsService.getAvailableModels();
      setModels(fallbackResponse.models);
      setIsFallback(true);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const selectOptions = modelsService.formatForSelect(models);

  return {
    models,
    isLoading,
    error,
    refresh: fetchModels,
    isFallback,
    selectOptions
  };
}

interface UseModelDetailsReturn {
  model: ModelOption | null;
  isLoading: boolean;
  error: string | null;
}

export function useModelDetails(modelId: string | null): UseModelDetailsReturn {
  const [model, setModel] = useState<ModelOption | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!modelId) {
      setModel(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    const fetchModelDetails = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const modelDetails = await modelsService.getModelDetails(modelId);
        setModel(modelDetails);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch model details';
        setError(errorMessage);
        console.error(`Error fetching details for model ${modelId}:`, err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchModelDetails();
  }, [modelId]);

  return {
    model,
    isLoading,
    error
  };
}