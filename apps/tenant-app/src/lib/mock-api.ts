/**
 * Mock API Service for GT 2.0 Tenant Application
 * Provides realistic mock data for development and testing
 */

export const mockApi = {
  // Auth endpoints
  auth: {
    login: async (email: string, password: string) => ({
      access_token: 'mock-tenant-jwt-token',
      refresh_token: 'mock-tenant-refresh-token',
      user: {
        id: 'user-1',
        email,
        full_name: 'Jane User',
        tenant: 'Test Company',
        role: 'user',
        avatar_url: null,
      }
    }),
    
    logout: async () => ({ success: true }),
    
    getProfile: async () => ({
      id: 'user-1',
      email: 'jane@test-company.com',
      full_name: 'Jane User',
      tenant: 'Test Company',
      role: 'user',
      avatar_url: null,
      preferences: {
        theme: 'light',
        notifications: true,
        ai_personality: 'balanced',
      }
    }),
  },

  // Conversations endpoints
  conversations: {
    list: async () => ({
      conversations: [
        {
          id: 'conv-1',
          title: 'Research on AI Ethics',
          agent_id: 'asst-1',
          agent_name: 'Research Agent',
          last_message: 'I can help you explore various ethical frameworks...',
          created_at: '2024-01-20T10:00:00Z',
          updated_at: '2024-01-20T11:30:00Z',
          message_count: 12,
        },
        {
          id: 'conv-2',
          title: 'Code Review Session',
          agent_id: 'asst-2',
          agent_name: 'Coding Agent',
          last_message: 'The refactored code looks much cleaner now...',
          created_at: '2024-01-19T14:00:00Z',
          updated_at: '2024-01-19T15:45:00Z',
          message_count: 8,
        },
        {
          id: 'conv-3',
          title: 'Security Analysis',
          agent_id: 'asst-3',
          agent_name: 'Cyber Agent',
          last_message: 'The vulnerability assessment shows...',
          created_at: '2024-01-18T09:00:00Z',
          updated_at: '2024-01-18T10:30:00Z',
          message_count: 6,
        }
      ],
      total: 3
    }),
    
    create: async (data: any) => ({
      id: `conv-${Date.now()}`,
      title: data.title || 'New Conversation',
      agent_id: data.agent_id,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    }),
    
    get: async (id: string) => ({
      id,
      title: 'Research on AI Ethics',
      agent_id: 'asst-1',
      agent_name: 'Research Agent',
      system_prompt: 'You are a helpful research agent...',
      created_at: '2024-01-20T10:00:00Z',
      updated_at: '2024-01-20T11:30:00Z',
      message_count: 12,
      context_sources: ['doc-1', 'doc-2'],
    }),
    
    getMessages: async (id: string) => ({
      messages: [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Can you help me understand the ethical implications of AI in healthcare?',
          created_at: '2024-01-20T10:00:00Z',
        },
        {
          id: 'msg-2',
          role: 'agent',
          content: `I'd be happy to help you explore the ethical implications of AI in healthcare. This is a crucial topic with several key dimensions:

## Key Ethical Considerations

### 1. **Patient Privacy and Data Protection**
- AI systems require vast amounts of patient data for training
- Concerns about data breaches and unauthorized access
- Need for robust anonymization techniques

### 2. **Bias and Fairness**
- AI models can perpetuate existing healthcare disparities
- Training data often underrepresents minority populations
- Risk of discriminatory outcomes in diagnosis and treatment recommendations

### 3. **Transparency and Explainability**
- "Black box" nature of many AI algorithms
- Physicians and patients need to understand AI-driven decisions
- Regulatory requirements for explainable AI in healthcare

### 4. **Accountability and Liability**
- Who is responsible when AI makes an error?
- Legal frameworks still evolving
- Need for clear governance structures

Would you like to explore any of these areas in more detail?`,
          created_at: '2024-01-20T10:01:00Z',
          model_used: 'gpt-4',
          tokens_used: 245,
        },
        {
          id: 'msg-3',
          role: 'user',
          content: 'Yes, can you elaborate on the bias and fairness issues?',
          created_at: '2024-01-20T10:05:00Z',
        },
        {
          id: 'msg-4',
          role: 'agent',
          content: `Certainly! Bias and fairness in healthcare AI is a critical issue that can have life-altering consequences. Let me break this down:

## Sources of Bias in Healthcare AI

### Historical Data Bias
- Medical datasets often reflect past inequities in healthcare access
- Underdiagnosis in certain populations gets encoded into AI models
- Example: Skin cancer detection AI trained primarily on light-skinned patients

### Representation Bias
- Clinical trials historically underrepresented women and minorities
- Rural populations often excluded from datasets
- Socioeconomic factors affecting data availability

## Real-World Consequences

1. **Diagnostic Disparities**: AI may be less accurate for underrepresented groups
2. **Treatment Recommendations**: Biased algorithms might suggest different treatments based on demographics rather than medical need
3. **Resource Allocation**: AI-driven triage systems might systematically disadvantage certain populations

## Mitigation Strategies

- **Diverse Training Data**: Actively collecting representative datasets
- **Bias Testing**: Regular audits for discriminatory patterns
- **Fairness Constraints**: Building equity metrics into model optimization
- **Community Involvement**: Including affected populations in AI development

The goal is to ensure AI enhances healthcare equity rather than exacerbating existing disparities.`,
          created_at: '2024-01-20T10:06:00Z',
          model_used: 'gpt-4',
          tokens_used: 312,
        }
      ],
      total: 4
    }),
    
    sendMessage: async (conversationId: string, content: string) => ({
      id: `msg-${Date.now()}`,
      role: 'agent',
      content: `I understand you're asking about "${content}". Let me help you with that...`,
      created_at: new Date().toISOString(),
      model_used: 'gpt-4',
      tokens_used: Math.floor(Math.random() * 500) + 100,
    }),
  },

  // Agents endpoints
  agents: {
    list: async () => ({
      data: [
        {
          id: 'asst-1',
          name: 'Research Agent',
          description: 'Specialized in research, analysis, and information synthesis',
          template_id: 'research_agent',
          category: 'research',
          personality_config: { tone: 'formal', explanation_depth: 'detailed' },
          resource_preferences: { primary_llm: 'gpt-4', temperature: 0.7 },
          tags: ['research', 'analysis'],
          is_favorite: false,
          conversation_count: 15,
          total_cost_cents: 1250,
          created_at: '2024-01-15T10:00:00Z',
          updated_at: '2024-01-20T11:30:00Z',
        },
        {
          id: 'asst-2',
          name: 'Coding Agent',
          description: 'Expert in software development and code review',
          template_id: 'coding_agent',
          category: 'development',
          personality_config: { tone: 'technical', explanation_depth: 'code-focused' },
          resource_preferences: { primary_llm: 'claude-3-sonnet', temperature: 0.3 },
          tags: ['coding', 'development'],
          is_favorite: true,
          conversation_count: 12,
          total_cost_cents: 890,
          created_at: '2024-01-14T10:00:00Z',
          updated_at: '2024-01-19T15:45:00Z',
        },
        {
          id: 'asst-3',
          name: 'Cybersecurity Agent',
          description: 'Threat detection and security analysis specialist',
          template_id: 'cyber_agent',
          category: 'cybersecurity',
          personality_config: { tone: 'professional', explanation_depth: 'technical' },
          resource_preferences: { primary_llm: 'gpt-4', temperature: 0.2 },
          tags: ['security', 'analysis'],
          is_favorite: false,
          conversation_count: 8,
          total_cost_cents: 670,
          created_at: '2024-01-13T10:00:00Z',
          updated_at: '2024-01-18T10:30:00Z',
        }
      ],
      total: 3,
      limit: 50,
      offset: 0
    }),
    
    create: async (data: any) => ({
      id: `asst-${Date.now()}`,
      ...data,
      created_at: new Date().toISOString(),
      conversation_count: 0,
    }),
    
    get: async (id: string) => ({
      id,
      name: 'Research Agent',
      description: 'Specialized in research, analysis, and information synthesis',
      template_id: 'research_agent',
      category: 'research',
      personality_config: { tone: 'formal', explanation_depth: 'detailed' },
      resource_preferences: { primary_llm: 'gpt-4', temperature: 0.7, max_tokens: 4000 },
      tags: ['research', 'analysis'],
      is_favorite: false,
      conversation_count: 15,
      total_cost_cents: 1250,
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-20T11:30:00Z',
    }),
    
    update: async (id: string, data: any) => ({
      id,
      ...data,
      updated_at: new Date().toISOString(),
    }),
    
    delete: async (id: string) => ({ success: true }),
  },

  // Backward compatibility: agents endpoint delegates to agents
  agents: {
    list: async () => {
      const agentResponse = await mockApi.agents.list();
      return {
        agents: agentResponse.data,
        total: agentResponse.total
      };
    },
    get: async (id: string) => mockApi.agents.get(id),
    create: async (data: any) => mockApi.agents.create(data),
    update: async (id: string, data: any) => mockApi.agents.update(id, data),
    delete: async (id: string) => mockApi.agents.delete(id),
  },

  // Documents endpoints
  documents: {
    list: async () => ({
      documents: [
        {
          id: 'doc-1',
          filename: 'AI_Ethics_Framework.pdf',
          file_type: 'application/pdf',
          file_size: 2456789,
          processing_status: 'completed',
          chunk_count: 45,
          uploaded_by: 'jane@test-company.com',
          created_at: '2024-01-18T10:00:00Z',
          processed_at: '2024-01-18T10:05:00Z',
        },
        {
          id: 'doc-2',
          filename: 'Healthcare_Data_Analysis.docx',
          file_type: 'application/docx',
          file_size: 1234567,
          processing_status: 'completed',
          chunk_count: 32,
          uploaded_by: 'jane@test-company.com',
          created_at: '2024-01-17T14:00:00Z',
          processed_at: '2024-01-17T14:03:00Z',
        },
        {
          id: 'doc-3',
          filename: 'Security_Best_Practices.md',
          file_type: 'text/markdown',
          file_size: 98765,
          processing_status: 'processing',
          chunk_count: 0,
          uploaded_by: 'jane@test-company.com',
          created_at: '2024-01-20T12:00:00Z',
          processed_at: null,
        }
      ],
      total: 3,
      storage_used: 3790121,
      storage_limit: 10737418240, // 10GB
    }),
    
    upload: async (file: File) => ({
      id: `doc-${Date.now()}`,
      filename: file.name,
      file_type: file.type,
      file_size: file.size,
      processing_status: 'pending',
      created_at: new Date().toISOString(),
    }),
    
    delete: async (id: string) => ({ success: true }),
    
    getChunks: async (id: string) => ({
      chunks: [
        {
          id: 'chunk-1',
          document_id: id,
          content: 'This is a sample chunk from the document...',
          chunk_index: 0,
          tokens: 125,
        },
        {
          id: 'chunk-2',
          document_id: id,
          content: 'Another chunk with important information...',
          chunk_index: 1,
          tokens: 98,
        }
      ],
      total: 2,
    }),
  },

  // RAG endpoints
  rag: {
    search: async (query: string, datasetIds?: string[]) => ({
      results: [
        {
          id: 'result-1',
          content: 'AI ethics frameworks typically consider principles like fairness, transparency, and accountability...',
          source: 'AI_Ethics_Framework.pdf',
          relevance_score: 0.92,
          chunk_id: 'chunk-15',
          page_number: 12,
        },
        {
          id: 'result-2',
          content: 'Healthcare data must be handled with strict privacy controls and patient consent...',
          source: 'Healthcare_Data_Analysis.docx',
          relevance_score: 0.87,
          chunk_id: 'chunk-23',
          page_number: 8,
        }
      ],
      total: 2,
      query_embedding_time_ms: 45,
      search_time_ms: 123,
    }),
    
    getDatasets: async () => ({
      datasets: [
        {
          id: 'dataset-1',
          name: 'Research Papers',
          description: 'Collection of AI and healthcare research papers',
          document_count: 12,
          chunk_count: 456,
          vector_count: 456,
          embedding_model: 'text-embedding-3-small',
          status: 'active',
          created_at: '2024-01-10T10:00:00Z',
        },
        {
          id: 'dataset-2',
          name: 'Security Documentation',
          description: 'Cybersecurity best practices and guidelines',
          document_count: 8,
          chunk_count: 234,
          vector_count: 234,
          embedding_model: 'text-embedding-3-small',
          status: 'active',
          created_at: '2024-01-12T10:00:00Z',
        }
      ],
      total: 2,
    }),
    
    createDataset: async (data: any) => ({
      id: `dataset-${Date.now()}`,
      ...data,
      document_count: 0,
      chunk_count: 0,
      vector_count: 0,
      status: 'active',
      created_at: new Date().toISOString(),
    }),
  },

  // Agents endpoints
  agents: {
    list: async () => ({
      agents: [
        {
          id: 'agent-1',
          name: 'Research Specialist',
          agent_type: 'research',
          description: 'Autonomous research agent for deep analysis',
          status: 'idle',
          capabilities: ['web_search', 'document_synthesis', 'report_generation'],
          execution_count: 24,
          last_execution: '2024-01-19T16:00:00Z',
        },
        {
          id: 'agent-2',
          name: 'Code Reviewer',
          agent_type: 'coding',
          description: 'Automated code review and improvement suggestions',
          status: 'idle',
          capabilities: ['code_analysis', 'security_scanning', 'refactoring'],
          execution_count: 18,
          last_execution: '2024-01-18T14:00:00Z',
        }
      ],
      total: 2,
    }),
    
    create: async (data: any) => ({
      id: `agent-${Date.now()}`,
      ...data,
      status: 'idle',
      execution_count: 0,
      created_at: new Date().toISOString(),
    }),
    
    execute: async (agentId: string, task: string) => ({
      execution_id: `exec-${Date.now()}`,
      agent_id: agentId,
      task,
      status: 'running',
      started_at: new Date().toISOString(),
      estimated_duration: 30,
    }),
  },

  // External Services endpoints
  services: {
    list: async () => ({
      services: [
        {
          id: 'svc-1',
          name: 'Canvas LMS',
          type: 'educational_service',
          description: 'Learning Management System',
          icon: '📚',
          status: 'available',
          category: 'education',
        },
        {
          id: 'svc-2',
          name: 'CTFd Platform',
          type: 'cybersecurity_service',
          description: 'Capture The Flag competition platform',
          icon: '🚩',
          status: 'available',
          category: 'cybersecurity',
        },
        {
          id: 'svc-3',
          name: 'Jupyter Hub',
          type: 'development_service',
          description: 'Interactive development environment',
          icon: '📓',
          status: 'available',
          category: 'development',
        },
        {
          id: 'svc-4',
          name: 'Guacamole',
          type: 'remote_access_service',
          description: 'Remote desktop gateway',
          icon: '🖥️',
          status: 'available',
          category: 'infrastructure',
        }
      ],
      total: 4,
    }),
    
    getEmbedConfig: async (serviceId: string) => ({
      iframe_url: `https://${serviceId}.test-company.gt2.com`,
      sandbox_attributes: ['allow-same-origin', 'allow-scripts', 'allow-forms'],
      authentication_token: 'mock-sso-token',
      session_data: {
        user_id: 'user-1',
        tenant_id: 'test-company',
        permissions: ['read', 'write'],
      },
    }),
  },

  // Projects endpoints
  projects: {
    list: async () => ({
      projects: [
        {
          id: 'proj-1',
          name: 'AI Ethics Research',
          description: 'Comprehensive research on ethical implications of AI in healthcare applications',
          project_type: 'research',
          status: 'active',
          completion_percentage: 65,
          linked_resources: ['gpt-4', 'semantic-search', 'document-processor'],
          collaborators: [
            { id: 'user-2', name: 'Alice Johnson' },
            { id: 'user-3', name: 'Bob Smith' }
          ],
          time_invested_minutes: 480,
          ai_interactions_count: 145,
          created_at: '2024-01-10T08:00:00Z',
          last_activity: '2024-01-25T14:30:00Z'
        },
        {
          id: 'proj-2',
          name: 'Security Vulnerability Analysis',
          description: 'Analyzing potential security vulnerabilities in cloud infrastructure',
          project_type: 'analysis',
          status: 'active',
          completion_percentage: 30,
          linked_resources: ['cyber-analyst', 'security-scanner'],
          collaborators: [
            { id: 'user-4', name: 'David Chen' }
          ],
          time_invested_minutes: 240,
          ai_interactions_count: 89,
          created_at: '2024-01-15T10:00:00Z',
          last_activity: '2024-01-25T16:00:00Z'
        },
        {
          id: 'proj-3',
          name: 'Customer Sentiment Dashboard',
          description: 'Building a real-time dashboard for customer sentiment analysis',
          project_type: 'development',
          status: 'completed',
          completion_percentage: 100,
          linked_resources: ['coding-agent', 'github-connector'],
          collaborators: [],
          time_invested_minutes: 960,
          ai_interactions_count: 234,
          created_at: '2023-12-01T09:00:00Z',
          last_activity: '2024-01-20T17:00:00Z'
        },
        {
          id: 'proj-4',
          name: 'Market Trend Analysis Q1',
          description: 'Quarterly market trend analysis and competitor benchmarking',
          project_type: 'analysis',
          status: 'on_hold',
          completion_percentage: 45,
          linked_resources: ['research-agent', 'web-search'],
          collaborators: [
            { id: 'user-5', name: 'Emma Wilson' },
            { id: 'user-6', name: 'Frank Lee' },
            { id: 'user-7', name: 'Grace Kim' }
          ],
          time_invested_minutes: 320,
          ai_interactions_count: 67,
          created_at: '2024-01-05T11:00:00Z',
          last_activity: '2024-01-18T13:00:00Z'
        }
      ],
      total: 4
    }),
    
    create: async (data: any) => ({
      id: `proj-${Date.now()}`,
      ...data,
      status: 'active',
      completion_percentage: 0,
      created_at: new Date().toISOString(),
    }),
  },

  // Games & AI Literacy endpoints
  games: {
    list: async () => ({
      games: [
        {
          id: 'game-1',
          name: 'Strategic Chess',
          type: 'chess',
          category: 'strategic_game',
          description: 'Improve strategic thinking with AI opponents',
          icon: '♟️',
          difficulty_levels: ['beginner', 'intermediate', 'expert'],
          user_rating: 1450,
          games_played: 23,
          win_rate: 0.43,
        },
        {
          id: 'game-2',
          name: 'Logic Puzzles',
          type: 'logic_puzzle',
          category: 'puzzle',
          description: 'Lateral thinking and logical deduction challenges',
          icon: '🧩',
          difficulty_levels: ['easy', 'medium', 'hard'],
          puzzles_solved: 45,
          average_time: 8.5,
          hint_usage_rate: 0.2,
        },
        {
          id: 'game-3',
          name: 'Ethical Dilemmas',
          type: 'philosophical_dilemma',
          category: 'philosophy',
          description: 'Explore ethical frameworks through scenarios',
          icon: '🤔',
          scenarios_completed: 12,
          frameworks_explored: ['utilitarian', 'deontological', 'virtue_ethics'],
          depth_score: 82,
        }
      ],
      total: 3,
      achievements: [
        { id: 'ach-1', name: 'First Victory', icon: '🏆', earned: true },
        { id: 'ach-2', name: 'Strategic Thinker', icon: '🧠', earned: false },
        { id: 'ach-3', name: 'Problem Solver', icon: '💡', earned: true },
      ],
    }),
    
    startGame: async (gameType: string, options?: any) => ({
      game_id: `game-${Date.now()}`,
      game_type: gameType,
      initial_state: {
        board: gameType === 'chess' ? 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR' : null,
        turn: 'player',
        time_remaining: 600,
      },
      ai_opponent: {
        name: 'AI Agent',
        difficulty: options?.difficulty || 'intermediate',
        personality: 'teaching',
      },
    }),
    
    makeMove: async (gameId: string, move: any) => ({
      game_id: gameId,
      player_move: move,
      ai_response: {
        move: 'e7e5',
        explanation: 'I\'m developing my center control...',
        alternative_moves: ['d7d5', 'g8f6'],
      },
      updated_state: {
        board: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR',
        turn: 'player',
        evaluation: 0.3,
      },
      game_status: 'ongoing',
    }),
    
    getProgress: async () => ({
      overall_progress: {
        level: 5,
        experience: 2345,
        next_level_xp: 3000,
        rank: 'Strategic Thinker',
      },
      skill_metrics: {
        strategic_thinking: 72,
        logical_reasoning: 85,
        ethical_reasoning: 68,
        problem_solving: 79,
        ai_collaboration: 91,
      },
      learning_streak: 7,
      total_time_spent: 1234, // minutes
      recommendations: [
        'Try the advanced chess puzzles to improve tactical vision',
        'Explore more ethical dilemmas to strengthen moral reasoning',
      ],
    }),
  },

  // Projects endpoints
  projects: {
    list: async () => ({
      projects: [
        {
          id: 'proj-1',
          name: 'AI Ethics Research',
          description: 'Comprehensive research on AI ethics in healthcare',
          project_type: 'research',
          status: 'active',
          completion_percentage: 65,
          document_count: 8,
          conversation_count: 3,
          created_at: '2024-01-10T10:00:00Z',
          last_activity: '2024-01-20T11:30:00Z',
        },
        {
          id: 'proj-2',
          name: 'Security Audit Tool',
          description: 'Development of automated security audit tool',
          project_type: 'development',
          status: 'active',
          completion_percentage: 40,
          document_count: 5,
          conversation_count: 2,
          created_at: '2024-01-12T10:00:00Z',
          last_activity: '2024-01-19T15:00:00Z',
        }
      ],
      total: 2,
    }),
    
    create: async (data: any) => ({
      id: `proj-${Date.now()}`,
      ...data,
      status: 'active',
      completion_percentage: 0,
      document_count: 0,
      conversation_count: 0,
      created_at: new Date().toISOString(),
    }),
    
    get: async (id: string) => ({
      id,
      name: 'AI Ethics Research',
      description: 'Comprehensive research on AI ethics in healthcare',
      project_type: 'research',
      status: 'active',
      completion_percentage: 65,
      associated_resources: ['asst-1', 'dataset-1'],
      document_references: ['doc-1', 'doc-2'],
      conversation_references: ['conv-1'],
      created_at: '2024-01-10T10:00:00Z',
      last_activity: '2024-01-20T11:30:00Z',
      time_invested_minutes: 450,
      ai_interactions_count: 234,
    }),
  },

  // Settings endpoints
  settings: {
    getPreferences: async () => ({
      theme: 'light',
      language: 'en',
      notifications_enabled: true,
      ai_personality: 'balanced',
      learning_style: 'interactive',
      difficulty_preference: 'adaptive',
      help_system_enabled: true,
      usage_analytics_enabled: true,
    }),
    
    updatePreferences: async (data: any) => ({
      ...data,
      updated_at: new Date().toISOString(),
    }),
  },
};

export default mockApi;