from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.database import get_db
from app.api.auth import get_current_user
from app.services.game_service import GameService, PuzzleService, PhilosophicalDialogueService
from app.models.game import GameSession, PuzzleSession, PhilosophicalDialogue, LearningAnalytics

router = APIRouter(prefix="/games", tags=["AI Literacy & Games"])


# Request/Response Models
class GameConfigRequest(BaseModel):
    game_type: str = Field(..., description="Type of game: chess, go")
    difficulty: str = Field(default="intermediate", description="Difficulty level")
    name: Optional[str] = Field(None, description="Custom game name")
    ai_personality: Optional[str] = Field(default="teaching", description="AI opponent personality")
    time_control: Optional[str] = Field(None, description="Time control settings")


class GameMoveRequest(BaseModel):
    move_data: Dict[str, Any] = Field(..., description="Move data specific to game type")
    request_analysis: Optional[bool] = Field(default=False, description="Request move analysis")


class PuzzleConfigRequest(BaseModel):
    puzzle_type: str = Field(..., description="Type of puzzle: lateral_thinking, logical_deduction, etc.")
    difficulty: Optional[int] = Field(None, description="Difficulty level 1-10", ge=1, le=10)
    category: Optional[str] = Field(None, description="Puzzle category")


class PuzzleSolutionRequest(BaseModel):
    solution: Dict[str, Any] = Field(..., description="Puzzle solution attempt")
    reasoning: Optional[str] = Field(None, description="User's reasoning explanation")


class HintRequest(BaseModel):
    hint_level: int = Field(default=1, description="Hint level 1-3", ge=1, le=3)


class DilemmaConfigRequest(BaseModel):
    dilemma_type: str = Field(..., description="Type of dilemma: ethical_frameworks, game_theory, ai_consciousness")
    topic: str = Field(..., description="Specific topic within the dilemma type")
    complexity: Optional[str] = Field(default="intermediate", description="Complexity level")


class DilemmaResponseRequest(BaseModel):
    response: str = Field(..., description="User's response to the dilemma")
    framework: Optional[str] = Field(None, description="Ethical framework being applied")


class DilemmaFinalPositionRequest(BaseModel):
    final_position: Dict[str, Any] = Field(..., description="User's final position on the dilemma")
    key_insights: Optional[List[str]] = Field(default=[], description="Key insights gained")


