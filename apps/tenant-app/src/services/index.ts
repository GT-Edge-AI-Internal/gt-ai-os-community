/**
 * GT 2.0 Services Index
 * 
 * Central export for all API services with consistent error handling
 * and authentication management.
 */

// Core API infrastructure
export { api, apiClient } from './api';
export type { ApiResponse } from './api';

// Authentication service
export {
  login,
  logout,
  getAuthToken,
  setAuthToken,
  removeAuthToken,
  getUser,
  setUser,
  getTenantInfo,
  setTenantInfo,
  isAuthenticated,
  isTokenValid,
  refreshToken,
  ensureValidToken,
} from './auth';
export type {
  User,
  TenantInfo,
  LoginRequest,
  LoginResponse,
} from './auth';

// Agent management (legacy)
export {
  getAgentTemplates,
  getAgentTemplate,
  listAgents,
  getAgent,
  createAgent,
  updateAgent,
  deleteAgent,
  toggleFavorite,
  getAgentStats,
  getAgentCategories,
} from './agents';
export type {
  Agent,
  AgentTemplate,
  CreateAgentRequest,
  UpdateAgentRequest,
} from './agents';

// Enhanced agent management
export {
  enhancedAgentService,
  listEnhancedAgents,
  getEnhancedAgent,
  createEnhancedAgent,
  updateEnhancedAgent,
  deleteEnhancedAgent,
  forkAgent,
  createFromTemplate,
  getPublicAgents,
  getMyAgents,
  getTeamAgents,
  getOrgAgents,
  getFeaturedAgents,
  searchAgents,
  getAgentsByCategory,
  getUserAgentSummary,
  getPersonalityProfiles,
} from './agents-enhanced';

// Agent management (primary interface) - types only, service already exported above
export type {
  EnhancedAgent,
  CreateEnhancedAgentRequest,
  UpdateEnhancedAgentRequest,
} from './agents-enhanced';

// Agent service aliases for consistency
export { enhancedAgentService as agentService } from './agents-enhanced';
export type {
  PersonalityType,
  Visibility,
  DatasetConnection,
  AgentCategory,
  AccessFilter as AgentAccessFilter,
  PersonalityProfile,
  ModelParameters,
  ExamplePrompt,
  ForkAgentRequest,
  CategoryInfo,
} from './agents-enhanced';

// Document & RAG services
export {
  listDocuments,
  uploadDocument,
  uploadMultipleDocuments,
  getDocument,
  processDocument,
  deleteDocument,
  getDocumentContext,
  searchDocuments,
  getRAGStatistics,
  documentService,
} from './documents';
export type {
  Document,
  SearchResult,
  SearchResponse,
  DocumentContext,
  RAGStatistics,
} from './documents';

// Dataset management services
export {
  datasetService,
  listDatasets,
  getDataset,
  createDataset,
  updateDataset,
  shareDataset,
  deleteDataset,
  addDocumentsToDataset,
  getDatasetStats,
  getMyDatasets,
  getTeamDatasets,
  getOrgDatasets,
  searchDatasets,
  getDatasetsByTag,
  getUserDatasetSummary,
} from './datasets';
export type {
  Dataset,
  CreateDatasetRequest,
  UpdateDatasetRequest,
  ShareDatasetRequest,
  DatasetStats,
  AccessGroup,
  AccessFilter,
} from './datasets';

// Conversation management
export {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  toggleConversationArchive,
  updateConversationTitle,
  getConversationMessages,
  sendMessage,
  createChatWebSocket,
  ChatWebSocket,
} from './conversations';
export type {
  Message,
  Conversation,
  CreateConversationRequest,
  SendMessageRequest,
  StreamingResponse,
} from './conversations';

// Games & AI literacy
export {
  getAvailableGames,
  getAvailablePuzzles,
  getAvailableDilemmas,
  startGame,
  startPuzzle,
  startDilemma,
  getGameSession,
  makeMove,
  submitPuzzleSolution,
  submitDilemmaResponse,
  endGameSession,
  getLearningAnalytics,
  getGameHistory,
  getGameProgress,
} from './games';
export type {
  GameData,
  PuzzleData,
  DilemmaData,
  GameSession,
  PuzzleSession,
  DilemmaSession,
  LearningAnalytics,
  StartGameRequest,
  StartPuzzleRequest,
  StartDilemmaRequest,
} from './games';

// Team collaboration services
export {
  listTeams,
  getTeam,
  createTeam,
  updateTeam,
  deleteTeam,
  listTeamMembers,
  addTeamMember,
  updateMemberPermission,
  removeTeamMember,
  shareResourceToTeam,
  unshareResourceFromTeam,
  listSharedResources,
  getPendingInvitations,
  acceptInvitation,
  declineInvitation,
  getTeamPendingInvitations,
  cancelInvitation,
  getPendingObservableRequests,
  approveObservableRequest,
  revokeObservableStatus,
  requestObservableStatus,
} from './teams';
export type {
  Team,
  TeamMember,
  SharedResource,
  TeamInvitation,
  ObservableRequest,
  TeamListResponse,
  TeamResponse,
  MemberListResponse,
  MemberResponse,
  SharedResourcesResponse,
  CreateTeamRequest,
  UpdateTeamRequest,
  AddMemberRequest,
  UpdateMemberPermissionRequest,
  ShareResourceRequest,
} from './teams';

// Utility functions
export const handleApiError = (response: { error?: string; status: number }) => {
  if (response.error) {
    console.error(`API Error (${response.status}):`, response.error);

    // Handle common error cases
    if (response.status === 401) {
      // Use centralized logout from auth store
      if (typeof window !== 'undefined') {
        import('@/stores/auth-store').then(({ useAuthStore }) => {
          useAuthStore.getState().logout('unauthorized');
        });
      }
    } else if (response.status === 403) {
      // Forbidden - insufficient permissions
      console.warn('Insufficient permissions for this operation');
    } else if (response.status === 429) {
      // Rate limited
      console.warn('Rate limit exceeded. Please try again later.');
    }

    return response.error;
  }
  return null;
};

// Re-export commonly used auth functions for convenience
// Note: removeAuthToken is already exported above in the auth section