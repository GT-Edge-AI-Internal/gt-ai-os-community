/**
 * GT 2.0 Games & AI Literacy Service
 * 
 * API client for educational games, puzzles, and learning analytics.
 */

import { api } from './api';

export interface GameData {
  type: string;
  name: string;
  description: string;
  current_rating: number;
  difficulty_levels: string[];
  features: string[];
  estimated_time: string;
  skills_developed: string[];
}

export interface PuzzleData {
  type: string;
  name: string;
  description: string;
  difficulty_range: [number, number];
  skills_developed: string[];
}

export interface DilemmaData {
  type: string;
  name: string;
  description: string;
  topics: string[];
  skills_developed: string[];
}

export interface GameSession {
  session_id: string;
  game_type: string;
  difficulty: string;
  status: 'active' | 'completed' | 'paused';
  start_time: string;
  end_time?: string;
  moves_played?: number;
  current_position?: any;
  ai_analysis?: any;
  performance_metrics?: {
    accuracy: number;
    time_per_move: number;
    blunders: number;
    excellent_moves: number;
  };
}

export interface PuzzleSession {
  session_id: string;
  puzzle_type: string;
  difficulty: number;
  status: 'active' | 'completed' | 'failed';
  start_time: string;
  end_time?: string;
  attempts: number;
  hints_used: number;
  solution_quality?: number;
}

export interface DilemmaSession {
  session_id: string;
  dilemma_type: string;
  topic: string;
  status: 'active' | 'completed';
  start_time: string;
  end_time?: string;
  responses: any[];
  ethical_frameworks_explored: string[];
  depth_score?: number;
}

export interface LearningAnalytics {
  overall_progress: {
    total_sessions: number;
    total_time_minutes: number;
    current_streak: number;
    longest_streak: number;
  };
  game_ratings: {
    chess: number;
    go: number;
    puzzle_level: number;
    philosophical_depth: number;
  };
  cognitive_skills: {
    strategic_thinking: number;
    logical_reasoning: number;
    creative_problem_solving: number;
    ethical_reasoning: number;
    pattern_recognition: number;
    metacognitive_awareness: number;
  };
  thinking_style: {
    system1_reliance: number;
    system2_engagement: number;
    intuition_accuracy: number;
    reflection_frequency: number;
  };
  ai_collaboration: {
    dependency_index: number;
    prompt_engineering: number;
    output_evaluation: number;
    collaborative_solving: number;
  };
  achievements: string[];
  recommendations: string[];
}

export interface StartGameRequest {
  game_type: 'chess' | 'go';
  difficulty: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  features?: string[];
}

export interface StartPuzzleRequest {
  puzzle_type: 'lateral_thinking' | 'logical_deduction' | 'mathematical_reasoning' | 'spatial_reasoning';
  difficulty: number;
}

export interface StartDilemmaRequest {
  dilemma_type: 'ethical_frameworks' | 'game_theory' | 'ai_consciousness';
  topic: string;
}

/**
 * Get available games
 */
export async function getAvailableGames() {
  return api.get<GameData[]>('/api/v1/games/available');
}

/**
 * Get available puzzles
 */
export async function getAvailablePuzzles() {
  return api.get<PuzzleData[]>('/api/v1/games/puzzles/available');
}

/**
 * Get available dilemmas
 */
export async function getAvailableDilemmas() {
  return api.get<DilemmaData[]>('/api/v1/games/dilemmas/available');
}

/**
 * Start new game session
 */
export async function startGame(request: StartGameRequest) {
  return api.post<GameSession>('/api/v1/games/start', request);
}

/**
 * Start new puzzle session
 */
export async function startPuzzle(request: StartPuzzleRequest) {
  return api.post<PuzzleSession>('/api/v1/games/puzzles/start', request);
}

/**
 * Start new dilemma session
 */
export async function startDilemma(request: StartDilemmaRequest) {
  return api.post<DilemmaSession>('/api/v1/games/dilemmas/start', request);
}

/**
 * Get active game session
 */
export async function getGameSession(sessionId: string) {
  return api.get<GameSession>(`/api/v1/games/sessions/${sessionId}`);
}

/**
 * Make move in game
 */
export async function makeMove(sessionId: string, move: any) {
  return api.post<{
    success: boolean;
    game_state: any;
    ai_response?: any;
    analysis?: any;
  }>(`/api/v1/games/sessions/${sessionId}/move`, { move });
}

/**
 * Submit puzzle solution
 */
export async function submitPuzzleSolution(sessionId: string, solution: any) {
  return api.post<{
    correct: boolean;
    explanation: string;
    hints?: string[];
    next_difficulty?: number;
  }>(`/api/v1/games/puzzles/sessions/${sessionId}/solution`, { solution });
}

/**
 * Submit dilemma response
 */
export async function submitDilemmaResponse(sessionId: string, response: any) {
  return api.post<{
    acknowledgment: string;
    follow_up_questions?: string[];
    ethical_analysis?: any;
  }>(`/api/v1/games/dilemmas/sessions/${sessionId}/response`, { response });
}

/**
 * End game session
 */
export async function endGameSession(sessionId: string) {
  return api.post<{
    final_score: any;
    performance_analysis: any;
    skill_improvements: any;
  }>(`/api/v1/games/sessions/${sessionId}/end`);
}

/**
 * Get user's learning analytics
 */
export async function getLearningAnalytics() {
  return api.get<LearningAnalytics>('/api/v1/games/analytics');
}

/**
 * Get game history
 */
export async function getGameHistory(params?: {
  game_type?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.game_type) searchParams.set('game_type', params.game_type);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return api.get<{
    sessions: (GameSession | PuzzleSession | DilemmaSession)[];
    total: number;
  }>(`/api/v1/games/history${query ? `?${query}` : ''}`);
}

/**
 * Get user progress for specific game type
 */
export async function getGameProgress(gameType: string) {
  return api.get<{
    sessions_played: number;
    best_rating: number;
    recent_performance: number;
    skill_progression: any[];
    achievements: string[];
  }>(`/api/v1/games/${gameType}/progress`);
}