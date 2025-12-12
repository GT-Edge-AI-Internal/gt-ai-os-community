from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from app.models.game import (
    GameSession, PuzzleSession, PhilosophicalDialogue, 
    LearningAnalytics, GameTemplate
)
import json
import uuid
from datetime import datetime, timedelta
import random


class GameService:
    """Service for managing strategic games (Chess, Go, etc.)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_available_games(self, user_id: str) -> Dict[str, Any]:
        """Get available games and user's current progress"""
        # Get user's analytics to determine appropriate difficulty
        analytics = await self.get_or_create_analytics(user_id)
        
        # Available game types with current user ratings
        available_games = {
            "chess": {
                "name": "Strategic Chess",
                "description": "Classical chess with AI analysis and move commentary",
                "current_rating": analytics.chess_rating,
                "difficulty_levels": ["beginner", "intermediate", "advanced", "expert"],
                "features": ["move_analysis", "position_evaluation", "opening_guidance", "endgame_tutorials"],
                "estimated_time": "15-45 minutes",
                "skills_developed": ["strategic_planning", "pattern_recognition", "calculation_depth"]
            },
            "go": {
                "name": "Strategic Go",
                "description": "The ancient game of Go with territory and influence analysis",
                "current_rating": analytics.go_rating,
                "difficulty_levels": ["beginner", "intermediate", "advanced", "expert"],
                "features": ["territory_visualization", "influence_mapping", "joseki_suggestions", "life_death_training"],
                "estimated_time": "20-60 minutes",
                "skills_developed": ["strategic_concepts", "reading_ability", "intuitive_judgment"]
            }
        }
        
        # Get recent game sessions
        recent_sessions_query = select(GameSession).where(
            and_(
                GameSession.user_id == user_id,
                GameSession.started_at >= datetime.utcnow() - timedelta(days=7)
            )
        ).order_by(desc(GameSession.started_at)).limit(5)
        
        result = await self.db.execute(recent_sessions_query)
        recent_sessions = result.scalars().all()
        
        return {
            "available_games": available_games,
            "recent_sessions": [self._serialize_game_session(session) for session in recent_sessions],
            "user_analytics": self._serialize_analytics(analytics)
        }
    
    async def start_game_session(self, user_id: str, game_type: str, config: Dict[str, Any]) -> GameSession:
        """Start a new game session"""
        analytics = await self.get_or_create_analytics(user_id)
        
        # Determine AI opponent configuration based on user rating
        ai_config = self._configure_ai_opponent(game_type, analytics, config.get('difficulty', 'intermediate'))
        
        session = GameSession(
            user_id=user_id,
            game_type=game_type,
            game_name=config.get('name', f"{game_type.title()} Game"),
            difficulty_level=config.get('difficulty', 'intermediate'),
            ai_opponent_config=ai_config,
            game_rules=self._get_game_rules(game_type),
            current_state=self._initialize_game_state(game_type),
            current_rating=getattr(analytics, f"{game_type}_rating", 1200)
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        return session
    
    async def make_move(self, session_id: str, user_id: str, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a user move and generate AI response"""
        session_query = select(GameSession).where(
            and_(GameSession.id == session_id, GameSession.user_id == user_id)
        )
        result = await self.db.execute(session_query)
        session = result.scalar_one_or_none()
        
        if not session or session.game_status != 'active':
            raise ValueError("Game session not found or not active")
        
        # Process user move
        move_result = self._process_move(session, move_data, is_ai=False)
        
        # Generate AI response
        ai_move = self._generate_ai_move(session)
        ai_result = self._process_move(session, ai_move, is_ai=True)
        
        # Update session state
        session.moves_count += 2  # User move + AI move
        session.last_move_at = datetime.utcnow()
        session.move_history = session.move_history + [move_result, ai_result]
        
        # Check for game end conditions
        game_status = self._check_game_status(session)
        if game_status['ended']:
            session.game_status = 'completed'
            session.completed_at = datetime.utcnow()
            session.outcome = game_status['outcome']
            session.ai_analysis = self._generate_game_analysis(session)
            session.learning_insights = self._extract_learning_insights(session)
            
            # Update user analytics
            await self._update_analytics_after_game(session)
        
        await self.db.commit()
        await self.db.refresh(session)
        
        return {
            "user_move": move_result,
            "ai_move": ai_result,
            "current_state": session.current_state,
            "game_status": game_status,
            "analysis": self._generate_move_analysis(session, move_data) if game_status.get('ended') else None
        }
    
    async def get_game_analysis(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Get detailed analysis of the current game position"""
        session_query = select(GameSession).where(
            and_(GameSession.id == session_id, GameSession.user_id == user_id)
        )
        result = await self.db.execute(session_query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise ValueError("Game session not found")
        
        analysis = {
            "position_evaluation": self._evaluate_position(session),
            "best_moves": self._get_best_moves(session),
            "strategic_insights": self._get_strategic_insights(session),
            "learning_points": self._get_learning_points(session),
            "skill_assessment": self._assess_current_skill(session)
        }
        
        return analysis
    
    async def get_user_game_history(self, user_id: str, game_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's game history with performance trends"""
        query = select(GameSession).where(GameSession.user_id == user_id)
        
        if game_type:
            query = query.where(GameSession.game_type == game_type)
        
        query = query.order_by(desc(GameSession.started_at)).limit(limit)
        
        result = await self.db.execute(query)
        sessions = result.scalars().all()
        
        return [self._serialize_game_session(session) for session in sessions]
    
    def _configure_ai_opponent(self, game_type: str, analytics: LearningAnalytics, difficulty: str) -> Dict[str, Any]:
        """Configure AI opponent based on user skill level"""
        base_config = {
            "personality": "teaching",  # teaching, aggressive, defensive, balanced
            "explanation_mode": True,
            "move_commentary": True,
            "mistake_correction": True,
            "hint_availability": True
        }
        
        if game_type == "chess":
            rating_map = {
                "beginner": analytics.chess_rating - 200,
                "intermediate": analytics.chess_rating,
                "advanced": analytics.chess_rating + 200,
                "expert": analytics.chess_rating + 400
            }
            base_config.update({
                "engine_strength": rating_map.get(difficulty, analytics.chess_rating),
                "opening_book": True,
                "endgame_tablebase": difficulty in ["advanced", "expert"],
                "thinking_time": {"beginner": 1, "intermediate": 3, "advanced": 5, "expert": 10}[difficulty]
            })
        
        elif game_type == "go":
            base_config.update({
                "handicap_stones": {"beginner": 4, "intermediate": 2, "advanced": 0, "expert": 0}[difficulty],
                "commentary_level": {"beginner": "detailed", "intermediate": "moderate", "advanced": "minimal", "expert": "minimal"}[difficulty],
                "joseki_teaching": difficulty in ["beginner", "intermediate"]
            })
        
        return base_config
    
    def _get_game_rules(self, game_type: str) -> Dict[str, Any]:
        """Get standard rules for the game type"""
        rules = {
            "chess": {
                "board_size": "8x8",
                "time_control": "unlimited",
                "special_rules": ["castling", "en_passant", "promotion"],
                "victory_conditions": ["checkmate", "resignation", "time_forfeit"]
            },
            "go": {
                "board_size": "19x19",
                "komi": 6.5,
                "special_rules": ["ko_rule", "suicide_rule"],
                "victory_conditions": ["territory_count", "resignation"]
            }
        }
        return rules.get(game_type, {})
    
    def _initialize_game_state(self, game_type: str) -> Dict[str, Any]:
        """Initialize the starting game state"""
        if game_type == "chess":
            return {
                "board": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",  # FEN notation
                "to_move": "white",
                "castling_rights": "KQkq",
                "en_passant": None,
                "halfmove_clock": 0,
                "fullmove_number": 1
            }
        elif game_type == "go":
            return {
                "board": [[0 for _ in range(19)] for _ in range(19)],  # 0=empty, 1=black, 2=white
                "to_move": "black",
                "captured_stones": {"black": 0, "white": 0},
                "ko_position": None,
                "move_number": 0
            }
        
        return {}
    
    def _process_move(self, session: GameSession, move_data: Dict[str, Any], is_ai: bool) -> Dict[str, Any]:
        """Process a move and update game state"""
        # This would contain game-specific logic for processing moves
        # For now, return a mock processed move
        return {
            "move": move_data,
            "is_ai": is_ai,
            "timestamp": datetime.utcnow().isoformat(),
            "evaluation": random.uniform(-1.0, 1.0),  # Mock evaluation
            "commentary": "Good move!" if not is_ai else "AI plays strategically"
        }
    
    def _generate_ai_move(self, session: GameSession) -> Dict[str, Any]:
        """Generate AI move based on current position"""
        # Mock AI move generation
        if session.game_type == "chess":
            return {"from": "e2", "to": "e4", "piece": "pawn"}
        elif session.game_type == "go":
            return {"x": 10, "y": 10, "color": "white"}
        
        return {}
    
    def _check_game_status(self, session: GameSession) -> Dict[str, Any]:
        """Check if game has ended and determine outcome"""
        # Mock game status check
        return {
            "ended": session.moves_count > 20,  # Mock end condition
            "outcome": random.choice(["win", "loss", "draw"]) if session.moves_count > 20 else None
        }
    
    def _generate_game_analysis(self, session: GameSession) -> Dict[str, Any]:
        """Generate comprehensive game analysis"""
        return {
            "game_quality": random.uniform(0.6, 0.95),
            "key_moments": [
                {"move": 5, "evaluation": "Excellent opening choice"},
                {"move": 12, "evaluation": "Missed tactical opportunity"},
                {"move": 18, "evaluation": "Strong endgame technique"}
            ],
            "skill_demonstration": {
                "tactical_awareness": random.uniform(0.5, 1.0),
                "strategic_understanding": random.uniform(0.4, 0.9),
                "time_management": random.uniform(0.6, 1.0)
            }
        }
    
    def _extract_learning_insights(self, session: GameSession) -> List[str]:
        """Extract key learning insights from the game"""
        insights = [
            "Focus on controlling the center in the opening",
            "Look for tactical combinations before moving",
            "Consider your opponent's threats before making your move",
            "Practice endgame fundamentals"
        ]
        return random.sample(insights, 2)
    
    async def _update_analytics_after_game(self, session: GameSession):
        """Update user analytics based on game performance"""
        analytics = await self.get_or_create_analytics(session.user_id)
        
        # Update game-specific rating
        if session.game_type == "chess":
            rating_change = self._calculate_rating_change(session)
            analytics.chess_rating += rating_change
        elif session.game_type == "go":
            rating_change = self._calculate_rating_change(session)
            analytics.go_rating += rating_change
        
        # Update cognitive skills based on performance
        if session.ai_analysis:
            skill_updates = session.ai_analysis.get("skill_demonstration", {})
            analytics.strategic_thinking_score = self._update_skill_score(
                analytics.strategic_thinking_score, 
                skill_updates.get("strategic_understanding", 0.5)
            )
        
        analytics.total_sessions += 1
        analytics.total_time_minutes += session.time_spent_seconds // 60
        analytics.last_activity_date = datetime.utcnow()
        
        await self.db.commit()
    
    def _calculate_rating_change(self, session: GameSession) -> int:
        """Calculate ELO rating change based on game outcome"""
        base_change = 30
        if session.outcome == "win":
            return base_change
        elif session.outcome == "loss":
            return -base_change
        else:  # draw
            return 0
    
    def _update_skill_score(self, current_score: float, performance: float) -> float:
        """Update skill score using exponential moving average"""
        alpha = 0.1  # Learning rate
        return current_score * (1 - alpha) + performance * 100 * alpha
    
    async def get_or_create_analytics(self, user_id: str) -> LearningAnalytics:
        """Get or create learning analytics for user"""
        query = select(LearningAnalytics).where(LearningAnalytics.user_id == user_id)
        result = await self.db.execute(query)
        analytics = result.scalar_one_or_none()
        
        if not analytics:
            analytics = LearningAnalytics(user_id=user_id)
            self.db.add(analytics)
            await self.db.commit()
            await self.db.refresh(analytics)
        
        return analytics
    
    def _serialize_game_session(self, session: GameSession) -> Dict[str, Any]:
        """Serialize game session for API response"""
        return {
            "id": session.id,
            "game_type": session.game_type,
            "game_name": session.game_name,
            "difficulty_level": session.difficulty_level,
            "game_status": session.game_status,
            "moves_count": session.moves_count,
            "time_spent_seconds": session.time_spent_seconds,
            "current_rating": session.current_rating,
            "outcome": session.outcome,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "learning_insights": session.learning_insights
        }
    
    def _serialize_analytics(self, analytics: LearningAnalytics) -> Dict[str, Any]:
        """Serialize learning analytics for API response"""
        return {
            "chess_rating": analytics.chess_rating,
            "go_rating": analytics.go_rating,
            "total_sessions": analytics.total_sessions,
            "total_time_minutes": analytics.total_time_minutes,
            "current_streak_days": analytics.current_streak_days,
            "strategic_thinking_score": analytics.strategic_thinking_score,
            "logical_reasoning_score": analytics.logical_reasoning_score,
            "pattern_recognition_score": analytics.pattern_recognition_score,
            "ai_collaboration_skills": {
                "dependency_index": analytics.ai_dependency_index,
                "prompt_engineering": analytics.prompt_engineering_skill,
                "output_evaluation": analytics.ai_output_evaluation_skill,
                "collaborative_solving": analytics.collaborative_problem_solving
            }
        }
    
    # Mock helper methods for analysis (would be replaced with actual game engines)
    def _evaluate_position(self, session: GameSession) -> Dict[str, Any]:
        return {"advantage": random.uniform(-2.0, 2.0), "complexity": random.uniform(0.3, 1.0)}
    
    def _get_best_moves(self, session: GameSession) -> List[Dict[str, Any]]:
        return [{"move": "e4", "evaluation": 0.3}, {"move": "d4", "evaluation": 0.2}]
    
    def _get_strategic_insights(self, session: GameSession) -> List[str]:
        return ["Control the center", "Develop pieces actively", "Ensure king safety"]
    
    def _get_learning_points(self, session: GameSession) -> List[str]:
        return ["Practice tactical patterns", "Study endgame principles"]
    
    def _assess_current_skill(self, session: GameSession) -> Dict[str, float]:
        return {
            "tactical_strength": random.uniform(0.4, 0.9),
            "positional_understanding": random.uniform(0.3, 0.8),
            "calculation_accuracy": random.uniform(0.5, 0.95)
        }
    
    def _generate_move_analysis(self, session: GameSession, move_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "move_quality": random.uniform(0.6, 1.0),
            "alternatives": ["Better move: Nf3", "Consider: Bc4"],
            "consequences": "Leads to tactical complications"
        }


class PuzzleService:
    """Service for managing logic puzzles and reasoning challenges"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_available_puzzles(self, user_id: str, category: Optional[str] = None) -> Dict[str, Any]:
        """Get available puzzles based on user skill level"""
        analytics = await self._get_analytics(user_id)
        
        puzzle_categories = {
            "lateral_thinking": {
                "name": "Lateral Thinking",
                "description": "Creative problem-solving that requires thinking outside conventional patterns",
                "difficulty_range": [1, 10],
                "skills_developed": ["creative_thinking", "assumption_challenging", "perspective_shifting"]
            },
            "logical_deduction": {
                "name": "Logical Deduction",
                "description": "Step-by-step reasoning to reach logical conclusions",
                "difficulty_range": [1, 8],
                "skills_developed": ["systematic_thinking", "evidence_evaluation", "logical_consistency"]
            },
            "mathematical_reasoning": {
                "name": "Mathematical Reasoning",
                "description": "Number patterns, sequences, and mathematical logic",
                "difficulty_range": [1, 9],
                "skills_developed": ["pattern_recognition", "analytical_thinking", "quantitative_reasoning"]
            },
            "spatial_reasoning": {
                "name": "Spatial Reasoning",
                "description": "3D visualization and spatial relationship puzzles",
                "difficulty_range": [1, 7],
                "skills_developed": ["spatial_visualization", "mental_rotation", "pattern_matching"]
            }
        }
        
        if category and category in puzzle_categories:
            return {"category": puzzle_categories[category]}
        
        return {
            "categories": puzzle_categories,
            "recommended_difficulty": min(analytics.puzzle_solving_level + 1, 10),
            "user_progress": {
                "current_level": analytics.puzzle_solving_level,
                "puzzles_solved_total": analytics.total_sessions,
                "favorite_categories": []  # Would be determined from session history
            }
        }
    
    async def start_puzzle_session(self, user_id: str, puzzle_type: str, difficulty: int = None) -> PuzzleSession:
        """Start a new puzzle session"""
        analytics = await self._get_analytics(user_id)
        
        if difficulty is None:
            difficulty = min(analytics.puzzle_solving_level + 1, 10)
        
        puzzle_def = self._generate_puzzle(puzzle_type, difficulty)
        
        session = PuzzleSession(
            user_id=user_id,
            puzzle_type=puzzle_type,
            puzzle_category=puzzle_def["category"],
            puzzle_definition=puzzle_def["definition"],
            solution_criteria=puzzle_def["solution_criteria"],
            difficulty_rating=difficulty,
            estimated_time_minutes=puzzle_def.get("estimated_time", 10)
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        return session
    
    async def submit_solution(self, session_id: str, user_id: str, solution: Dict[str, Any], reasoning: str = None) -> Dict[str, Any]:
        """Submit a solution attempt for evaluation"""
        session_query = select(PuzzleSession).where(
            and_(PuzzleSession.id == session_id, PuzzleSession.user_id == user_id)
        )
        result = await self.db.execute(session_query)
        session = result.scalar_one_or_none()
        
        if not session or session.session_status not in ['active', 'hint_requested']:
            raise ValueError("Puzzle session not found or not active")
        
        # Evaluate solution
        evaluation = self._evaluate_solution(session, solution, reasoning)
        
        # Update session
        session.attempts_count += 1
        session.current_attempt = solution
        session.attempt_history = session.attempt_history + [solution]
        session.reasoning_explanation = reasoning
        session.time_spent_seconds += 60  # Mock time tracking
        
        if evaluation["correct"]:
            session.is_solved = True
            session.session_status = 'solved'
            session.solved_at = datetime.utcnow()
            session.solution_quality_score = evaluation["quality_score"]
            session.ai_feedback = evaluation["feedback"]
            
            # Update user analytics
            await self._update_analytics_after_puzzle(session, evaluation)
        
        await self.db.commit()
        await self.db.refresh(session)
        
        return {
            "correct": evaluation["correct"],
            "feedback": evaluation["feedback"],
            "quality_score": evaluation.get("quality_score", 0),
            "hints_available": not evaluation["correct"],
            "next_difficulty_recommendation": evaluation.get("next_difficulty", session.difficulty_rating)
        }
    
    async def get_hint(self, session_id: str, user_id: str, hint_level: int = 1) -> Dict[str, Any]:
        """Provide a hint for the current puzzle"""
        session_query = select(PuzzleSession).where(
            and_(PuzzleSession.id == session_id, PuzzleSession.user_id == user_id)
        )
        result = await self.db.execute(session_query)
        session = result.scalar_one_or_none()
        
        if not session or session.session_status not in ['active', 'hint_requested']:
            raise ValueError("Puzzle session not found or not active")
        
        hint = self._generate_hint(session, hint_level)
        
        # Update session
        session.hints_used_count += 1
        session.hints_given = session.hints_given + [hint]
        session.session_status = 'hint_requested'
        
        await self.db.commit()
        
        return {
            "hint": hint["text"],
            "hint_type": hint["type"],
            "points_deducted": hint.get("point_penalty", 5),
            "hints_remaining": max(0, 3 - session.hints_used_count)
        }
    
    def _generate_puzzle(self, puzzle_type: str, difficulty: int) -> Dict[str, Any]:
        """Generate a puzzle based on type and difficulty"""
        puzzles = {
            "lateral_thinking": {
                "definition": {
                    "question": "A man lives on the 20th floor of an apartment building. Every morning he takes the elevator down to the ground floor. When he comes home, he takes the elevator to the 10th floor and walks the rest of the way... except on rainy days, when he takes the elevator all the way to the 20th floor. Why?",
                    "context": "This is a classic lateral thinking puzzle that requires you to challenge your assumptions."
                },
                "solution_criteria": {
                    "key_insights": ["height limitation", "elevator button accessibility"],
                    "required_elements": ["umbrella usage", "physical constraint explanation"]
                },
                "category": "lateral_thinking",
                "estimated_time": 15
            },
            "logical_deduction": {
                "definition": {
                    "question": "Five people of different nationalities live in five houses of different colors, drink different beverages, smoke different brands, and keep different pets. Using the given clues, determine who owns the fish.",
                    "clues": [
                        "The Brit lives in the red house",
                        "The Swede keeps dogs as pets",
                        "The Dane drinks tea",
                        "The green house is on the left of the white house",
                        "The green house's owner drinks coffee"
                    ]
                },
                "solution_criteria": {
                    "format": "grid_solution",
                    "required_mapping": ["nationality", "house_color", "beverage", "smoke", "pet"]
                },
                "category": "logical_deduction",
                "estimated_time": 25
            }
        }
        
        return puzzles.get(puzzle_type, puzzles["lateral_thinking"])
    
    def _evaluate_solution(self, session: PuzzleSession, solution: Dict[str, Any], reasoning: str = None) -> Dict[str, Any]:
        """Evaluate a puzzle solution"""
        # Mock evaluation logic
        is_correct = random.choice([True, False])  # Would be actual evaluation
        
        quality_score = random.uniform(60, 95) if is_correct else random.uniform(20, 60)
        
        feedback = {
            "correctness": "Excellent reasoning!" if is_correct else "Not quite right, but good thinking.",
            "reasoning_quality": "Clear logical steps" if reasoning else "Consider explaining your reasoning",
            "suggestions": ["Try thinking about the constraints differently", "What assumptions might you be making?"]
        }
        
        return {
            "correct": is_correct,
            "quality_score": quality_score,
            "feedback": feedback,
            "next_difficulty": session.difficulty_rating + (1 if is_correct else 0)
        }
    
    def _generate_hint(self, session: PuzzleSession, hint_level: int) -> Dict[str, Any]:
        """Generate appropriate hint based on puzzle and user progress"""
        hints = [
            {"text": "Consider what might be different about rainy days", "type": "direction"},
            {"text": "Think about the man's physical characteristics", "type": "clue"},
            {"text": "What would an umbrella help him reach?", "type": "leading"}
        ]
        
        return hints[min(hint_level - 1, len(hints) - 1)]
    
    async def _update_analytics_after_puzzle(self, session: PuzzleSession, evaluation: Dict[str, Any]):
        """Update analytics after puzzle completion"""
        analytics = await self._get_analytics(session.user_id)
        
        if evaluation["correct"]:
            analytics.puzzle_solving_level = min(analytics.puzzle_solving_level + 0.1, 10)
            analytics.logical_reasoning_score = self._update_skill_score(
                analytics.logical_reasoning_score, 
                evaluation["quality_score"] / 100
            )
        
        analytics.total_sessions += 1
        analytics.last_activity_date = datetime.utcnow()
        
        await self.db.commit()
    
    async def _get_analytics(self, user_id: str) -> LearningAnalytics:
        """Get user analytics (shared with GameService)"""
        query = select(LearningAnalytics).where(LearningAnalytics.user_id == user_id)
        result = await self.db.execute(query)
        analytics = result.scalar_one_or_none()
        
        if not analytics:
            analytics = LearningAnalytics(user_id=user_id)
            self.db.add(analytics)
            await self.db.commit()
            await self.db.refresh(analytics)
        
        return analytics
    
    def _update_skill_score(self, current_score: float, performance: float) -> float:
        """Update skill score using exponential moving average"""
        alpha = 0.1
        return current_score * (1 - alpha) + performance * 100 * alpha


class PhilosophicalDialogueService:
    """Service for managing philosophical dilemmas and ethical reasoning"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_available_dilemmas(self, user_id: str) -> Dict[str, Any]:
        """Get available philosophical dilemmas"""
        analytics = await self._get_analytics(user_id)
        
        dilemma_types = {
            "ethical_frameworks": {
                "name": "Ethical Framework Analysis",
                "description": "Explore different ethical theories through practical dilemmas",
                "topics": ["trolley_problem", "utilitarian_vs_deontological", "virtue_ethics_scenarios"],
                "skills_developed": ["ethical_reasoning", "framework_application", "moral_consistency"]
            },
            "game_theory": {
                "name": "Game Theory Dilemmas",
                "description": "Strategic decision-making in competitive and cooperative scenarios",
                "topics": ["prisoners_dilemma", "tragedy_of_commons", "coordination_games"],
                "skills_developed": ["strategic_thinking", "cooperation_analysis", "incentive_understanding"]
            },
            "ai_consciousness": {
                "name": "AI Consciousness & Rights",
                "description": "Explore questions about AI sentience, rights, and moral status",
                "topics": ["chinese_room", "turing_test_ethics", "ai_rights", "consciousness_criteria"],
                "skills_developed": ["conceptual_analysis", "consciousness_theory", "future_ethics"]
            }
        }
        
        return {
            "dilemma_types": dilemma_types,
            "user_level": analytics.philosophical_depth_level,
            "recommended_topics": self._get_recommended_topics(analytics),
            "recent_insights": []  # Would come from recent sessions
        }
    
    async def start_dialogue_session(self, user_id: str, dilemma_type: str, topic: str) -> PhilosophicalDialogue:
        """Start a new philosophical dialogue session"""
        scenario = self._get_dilemma_scenario(dilemma_type, topic)
        
        dialogue = PhilosophicalDialogue(
            user_id=user_id,
            dilemma_type=dilemma_type,
            dilemma_title=scenario["title"],
            scenario_description=scenario["description"],
            framework_options=scenario["frameworks"],
            complexity_level=scenario.get("complexity", "intermediate"),
            estimated_discussion_time=scenario.get("estimated_time", 20)
        )
        
        self.db.add(dialogue)
        await self.db.commit()
        await self.db.refresh(dialogue)
        
        return dialogue
    
    async def submit_response(self, dialogue_id: str, user_id: str, response: str, framework: str = None) -> Dict[str, Any]:
        """Submit a response to the philosophical dilemma"""
        dialogue_query = select(PhilosophicalDialogue).where(
            and_(PhilosophicalDialogue.id == dialogue_id, PhilosophicalDialogue.user_id == user_id)
        )
        result = await self.db.execute(dialogue_query)
        dialogue = result.scalar_one_or_none()
        
        if not dialogue or dialogue.dialogue_status != 'active':
            raise ValueError("Dialogue session not found or not active")
        
        # Generate AI response based on user input
        ai_response = self._generate_ai_response(dialogue, response, framework)
        
        # Update dialogue state
        dialogue.exchange_count += 1
        dialogue.dialogue_history = dialogue.dialogue_history + [
            {"speaker": "user", "content": response, "framework": framework, "timestamp": datetime.utcnow().isoformat()},
            {"speaker": "ai", "content": ai_response["content"], "type": ai_response["type"], "timestamp": datetime.utcnow().isoformat()}
        ]
        
        if framework and framework not in dialogue.frameworks_explored:
            dialogue.frameworks_explored = dialogue.frameworks_explored + [framework]
            dialogue.framework_applications += 1
        
        dialogue.last_exchange_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(dialogue)
        
        return {
            "ai_response": ai_response["content"],
            "follow_up_questions": ai_response.get("questions", []),
            "suggested_frameworks": ai_response.get("suggested_frameworks", []),
            "dialogue_progress": {
                "exchanges": dialogue.exchange_count,
                "frameworks_explored": len(dialogue.frameworks_explored),
                "depth_assessment": self._assess_dialogue_depth(dialogue)
            }
        }
    
    async def conclude_dialogue(self, dialogue_id: str, user_id: str, final_position: Dict[str, Any]) -> Dict[str, Any]:
        """Conclude the philosophical dialogue with final assessment"""
        dialogue_query = select(PhilosophicalDialogue).where(
            and_(PhilosophicalDialogue.id == dialogue_id, PhilosophicalDialogue.user_id == user_id)
        )
        result = await self.db.execute(dialogue_query)
        dialogue = result.scalar_one_or_none()
        
        if not dialogue:
            raise ValueError("Dialogue session not found")
        
        # Generate final assessment
        assessment = self._generate_final_assessment(dialogue, final_position)
        
        # Update dialogue
        dialogue.dialogue_status = 'concluded'
        dialogue.concluded_at = datetime.utcnow()
        dialogue.final_position = final_position
        dialogue.key_insights = assessment["insights"]
        dialogue.ai_assessment = assessment["ai_evaluation"]
        
        # Update scores based on dialogue quality
        dialogue.ethical_consistency_score = assessment["scores"]["consistency"]
        dialogue.perspective_flexibility_score = assessment["scores"]["flexibility"]
        dialogue.framework_mastery_score = assessment["scores"]["framework_mastery"]
        dialogue.synthesis_quality_score = assessment["scores"]["synthesis"]
        
        # Update user analytics
        await self._update_analytics_after_dialogue(dialogue, assessment)
        
        await self.db.commit()
        await self.db.refresh(dialogue)
        
        return {
            "final_assessment": assessment,
            "skill_development": assessment["skill_changes"],
            "recommended_next_topics": assessment["recommendations"]
        }
    
    def _get_dilemma_scenario(self, dilemma_type: str, topic: str) -> Dict[str, Any]:
        """Get specific dilemma scenario"""
        scenarios = {
            "ethical_frameworks": {
                "trolley_problem": {
                    "title": "The Trolley Problem",
                    "description": "A runaway trolley is heading towards five people tied to the tracks. You can pull a lever to divert it to another track, where it will kill one person instead. Do you pull the lever?",
                    "frameworks": ["utilitarianism", "deontological", "virtue_ethics", "care_ethics"],
                    "complexity": "intermediate"
                }
            },
            "game_theory": {
                "prisoners_dilemma": {
                    "title": "The Prisoner's Dilemma",
                    "description": "You and your partner are arrested and held separately. You can either confess (defect) or remain silent (cooperate). The outcomes depend on both choices.",
                    "frameworks": ["rational_choice", "social_contract", "evolutionary_ethics"],
                    "complexity": "intermediate"
                }
            },
            "ai_consciousness": {
                "chinese_room": {
                    "title": "The Chinese Room Argument",
                    "description": "Is a computer program that can perfectly simulate understanding Chinese actually understanding Chinese? What does this mean for AI consciousness?",
                    "frameworks": ["functionalism", "behaviorism", "phenomenology", "computational_theory"],
                    "complexity": "advanced"
                }
            }
        }
        
        return scenarios.get(dilemma_type, {}).get(topic, scenarios["ethical_frameworks"]["trolley_problem"])
    
    def _generate_ai_response(self, dialogue: PhilosophicalDialogue, user_response: str, framework: str = None) -> Dict[str, Any]:
        """Generate AI response using Socratic method"""
        # Mock AI response generation
        response_types = ["socratic_question", "framework_challenge", "perspective_shift", "synthesis_prompt"]
        response_type = random.choice(response_types)
        
        responses = {
            "socratic_question": {
                "content": "That's an interesting perspective. What underlying assumptions are you making about the value of individual lives versus collective outcomes?",
                "questions": ["How do you weigh individual rights against collective welfare?", "What if the numbers were different?"],
                "type": "questioning"
            },
            "framework_challenge": {
                "content": "Your utilitarian approach focuses on outcomes. How might a deontologist view this same situation?",
                "suggested_frameworks": ["deontological", "virtue_ethics"],
                "type": "framework_exploration"
            },
            "perspective_shift": {
                "content": "Consider this from the perspective of each person involved. How might their consent or agency factor into your decision?",
                "questions": ["Does intent matter as much as outcome?", "What about the rights of those who cannot consent?"],
                "type": "perspective_expansion"
            },
            "synthesis_prompt": {
                "content": "You've explored multiple frameworks. Can you synthesize these different approaches into a coherent position?",
                "type": "synthesis"
            }
        }
        
        return responses[response_type]
    
    def _assess_dialogue_depth(self, dialogue: PhilosophicalDialogue) -> Dict[str, Any]:
        """Assess the depth and quality of the dialogue"""
        return {
            "conceptual_depth": min(dialogue.exchange_count / 5, 1.0),
            "framework_breadth": len(dialogue.frameworks_explored) / 4,
            "synthesis_attempts": dialogue.synthesis_attempts,
            "perspective_shifts": dialogue.perspective_shifts
        }
    
    def _generate_final_assessment(self, dialogue: PhilosophicalDialogue, final_position: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive final assessment"""
        return {
            "insights": [
                "Demonstrated understanding of utilitarian reasoning",
                "Showed ability to consider multiple perspectives",
                "Struggled with synthesizing competing frameworks"
            ],
            "scores": {
                "consistency": random.uniform(0.6, 0.9),
                "flexibility": random.uniform(0.5, 0.8),
                "framework_mastery": random.uniform(0.4, 0.85),
                "synthesis": random.uniform(0.3, 0.7)
            },
            "skill_changes": {
                "ethical_reasoning": "+5%",
                "perspective_taking": "+3%",
                "logical_consistency": "+2%"
            },
            "recommendations": [
                "Explore virtue ethics in more depth",
                "Practice synthesizing competing moral intuitions",
                "Consider real-world applications of ethical frameworks"
            ],
            "ai_evaluation": {
                "dialogue_quality": "Good engagement with multiple perspectives",
                "growth_areas": "Framework synthesis and practical application",
                "strengths": "Clear reasoning and willingness to explore"
            }
        }
    
    async def _update_analytics_after_dialogue(self, dialogue: PhilosophicalDialogue, assessment: Dict[str, Any]):
        """Update user analytics after dialogue completion"""
        analytics = await self._get_analytics(dialogue.user_id)
        
        # Update philosophical reasoning skills
        analytics.ethical_reasoning_score = self._update_skill_score(
            analytics.ethical_reasoning_score,
            assessment["scores"]["consistency"]
        )
        
        analytics.philosophical_depth_level = min(
            analytics.philosophical_depth_level + 0.1, 
            10
        )
        
        analytics.total_sessions += 1
        analytics.last_activity_date = datetime.utcnow()
        
        await self.db.commit()
    
    def _get_recommended_topics(self, analytics: LearningAnalytics) -> List[str]:
        """Get recommended topics based on user progress"""
        if analytics.philosophical_depth_level < 3:
            return ["trolley_problem", "prisoners_dilemma"]
        elif analytics.philosophical_depth_level < 6:
            return ["virtue_ethics_scenarios", "tragedy_of_commons", "ai_rights"]
        else:
            return ["chinese_room", "consciousness_criteria", "coordination_games"]
    
    async def _get_analytics(self, user_id: str) -> LearningAnalytics:
        """Get user analytics"""
        query = select(LearningAnalytics).where(LearningAnalytics.user_id == user_id)
        result = await self.db.execute(query)
        analytics = result.scalar_one_or_none()
        
        if not analytics:
            analytics = LearningAnalytics(user_id=user_id)
            self.db.add(analytics)
            await self.db.commit()
            await self.db.refresh(analytics)
        
        return analytics
    
    def _update_skill_score(self, current_score: float, performance: float) -> float:
        """Update skill score using exponential moving average"""
        alpha = 0.1
        return current_score * (1 - alpha) + performance * 100 * alpha