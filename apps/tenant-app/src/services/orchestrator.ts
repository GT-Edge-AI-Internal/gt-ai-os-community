/**
 * GT 2.0 Task Orchestrator Service
 * 
 * DeepAgent-inspired intelligent orchestration layer that analyzes user intent
 * and selects optimal resources (datasets, history, or direct LLM) for responses.
 */

import { searchDocuments, searchConversationHistory, ConversationHistoryResult, SearchResult } from './documents';
import { api } from './api';

export interface TaskContext {
  conversationId: string;
  userId: string;
  availableDatasets: string[];
  selectedDatasets: string[];
  historySearchEnabled: boolean;
  agentId?: string;
}

export interface IntentAnalysis {
  intent: 'question' | 'task' | 'creative' | 'analysis';
  complexity: 'simple' | 'moderate' | 'complex';
  needsContext: boolean;
  needsHistory: boolean;
  confidence: number;
  reasoning: string;
}

export interface ResourceSelection {
  useDatasets: boolean;
  useHistory: boolean;
  searchMethod: 'vector' | 'hybrid' | 'keyword';
  datasetIds: string[];
  historyParams?: {
    days_back: number;
    agent_filter?: string[];
  };
}

export interface OrchestrationResult {
  intent: IntentAnalysis;
  resources: ResourceSelection;
  contextSources: ContextSource[];
  historyResults?: ConversationHistoryResult[];
  searchResults?: SearchResult[];
}

export interface ContextSource {
  id: string;
  type: 'dataset' | 'history' | 'direct';
  name: string;
  relevance: number;
  content?: string;
}

export class TaskOrchestrator {
  private readonly INTENT_KEYWORDS = {
    question: ['what', 'how', 'why', 'when', 'where', 'explain', 'tell me about'],
    task: ['create', 'build', 'generate', 'write', 'make', 'develop', 'implement'],
    creative: ['imagine', 'story', 'poem', 'creative', 'artistic', 'design'],
    analysis: ['analyze', 'compare', 'evaluate', 'review', 'assess', 'study']
  };

  private readonly CONTEXT_INDICATORS = [
    'based on', 'according to', 'in the document', 'from the data', 
    'previously', 'earlier', 'last time', 'before'
  ];

  private readonly HISTORY_INDICATORS = [
    'previously', 'earlier', 'last time', 'before', 'remember when',
    'what did we discuss', 'go back to', 'from our conversation'
  ];

  async orchestrate(query: string, context: TaskContext): Promise<OrchestrationResult> {
    // Step 1: Analyze user intent
    const intent = this.analyzeIntent(query);

    // Step 2: Determine resource needs
    const resources = await this.selectResources(query, intent, context);

    // Step 3: Gather context from selected resources
    const contextSources: ContextSource[] = [];
    let historyResults: ConversationHistoryResult[] = [];
    let searchResults: SearchResult[] = [];

    // Execute dataset search if needed
    if (resources.useDatasets && resources.datasetIds.length > 0) {
      try {
        const searchResponse = await searchDocuments({
          query,
          dataset_ids: resources.datasetIds,
          search_method: resources.searchMethod,
          top_k: 5,
          similarity_threshold: 0.7
        });

        if (searchResponse.success) {
          searchResults = searchResponse.data.results;
          searchResults.forEach(result => {
            contextSources.push({
              id: result.chunk_id,
              type: 'dataset',
              name: `Document: ${result.document}`,
              relevance: result.similarity,
              content: result.metadata?.content || result.document
            });
          });
        }
      } catch (error) {
        console.error('Dataset search failed:', error);
      }
    }

    // Execute history search if needed
    if (resources.useHistory) {
      try {
        const historyResponse = await searchConversationHistory({
          query,
          ...resources.historyParams,
          limit: 5
        });

        if (historyResponse.success) {
          historyResults = historyResponse.data;
          historyResults.forEach(result => {
            contextSources.push({
              id: result.message_id,
              type: 'history',
              name: `${result.conversation_title} - ${result.agent_name}`,
              relevance: result.relevance_score,
              content: result.content
            });
          });
        }
      } catch (error) {
        console.error('History search failed:', error);
      }
    }

    // Sort context sources by relevance
    contextSources.sort((a, b) => b.relevance - a.relevance);

    return {
      intent,
      resources,
      contextSources: contextSources.slice(0, 8), // Limit to top 8 sources
      historyResults,
      searchResults
    };
  }

