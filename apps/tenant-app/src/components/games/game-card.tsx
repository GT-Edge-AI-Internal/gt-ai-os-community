'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  ChevronRight,
  Trophy,
  Clock,
  Target,
  TrendingUp,
  Brain,
  Gamepad2,
  Star,
  Play,
  BarChart3
} from 'lucide-react';

interface GameCardProps {
  game: {
    type: string;
    name: string;
    description: string;
    current_rating: number;
    difficulty_levels: string[];
    features: string[];
    estimated_time: string;
    skills_developed: string[];
  };
  userProgress?: {
    sessions_played: number;
    best_rating: number;
    recent_performance: number;
  };
  onStart: (gameType: string, difficulty: string) => void;
  onViewProgress: (gameType: string) => void;
}

export function GameCard({ game, userProgress, onStart, onViewProgress }: GameCardProps) {
  const [selectedDifficulty, setSelectedDifficulty] = useState('intermediate');

  const getGameIcon = (gameType: string) => {
    switch (gameType) {
      case 'chess':
        return '♛';
      case 'go':
        return '●';
      default:
        return <Gamepad2 className="w-6 h-6" />;
    }
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'intermediate':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'advanced':
        return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'expert':
        return 'bg-red-100 text-red-700 border-red-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getRatingColor = (rating: number) => {
    if (rating >= 1800) return 'text-purple-600';
    if (rating >= 1600) return 'text-blue-600';
    if (rating >= 1400) return 'text-green-600';
    if (rating >= 1200) return 'text-yellow-600';
    return 'text-gray-600';
  };

  return (
    <Card className="hover:shadow-lg transition-shadow duration-200 border-2 hover:border-gt-green/20">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-gt-green/10 rounded-lg flex items-center justify-center text-2xl">
              {typeof getGameIcon(game.type) === 'string' ? getGameIcon(game.type) : getGameIcon(game.type)}
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">{game.name}</CardTitle>
              <p className="text-sm text-gray-600 mt-1">{game.description}</p>
            </div>
          </div>
          <Badge variant="secondary" className="bg-gt-green/10 text-gt-green border-gt-green/20">
            {game.type.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Current Rating & Progress */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-2">
            <Trophy className="w-4 h-4 text-yellow-600" />
            <span className="text-sm font-medium">Current Rating</span>
          </div>
          <span className={cn("text-lg font-bold", getRatingColor(game.current_rating))}>
            {game.current_rating}
          </span>
        </div>

        {/* User Progress Stats */}
        {userProgress && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-blue-50 rounded">
              <div className="text-sm font-semibold text-blue-700">{userProgress.sessions_played}</div>
              <div className="text-xs text-blue-600">Sessions</div>
            </div>
            <div className="p-2 bg-green-50 rounded">
              <div className="text-sm font-semibold text-green-700">{userProgress.best_rating}</div>
              <div className="text-xs text-green-600">Best Rating</div>
            </div>
            <div className="p-2 bg-purple-50 rounded">
              <div className="text-sm font-semibold text-purple-700">{userProgress.recent_performance}%</div>
              <div className="text-xs text-purple-600">Win Rate</div>
            </div>
          </div>
        )}

        {/* Difficulty Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Choose Difficulty
          </label>
          <div className="grid grid-cols-2 gap-2">
            {game.difficulty_levels.map((difficulty) => (
              <button
                key={difficulty}
                onClick={() => setSelectedDifficulty(difficulty)}
                className={cn(
                  "px-3 py-2 rounded-lg text-sm font-medium border transition-colors",
                  selectedDifficulty === difficulty
                    ? getDifficultyColor(difficulty)
                    : "bg-gt-white border-gray-200 text-gray-700 hover:bg-gray-50"
                )}
              >
                {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Game Features */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Features
          </label>
          <div className="flex flex-wrap gap-1">
            {game.features.slice(0, 3).map((feature) => (
              <Badge key={feature} variant="secondary" className="text-xs">
                {feature.replace('_', ' ')}
              </Badge>
            ))}
            {game.features.length > 3 && (
              <Badge variant="secondary" className="text-xs">
                +{game.features.length - 3} more
              </Badge>
            )}
          </div>
        </div>

        {/* Skills Developed */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Skills Developed
          </label>
          <div className="flex flex-wrap gap-1">
            {game.skills_developed.map((skill) => (
              <Badge key={skill} className="text-xs bg-gt-green/10 text-gt-green hover:bg-gt-green/20">
                <Brain className="w-3 h-3 mr-1" />
                {skill.replace('_', ' ')}
              </Badge>
            ))}
          </div>
        </div>

        {/* Time Estimate */}
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <Clock className="w-4 h-4" />
          <span>Estimated time: {game.estimated_time}</span>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-2 pt-2">
          <Button
            onClick={() => onStart(game.type, selectedDifficulty)}
            className="flex-1 bg-gt-green hover:bg-gt-green/90"
          >
            <Play className="w-4 h-4 mr-2" />
            Start Game
          </Button>
          <Button
            variant="secondary"
            onClick={() => onViewProgress(game.type)}
            className="px-3"
          >
            <BarChart3 className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}