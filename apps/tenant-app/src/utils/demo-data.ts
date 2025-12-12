/**
 * Demo Data Creation Utilities
 * 
 * Provides functions to reset and populate demo data for GT 2.0
 */

import { agentService, CreateEnhancedAgentRequest } from '@/services';

export interface DemoAgent {
  name: string;
  description: string;
  category: string;
  personality_type: string;
  system_prompt: string;
  model_id: string;
  custom_avatar_url?: string;
  tags: string[];
  example_prompts: Array<{
    text: string;
    category: string;
    expected_behavior: string;
  }>;
}

export const DEMO_AGENTS: DemoAgent[] = [
  {
    name: "Demo Agent",
    description: "A helpful AI agent designed to demonstrate GT 2.0's capabilities with clear, accurate, and friendly responses.",
    category: "general",
    personality_type: "helpful",
    system_prompt: "You are a helpful AI agent built on the GT 2.0 platform. Provide clear, accurate, and friendly responses. Help users understand your capabilities and demonstrate the power of the GT 2.0 system. Always be professional yet approachable in your communication.",
    model_id: "gpt-3.5-turbo",
    tags: ["demo", "general", "helpful", "gt2"],
    example_prompts: [
      {
        text: "What can you help me with?",
        category: "capabilities",
        expected_behavior: "Explain your core capabilities and how you can assist users"
      },
      {
        text: "Tell me about GT 2.0",
        category: "platform",
        expected_behavior: "Provide an overview of the GT 2.0 platform and its features"
      },
      {
        text: "How does conversation work here?",
        category: "usage",
        expected_behavior: "Explain how to use the chat interface and conversation features"
      }
    ]
  }
];

/**
 * Delete all existing agents for the current user
 */
export async function clearAllAgents(): Promise<{ deleted: number; errors: string[] }> {
  try {
    const response = await agentService.listAgents();
    
    if (!response.data?.data) {
      return { deleted: 0, errors: ['Failed to fetch agents'] };
    }

    const agents = response.data.data;
    const errors: string[] = [];
    let deleted = 0;

    console.log(`Found ${agents.length} agents to delete`);

    // If no agents to delete, return early
    if (agents.length === 0) {
      console.log('No agents found to delete');
      return { deleted: 0, errors: [] };
    }

    for (const agent of agents) {
      try {
        const deleteResult = await agentService.deleteAgent(agent.id);
        if (deleteResult.status >= 200 && deleteResult.status < 300) {
          deleted++;
          console.log(`✅ Deleted agent: ${agent.name}`);
        } else {
          // Extract a more user-friendly error message
          const errorMsg = deleteResult.error || 'Server error during deletion';
          errors.push(`${agent.name}: ${errorMsg}`);
          console.warn(`⚠️ Failed to delete ${agent.name}: ${errorMsg}`);
        }
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Unknown error';
        errors.push(`${agent.name}: ${errorMsg}`);
        console.warn(`⚠️ Failed to delete ${agent.name}: ${errorMsg}`);
      }
    }

    // Log summary
    console.log(`Agent deletion summary: ${deleted} deleted, ${errors.length} failed`);

    return { deleted, errors };
  } catch (error) {
    return {
      deleted: 0,
      errors: [`Failed to fetch agents: ${error instanceof Error ? error.message : 'Unknown error'}`]
    };
  }
}

/**
 * Create demo agents
 */
export async function createDemoAgents(): Promise<{ created: number; errors: string[] }> {
  const errors: string[] = [];
  let created = 0;

  for (const demoAgent of DEMO_AGENTS) {
    try {
      const createRequest: CreateEnhancedAgentRequest = {
        name: demoAgent.name,
        description: demoAgent.description,
        category: demoAgent.category,
        personality_type: demoAgent.personality_type as any,
        system_prompt: demoAgent.system_prompt,
        model_id: demoAgent.model_id,
        custom_avatar_url: demoAgent.custom_avatar_url,
        tags: demoAgent.tags,
        example_prompts: demoAgent.example_prompts,
        // Default values for required fields
        visibility: 'individual',
        dataset_connection: 'all',
        require_moderation: false,
        enabled_capabilities: [],
        mcp_integration_ids: [],
        model_parameters: {
          temperature: 0.7,
          max_tokens: 1000,
          top_p: 1.0,
          frequency_penalty: 0,
          presence_penalty: 0
        }
      };

      const result = await agentService.createAgent(createRequest);
      if (result.data && result.status >= 200 && result.status < 300) {
        created++;
        console.log(`✅ Created demo agent: ${demoAgent.name}`);
      } else {
        errors.push(`Failed to create ${demoAgent.name}: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      errors.push(`Failed to create ${demoAgent.name}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  return { created, errors };
}

/**
 * Complete demo data reset - delete all agents and create demo ones
 */
export async function resetToDemo(): Promise<{
  deleted: number;
  created: number;
  errors: string[];
}> {
  console.log('🔄 Starting demo data reset...');
  
  // First, clear all existing agents
  const deleteResult = await clearAllAgents();
  console.log(`Deleted ${deleteResult.deleted} agents`);

  // Wait a moment for deletions to complete
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Then create demo agents
  const createResult = await createDemoAgents();
  console.log(`Created ${createResult.created} demo agents`);

  const allErrors = [...deleteResult.errors, ...createResult.errors];

  if (allErrors.length === 0) {
    console.log('✅ Demo data reset completed successfully');
  } else {
    console.log('⚠️ Demo data reset completed with errors:', allErrors);
  }

  return {
    deleted: deleteResult.deleted,
    created: createResult.created,
    errors: allErrors
  };
}