  private analyzeIntent(query: string): IntentAnalysis {
    const lowerQuery = query.toLowerCase();
    const words = lowerQuery.split(/\s+/);

    // Determine primary intent
    let intent: IntentAnalysis['intent'] = 'question';
    let maxScore = 0;

    for (const [intentType, keywords] of Object.entries(this.INTENT_KEYWORDS)) {
      const score = keywords.reduce((acc, keyword) => {
        return acc + (lowerQuery.includes(keyword) ? 1 : 0);
      }, 0);

      if (score > maxScore) {
        maxScore = score;
        intent = intentType as IntentAnalysis['intent'];
      }
    }

    // Determine complexity based on query length and structure
    const complexity: IntentAnalysis['complexity'] = 
      words.length < 5 ? 'simple' :
      words.length < 15 ? 'moderate' : 'complex';

    // Check if context is needed
    const needsContext = this.CONTEXT_INDICATORS.some(indicator => 
      lowerQuery.includes(indicator)
    );

    // Check if history is needed
    const needsHistory = this.HISTORY_INDICATORS.some(indicator => 
      lowerQuery.includes(indicator)
    );

    const confidence = Math.min(0.9, 0.5 + (maxScore * 0.1));

    return {
      intent,
      complexity,
      needsContext: needsContext || intent === 'analysis',
      needsHistory,
      confidence,
      reasoning: `Intent: ${intent}, Keywords found: ${maxScore}, Length: ${words.length} words`
    };
  }

  private async selectResources(
    query: string,
    intent: IntentAnalysis,
    context: TaskContext
  ): Promise<ResourceSelection> {
    const resources: ResourceSelection = {
      useDatasets: false,
      useHistory: false,
      searchMethod: 'hybrid',
      datasetIds: []
    };

    // Use datasets if context is needed and datasets are available
    if ((intent.needsContext || intent.intent === 'analysis') && context.selectedDatasets.length > 0) {
      resources.useDatasets = true;
      resources.datasetIds = context.selectedDatasets;
      
      // Choose search method based on intent and complexity
      if (intent.intent === 'creative') {
        resources.searchMethod = 'vector'; // Better for semantic similarity
      } else if (intent.complexity === 'simple') {
        resources.searchMethod = 'keyword'; // Faster for simple queries
      } else {
        resources.searchMethod = 'hybrid'; // Best overall performance
      }
    }

    // Use history if explicitly requested or if pattern suggests it
    if (context.historySearchEnabled && (intent.needsHistory || intent.complexity === 'complex')) {
      resources.useHistory = true;
      resources.historyParams = {
        days_back: intent.complexity === 'complex' ? 60 : 30,
        agent_filter: context.agentId ? [context.agentId] : undefined
      };
    }

    return resources;
  }

  /**
   * Generate a prompt with context for the LLM
   */
  generateContextualPrompt(
    originalQuery: string,
    orchestrationResult: OrchestrationResult
  ): string {
    let prompt = originalQuery;

    if (orchestrationResult.contextSources.length === 0) {
      return prompt;
    }

    // Add context header
    prompt += '\n\n--- CONTEXT ---\n';
    
    // Add relevant sources
    orchestrationResult.contextSources.forEach((source, index) => {
      prompt += `\n${index + 1}. [${source.type.toUpperCase()}] ${source.name}\n`;
      if (source.content) {
        prompt += `   ${source.content.substring(0, 500)}${source.content.length > 500 ? '...' : ''}\n`;
      }
    });

    prompt += '\n--- END CONTEXT ---\n\n';
    prompt += 'Please answer based on the provided context when relevant. ';
    prompt += 'If the context doesn\'t contain relevant information, please indicate that and provide a general response.';

    return prompt;
  }
}

// Singleton instance
export const taskOrchestrator = new TaskOrchestrator();