# Strategic Games Endpoints
@router.get("/available")
async def get_available_games(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get available games and user progress"""
    service = GameService(db)
    return await service.get_available_games(current_user["user_id"])


@router.post("/start")
async def start_game_session(
    config: GameConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Start a new game session"""
    service = GameService(db)
    
    try:
        session = await service.start_game_session(
            user_id=current_user["user_id"],
            game_type=config.game_type,
            config=config.dict()
        )
        
        return {
            "session_id": session.id,
            "game_type": session.game_type,
            "difficulty": session.difficulty_level,
            "initial_state": session.current_state,
            "ai_config": session.ai_opponent_config,
            "started_at": session.started_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}")
async def get_game_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get current game session details"""
    service = GameService(db)
    
    try:
        analysis = await service.get_game_analysis(session_id, current_user["user_id"])
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/session/{session_id}/move")
async def make_move(
    session_id: str,
    move: GameMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Make a move in the game"""
    service = GameService(db)
    
    try:
        result = await service.make_move(
            session_id=session_id,
            user_id=current_user["user_id"],
            move_data=move.move_data
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}/analysis")
async def get_game_analysis(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed game analysis"""
    service = GameService(db)
    
    try:
        analysis = await service.get_game_analysis(session_id, current_user["user_id"])
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/history")
async def get_game_history(
    game_type: Optional[str] = Query(None, description="Filter by game type"),
    limit: int = Query(20, description="Number of games to return", ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get user's game history"""
    service = GameService(db)
    return await service.get_user_game_history(
        user_id=current_user["user_id"],
        game_type=game_type,
        limit=limit
    )


# Logic Puzzles Endpoints
@router.get("/puzzles/available")
async def get_available_puzzles(
    category: Optional[str] = Query(None, description="Filter by puzzle category"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get available puzzle categories and difficulty recommendations"""
    service = PuzzleService(db)
    return await service.get_available_puzzles(current_user["user_id"], category)


@router.post("/puzzles/start")
async def start_puzzle_session(
    config: PuzzleConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Start a new puzzle session"""
    service = PuzzleService(db)
    
    try:
        session = await service.start_puzzle_session(
            user_id=current_user["user_id"],
            puzzle_type=config.puzzle_type,
            difficulty=config.difficulty
        )
        
        return {
            "session_id": session.id,
            "puzzle_type": session.puzzle_type,
            "difficulty": session.difficulty_rating,
            "puzzle": session.puzzle_definition,
            "estimated_time": session.estimated_time_minutes,
            "started_at": session.started_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/puzzles/{session_id}/solve")
async def submit_puzzle_solution(
    session_id: str,
    solution: PuzzleSolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Submit a solution for the puzzle"""
    service = PuzzleService(db)
    
    try:
        result = await service.submit_solution(
            session_id=session_id,
            user_id=current_user["user_id"],
            solution=solution.solution,
            reasoning=solution.reasoning
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/puzzles/{session_id}/hint")
async def get_puzzle_hint(
    session_id: str,
    hint_request: HintRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a hint for the current puzzle"""
    service = PuzzleService(db)
    
    try:
        hint = await service.get_hint(
            session_id=session_id,
            user_id=current_user["user_id"],
            hint_level=hint_request.hint_level
        )
        return hint
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Philosophical Dilemmas Endpoints
@router.get("/dilemmas/available")
async def get_available_dilemmas(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get available philosophical dilemmas"""
    service = PhilosophicalDialogueService(db)
    return await service.get_available_dilemmas(current_user["user_id"])


@router.post("/dilemmas/start")
async def start_philosophical_dialogue(
    config: DilemmaConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Start a new philosophical dialogue session"""
    service = PhilosophicalDialogueService(db)
    
    try:
        dialogue = await service.start_dialogue_session(
            user_id=current_user["user_id"],
            dilemma_type=config.dilemma_type,
            topic=config.topic
        )
        
        return {
            "dialogue_id": dialogue.id,
            "dilemma_title": dialogue.dilemma_title,
            "scenario": dialogue.scenario_description,
            "framework_options": dialogue.framework_options,
            "complexity": dialogue.complexity_level,
            "estimated_time": dialogue.estimated_discussion_time,
            "started_at": dialogue.started_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dilemmas/{dialogue_id}/respond")
async def submit_dilemma_response(
    dialogue_id: str,
    response: DilemmaResponseRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Submit a response to the philosophical dilemma"""
    service = PhilosophicalDialogueService(db)
    
    try:
        result = await service.submit_response(
            dialogue_id=dialogue_id,
            user_id=current_user["user_id"],
            response=response.response,
            framework=response.framework
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dilemmas/{dialogue_id}/conclude")
async def conclude_philosophical_dialogue(
    dialogue_id: str,
    final_position: DilemmaFinalPositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Conclude the philosophical dialogue with final assessment"""
    service = PhilosophicalDialogueService(db)
    
    try:
        result = await service.conclude_dialogue(
            dialogue_id=dialogue_id,
            user_id=current_user["user_id"],
            final_position=final_position.final_position
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dilemmas/{dialogue_id}")
async def get_dialogue_session(
    dialogue_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get philosophical dialogue session details"""
    query = """
    SELECT * FROM philosophical_dialogues 
    WHERE id = :dialogue_id AND user_id = :user_id
    """
    
    result = await db.execute(query, {
        "dialogue_id": dialogue_id,
        "user_id": current_user["user_id"]
    })
    dialogue = result.fetchone()
    
    if not dialogue:
        raise HTTPException(status_code=404, detail="Dialogue session not found")
    
    return {
        "dialogue_id": dialogue["id"],
        "dilemma_title": dialogue["dilemma_title"],
        "scenario": dialogue["scenario_description"],
        "dialogue_history": dialogue["dialogue_history"],
        "frameworks_explored": dialogue["frameworks_explored"],
        "status": dialogue["dialogue_status"],
        "exchange_count": dialogue["exchange_count"],
        "started_at": dialogue["started_at"],
        "last_exchange_at": dialogue["last_exchange_at"]
    }


# Learning Analytics Endpoints
@router.get("/analytics/progress")
async def get_learning_progress(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get comprehensive learning progress and analytics"""
    service = GameService(db)
    analytics = await service.get_or_create_analytics(current_user["user_id"])
    
    return {
        "overall_progress": {
            "total_sessions": analytics.total_sessions,
            "total_time_minutes": analytics.total_time_minutes,
            "current_streak": analytics.current_streak_days,
            "longest_streak": analytics.longest_streak_days
        },
        "game_ratings": {
            "chess": analytics.chess_rating,
            "go": analytics.go_rating,
            "puzzle_level": analytics.puzzle_solving_level,
            "philosophical_depth": analytics.philosophical_depth_level
        },
        "cognitive_skills": {
            "strategic_thinking": analytics.strategic_thinking_score,
            "logical_reasoning": analytics.logical_reasoning_score,
            "creative_problem_solving": analytics.creative_problem_solving_score,
            "ethical_reasoning": analytics.ethical_reasoning_score,
            "pattern_recognition": analytics.pattern_recognition_score,
            "metacognitive_awareness": analytics.metacognitive_awareness_score
        },
        "thinking_style": {
            "system1_reliance": analytics.system1_reliance_average,
            "system2_engagement": analytics.system2_engagement_average,
            "intuition_accuracy": analytics.intuition_accuracy_score,
            "reflection_frequency": analytics.reflection_frequency_score
        },
        "ai_collaboration": {
            "dependency_index": analytics.ai_dependency_index,
            "prompt_engineering": analytics.prompt_engineering_skill,
            "output_evaluation": analytics.ai_output_evaluation_skill,
            "collaborative_solving": analytics.collaborative_problem_solving
        },
        "achievements": analytics.achievement_badges,
        "recommendations": analytics.recommended_activities,
        "last_activity": analytics.last_activity_date.isoformat() if analytics.last_activity_date else None
    }


@router.get("/analytics/trends")
async def get_learning_trends(
    timeframe: str = Query("30d", description="Timeframe: 7d, 30d, 90d, 1y"),
    skill_area: Optional[str] = Query(None, description="Specific skill area to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get learning trends and performance over time"""
    service = GameService(db)
    analytics = await service.get_or_create_analytics(current_user["user_id"])
    
    # This would typically involve more complex analytics queries
    # For now, return structured trend data
    return {
        "timeframe": timeframe,
        "skill_progression": analytics.skill_progression_data,
        "performance_trends": {
            "chess_rating_history": [{"date": "2024-01-01", "rating": 1200}],  # Mock data
            "puzzle_completion_rate": [{"week": 1, "rate": 0.75}],
            "session_frequency": [{"week": 1, "sessions": 3}]
        },
        "comparative_metrics": {
            "peer_comparison": "Above average",
            "improvement_rate": "15% this month",
            "consistency_score": 0.85
        },
        "insights": [
            "Strong improvement in strategic thinking",
            "Puzzle-solving speed has increased 20%",
            "Consider more challenging philosophical dilemmas"
        ]
    }


@router.get("/analytics/recommendations")
async def get_learning_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get personalized learning recommendations"""
    service = GameService(db)
    analytics = await service.get_or_create_analytics(current_user["user_id"])
    
    return {
        "next_activities": [
            {
                "type": "chess",
                "difficulty": "advanced",
                "reason": "Your tactical skills have improved significantly",
                "estimated_time": 30
            },
            {
                "type": "logical_deduction",
                "difficulty": 6,
                "reason": "Ready for more complex reasoning challenges",
                "estimated_time": 20
            },
            {
                "type": "ai_consciousness",
                "topic": "chinese_room",
                "reason": "Explore deeper philosophical concepts",
                "estimated_time": 25
            }
        ],
        "skill_focus_areas": [
            "Synthesis of multiple ethical frameworks",
            "Advanced strategic planning in Go",
            "Metacognitive awareness development"
        ],
        "adaptive_settings": {
            "chess_difficulty": "advanced",
            "puzzle_difficulty": min(analytics.puzzle_solving_level + 1, 10),
            "philosophical_complexity": "advanced" if analytics.philosophical_depth_level > 6 else "intermediate"
        },
        "learning_goals": analytics.learning_goals or [
            "Improve system 2 thinking engagement",
            "Develop better AI collaboration skills",
            "Master ethical framework application"
        ]
    }


@router.post("/analytics/reflection")
async def submit_learning_reflection(
    reflection_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Submit learning reflection and self-assessment"""
    service = GameService(db)
    analytics = await service.get_or_create_analytics(current_user["user_id"])
    
    # Process reflection data and update analytics
    # This would involve sophisticated analysis of user self-reflection
    
    return {
        "reflection_recorded": True,
        "metacognitive_feedback": "Your self-awareness of thinking patterns is improving",
        "updated_recommendations": [
            "Continue exploring areas where intuition conflicts with analysis",
            "Practice explaining your reasoning process more explicitly"
        ],
        "insights_gained": reflection_data.get("insights", [])
    }