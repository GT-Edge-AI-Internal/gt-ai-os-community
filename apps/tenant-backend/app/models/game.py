"""
Game Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for game entities using the PostgreSQL + PGVector backend.
Game sessions for AI literacy and strategic thinking development.
Perfect tenant isolation - each tenant has separate game data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel


def generate_uuid():
    """Generate a unique identifier"""
    return str(uuid.uuid4())


class GameType(str, Enum):
    """Game type enumeration"""
    CHESS = "chess"
    GO = "go"
    LOGIC_PUZZLE = "logic_puzzle"
    PHILOSOPHICAL_DILEMMA = "philosophical_dilemma"
    TRIVIA = "trivia"
    DEBATE = "debate"


class DifficultyLevel(str, Enum):
    """Difficulty level enumeration"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class GameStatus(str, Enum):
    """Game status enumeration"""
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class GameSession(BaseServiceModel):
    """
    Game session model for GT 2.0 service-based architecture.
    
    Represents AI literacy and strategic thinking game sessions
    with progress tracking and skill development.
    """
    
    # Core game properties
    user_id: str = Field(..., description="User playing the game")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    game_type: GameType = Field(..., description="Type of game")
    game_name: str = Field(..., min_length=1, max_length=100, description="Game name")
    
    # Game configuration
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE, description="Difficulty level")
    ai_opponent_config: Dict[str, Any] = Field(default_factory=dict, description="AI opponent settings")
    game_rules: Dict[str, Any] = Field(default_factory=dict, description="Game-specific rules")
    
    # Game state
    current_state: Dict[str, Any] = Field(default_factory=dict, description="Current game state")
    move_history: List[Dict[str, Any]] = Field(default_factory=list, description="History of moves")
    game_status: GameStatus = Field(default=GameStatus.ACTIVE, description="Game status")
    
    # Progress tracking
    moves_count: int = Field(default=0, description="Number of moves made")
    hints_used: int = Field(default=0, description="Number of hints used")
    time_spent_seconds: int = Field(default=0, description="Time spent in seconds")
    current_rating: int = Field(default=1200, description="ELO-style rating")
    
    # Results
    winner: Optional[str] = Field(None, description="Winner of the game")
    final_score: Optional[Dict[str, Any]] = Field(None, description="Final score details")
    learning_insights: List[str] = Field(default_factory=list, description="Learning insights")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "game_sessions"
    
    def add_move(self, move_data: Dict[str, Any]) -> None:
        """Add a move to the game history"""
        self.move_history.append(move_data)
        self.moves_count += 1
        self.update_timestamp()
    
    def use_hint(self) -> None:
        """Record hint usage"""
        self.hints_used += 1
        self.update_timestamp()
    
    def complete_game(self, winner: str, final_score: Dict[str, Any]) -> None:
        """Mark game as completed"""
        self.game_status = GameStatus.COMPLETED
        self.winner = winner
        self.final_score = final_score
        self.update_timestamp()
    
    def pause_game(self) -> None:
        """Pause the game"""
        self.game_status = GameStatus.PAUSED
        self.update_timestamp()
    
    def resume_game(self) -> None:
        """Resume the game"""
        self.game_status = GameStatus.ACTIVE
        self.update_timestamp()


class PuzzleSession(BaseServiceModel):
    """
    Puzzle session model for logic and problem-solving games.
    
    Tracks puzzle-specific metrics and progress.
    """
    
    # Core puzzle properties
    user_id: str = Field(..., description="User solving the puzzle")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    puzzle_type: str = Field(..., max_length=50, description="Type of puzzle")
    puzzle_name: str = Field(..., min_length=1, max_length=100, description="Puzzle name")
    
    # Puzzle configuration
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE, description="Difficulty level")
    puzzle_data: Dict[str, Any] = Field(default_factory=dict, description="Puzzle configuration")
    solution_data: Dict[str, Any] = Field(default_factory=dict, description="Solution information")
    
    # Progress tracking
    attempts_made: int = Field(default=0, description="Number of attempts")
    hints_requested: int = Field(default=0, description="Hints requested")
    is_solved: bool = Field(default=False, description="Whether puzzle is solved")
    solve_time_seconds: Optional[int] = Field(None, description="Time to solve")
    
    # Learning metrics
    skill_points_earned: int = Field(default=0, description="Skill points earned")
    concepts_learned: List[str] = Field(default_factory=list, description="Concepts learned")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "puzzle_sessions"
    
    def add_attempt(self) -> None:
        """Record a puzzle attempt"""
        self.attempts_made += 1
        self.update_timestamp()
    
    def solve_puzzle(self, solve_time: int, skill_points: int) -> None:
        """Mark puzzle as solved"""
        self.is_solved = True
        self.solve_time_seconds = solve_time
        self.skill_points_earned = skill_points
        self.update_timestamp()


