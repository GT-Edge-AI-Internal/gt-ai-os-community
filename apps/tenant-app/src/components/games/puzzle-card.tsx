'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Brain,
  Clock,
  Target,
  Lightbulb,
  Play,
  TrendingUp,
  Puzzle,
  Zap,
  Star,
  BarChart3
} from 'lucide-react';

interface PuzzleCardProps {
  puzzle: {
    type: string;
    name: string;
    description: string;
    difficulty_range: [number, number];
    skills_developed: string[];
  };
  userProgress?: {
    completed_puzzles: number;
    average_time: number;
    success_rate: number;
    current_level: number;
  };
  onStart: (puzzleType: string, difficulty: number) => void;
  onViewProgress: (puzzleType: string) => void;
}

export function PuzzleCard({ puzzle, userProgress, onStart, onViewProgress }: PuzzleCardProps) {
  const [selectedDifficulty, setSelectedDifficulty] = useState(
    userProgress?.current_level || Math.floor((puzzle.difficulty_range[0] + puzzle.difficulty_range[1]) / 2)
  );

  const getPuzzleIcon = (puzzleType: string) => {
    switch (puzzleType) {
      case 'lateral_thinking':
        return <Lightbulb className="w-6 h-6" />;
      case 'logical_deduction':
        return <Target className="w-6 h-6" />;
      case 'mathematical_reasoning':
        return <BarChart3 className="w-6 h-6" />;
      case 'spatial_reasoning':
        return <Puzzle className="w-6 h-6" />;
      default:
        return <Brain className="w-6 h-6" />;
    }
  };

  const getDifficultyColor = (difficulty: number) => {
    if (difficulty <= 3) return 'bg-green-100 text-green-700 border-green-200';
    if (difficulty <= 6) return 'bg-blue-100 text-blue-700 border-blue-200';
    if (difficulty <= 8) return 'bg-orange-100 text-orange-700 border-orange-200';
    return 'bg-red-100 text-red-700 border-red-200';
  };

  const getDifficultyLabel = (difficulty: number) => {
    if (difficulty <= 3) return 'Easy';
    if (difficulty <= 6) return 'Medium';
    if (difficulty <= 8) return 'Hard';
    return 'Expert';
  };

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 80) return 'text-green-600';
    if (rate >= 60) return 'text-blue-600';
    if (rate >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <Card className="hover:shadow-lg transition-shadow duration-200 border-2 hover:border-purple-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600">
              {getPuzzleIcon(puzzle.type)}
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">{puzzle.name}</CardTitle>
              <p className="text-sm text-gray-600 mt-1">{puzzle.description}</p>
            </div>
          </div>
          <Badge variant="secondary" className="bg-purple-100 text-purple-700 border-purple-200">
            PUZZLE
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* User Progress Stats */}
        {userProgress && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-blue-50 rounded">
              <div className="text-sm font-semibold text-blue-700">{userProgress.completed_puzzles}</div>
              <div className="text-xs text-blue-600">Solved</div>
            </div>
            <div className="p-2 bg-green-50 rounded">
              <div className="text-sm font-semibold text-green-700">{Math.round(userProgress.average_time)}m</div>
              <div className="text-xs text-green-600">Avg Time</div>
            </div>
            <div className="p-2 bg-purple-50 rounded">
              <div className={cn("text-sm font-semibold", getSuccessRateColor(userProgress.success_rate))}>
                {userProgress.success_rate}%
              </div>
              <div className="text-xs text-purple-600">Success</div>
            </div>
          </div>
        )}

        {/* Current Level */}
        {userProgress && (
          <div className="flex items-center justify-between p-3 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg">
            <div className="flex items-center space-x-2">
              <Star className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-medium">Current Level</span>
            </div>
            <span className="text-lg font-bold text-purple-700">
              Level {userProgress.current_level}
            </span>
          </div>
        )}

        {/* Difficulty Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Choose Difficulty (1-{puzzle.difficulty_range[1]})
          </label>
          <div className="space-y-2">
            {/* Slider */}
            <input
              type="range"
              min={puzzle.difficulty_range[0]}
              max={puzzle.difficulty_range[1]}
              value={selectedDifficulty}
              onChange={(e) => setSelectedDifficulty(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            
            {/* Selected Difficulty Display */}
            <div className="flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <Badge className={cn("text-xs", getDifficultyColor(selectedDifficulty))}>
                  Level {selectedDifficulty}
                </Badge>
                <span className="text-sm text-gray-600">({getDifficultyLabel(selectedDifficulty)})</span>
              </div>
              {userProgress && selectedDifficulty > userProgress.current_level && (
                <Badge variant="secondary" className="text-xs text-orange-600 border-orange-200">
                  Challenge Mode
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Skills Developed */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Skills Developed
          </label>
          <div className="flex flex-wrap gap-1">
            {puzzle.skills_developed.map((skill) => (
              <Badge key={skill} className="text-xs bg-purple-100 text-purple-700 hover:bg-purple-200">
                <Brain className="w-3 h-3 mr-1" />
                {skill.replace('_', ' ')}
              </Badge>
            ))}
          </div>
        </div>

        {/* Features */}
        <div className="space-y-2">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Lightbulb className="w-4 h-4" />
            <span>AI collaboration and hint system</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Zap className="w-4 h-4" />
            <span>Adaptive difficulty based on performance</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <TrendingUp className="w-4 h-4" />
            <span>Real-time cognitive skill assessment</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-2 pt-2">
          <Button
            onClick={() => onStart(puzzle.type, selectedDifficulty)}
            className="flex-1 bg-purple-600 hover:bg-purple-700"
          >
            <Play className="w-4 h-4 mr-2" />
            Start Puzzle
          </Button>
          <Button
            variant="secondary"
            onClick={() => onViewProgress(puzzle.type)}
            className="px-3 border-purple-200 text-purple-700 hover:bg-purple-50"
          >
            <BarChart3 className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}