class PhilosophicalDialogue(BaseServiceModel):
    """
    Philosophical dialogue model for ethical and critical thinking development.
    
    Tracks philosophical discussions and thinking development.
    """
    
    # Core dialogue properties
    user_id: str = Field(..., description="User participating in dialogue")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    dialogue_topic: str = Field(..., min_length=1, max_length=200, description="Dialogue topic")
    dialogue_type: str = Field(..., max_length=50, description="Type of philosophical dialogue")
    
    # Dialogue configuration
    ai_persona: str = Field(default="socratic", max_length=50, description="AI dialogue persona")
    dialogue_style: str = Field(default="questioning", max_length=50, description="Dialogue style")
    target_concepts: List[str] = Field(default_factory=list, description="Target concepts to explore")
    
    # Dialogue content
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Dialogue messages")
    key_insights: List[str] = Field(default_factory=list, description="Key insights generated")
    
    # Progress metrics
    turns_count: int = Field(default=0, description="Number of dialogue turns")
    depth_score: float = Field(default=0.0, description="Depth of philosophical exploration")
    critical_thinking_score: float = Field(default=0.0, description="Critical thinking score")
    
    # Status
    is_completed: bool = Field(default=False, description="Whether dialogue is completed")
    completion_reason: Optional[str] = Field(None, description="Reason for completion")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "philosophical_dialogues"
    
    def add_message(self, message_data: Dict[str, Any]) -> None:
        """Add a message to the dialogue"""
        self.messages.append(message_data)
        self.turns_count += 1
        self.update_timestamp()
    
    def complete_dialogue(self, reason: str) -> None:
        """Mark dialogue as completed"""
        self.is_completed = True
        self.completion_reason = reason
        self.update_timestamp()


class LearningAnalytics(BaseServiceModel):
    """
    Learning analytics model for tracking educational progress.
    
    Aggregates learning data across all game types.
    """
    
    # Core analytics properties
    user_id: str = Field(..., description="User being analyzed")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    
    # Skill tracking
    chess_rating: int = Field(default=1200, description="Chess skill rating")
    go_rating: int = Field(default=1200, description="Go skill rating")
    puzzle_solving_level: int = Field(default=1, description="Puzzle solving level")
    critical_thinking_level: int = Field(default=1, description="Critical thinking level")
    
    # Activity metrics
    total_games_played: int = Field(default=0, description="Total games played")
    total_puzzles_solved: int = Field(default=0, description="Total puzzles solved")
    total_dialogues_completed: int = Field(default=0, description="Total dialogues completed")
    total_time_spent_hours: float = Field(default=0.0, description="Total time spent in hours")
    
    # Learning metrics
    concepts_mastered: List[str] = Field(default_factory=list, description="Mastered concepts")
    learning_streaks: Dict[str, int] = Field(default_factory=dict, description="Learning streaks")
    achievement_badges: List[str] = Field(default_factory=list, description="Achievement badges")
    
    # Progress tracking
    last_activity_date: Optional[datetime] = Field(None, description="Last activity date")
    learning_goals: List[Dict[str, Any]] = Field(default_factory=list, description="Learning goals")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "learning_analytics"
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity_date = datetime.utcnow()
        self.update_timestamp()
    
    def earn_badge(self, badge_name: str) -> None:
        """Earn an achievement badge"""
        if badge_name not in self.achievement_badges:
            self.achievement_badges.append(badge_name)
            self.update_timestamp()


class GameTemplate(BaseServiceModel):
    """
    Game template model for configuring game types and rules.
    
    Defines reusable game configurations and templates.
    """
    
    # Core template properties
    template_name: str = Field(..., min_length=1, max_length=100, description="Template name")
    game_type: GameType = Field(..., description="Game type")
    template_description: str = Field(..., max_length=500, description="Template description")
    
    # Template configuration
    default_rules: Dict[str, Any] = Field(default_factory=dict, description="Default game rules")
    ai_configurations: List[Dict[str, Any]] = Field(default_factory=list, description="AI opponent configs")
    difficulty_settings: Dict[str, Any] = Field(default_factory=dict, description="Difficulty settings")
    
    # Educational content
    learning_objectives: List[str] = Field(default_factory=list, description="Learning objectives")
    skill_categories: List[str] = Field(default_factory=list, description="Skill categories")
    educational_notes: Optional[str] = Field(None, description="Educational notes")
    
    # Template metadata
    created_by: str = Field(..., description="Creator of the template")
    tenant_id: str = Field(..., description="Tenant domain identifier")
    is_public: bool = Field(default=False, description="Whether template is publicly available")
    usage_count: int = Field(default=0, description="Number of times used")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "game_templates"
    
    def increment_usage(self) -> None:
        """Increment usage count"""
        self.usage_count += 1
        self.update_timestamp()


# Create/Update/Response models

class GameSessionCreate(BaseCreateModel):
    """Model for creating new game sessions"""
    user_id: str
    tenant_id: str
    game_type: GameType
    game_name: str = Field(..., min_length=1, max_length=100)
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE)
    ai_opponent_config: Dict[str, Any] = Field(default_factory=dict)
    game_rules: Dict[str, Any] = Field(default_factory=dict)


class GameSessionUpdate(BaseUpdateModel):
    """Model for updating game sessions"""
    current_state: Optional[Dict[str, Any]] = None
    game_status: Optional[GameStatus] = None
    time_spent_seconds: Optional[int] = Field(None, ge=0)
    current_rating: Optional[int] = Field(None, ge=0, le=3000)
    winner: Optional[str] = None
    final_score: Optional[Dict[str, Any]] = None


class GameSessionResponse(BaseResponseModel):
    """Model for game session API responses"""
    id: str
    user_id: str
    tenant_id: str
    game_type: GameType
    game_name: str
    difficulty_level: DifficultyLevel
    current_state: Dict[str, Any]
    move_history: List[Dict[str, Any]]
    game_status: GameStatus
    moves_count: int
    hints_used: int
    time_spent_seconds: int
    current_rating: int
    winner: Optional[str]
    final_score: Optional[Dict[str, Any]]
    learning_insights: List[str]
    created_at: datetime
    updated_at: datetime