'use client';

import { TestLayout } from '@/components/layout/test-layout';
import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Trophy, Brain, Puzzle, Users, ChevronRight, Star, Target, TrendingUp } from 'lucide-react';
import { mockApi } from '@/lib/mock-api';

export default function TestGamesPage() {
  const [games, setGames] = useState<any[]>([]);
  const [progress, setProgress] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadGamesAndProgress();
  }, []);

  const loadGamesAndProgress = async () => {
    try {
      const [gamesData, progressData] = await Promise.all([
        mockApi.games.list(),
        mockApi.games.getProgress()
      ]);
      setGames(gamesData.games);
      setProgress(progressData);
    } catch (error) {
      console.error('Failed to load games:', error);
    } finally {
      setLoading(false);
    }
  };

  const getGameIcon = (type: string) => {
    switch (type) {
      case 'chess': return '♟️';
      case 'logic_puzzle': return '🧩';
      case 'philosophical_dilemma': return '🤔';
      default: return '🎮';
    }
  };

  const getDifficultyColor = (level: string) => {
    switch (level) {
      case 'beginner':
      case 'easy': return 'bg-green-100 text-green-700';
      case 'intermediate':
      case 'medium': return 'bg-yellow-100 text-yellow-700';
      case 'expert':
      case 'hard': return 'bg-red-100 text-red-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  if (loading) {
    return (
      <TestLayout>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
        </div>
      </TestLayout>
    );
  }

  return (
    <TestLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">AI Literacy & Cognitive Development</h1>
          <p className="text-gray-600 mt-1">Develop critical thinking skills through games and challenges</p>
        </div>

        {/* Progress Overview */}
        {progress && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Card className="p-4">
              <div className="flex items-center justify-between mb-2">
                <Trophy className="w-5 h-5 text-yellow-500" />
                <span className="text-2xl font-bold">{progress.overall_progress.level}</span>
              </div>
              <p className="text-sm text-gray-600">Current Level</p>
              <Progress value={(progress.overall_progress.experience / progress.overall_progress.next_level_xp) * 100} className="mt-2 h-1" />
              <p className="text-xs text-gray-500 mt-1">
                {progress.overall_progress.experience} / {progress.overall_progress.next_level_xp} XP
              </p>
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between mb-2">
                <Brain className="w-5 h-5 text-purple-500" />
                <span className="text-2xl font-bold">{progress.skill_metrics.strategic_thinking}%</span>
              </div>
              <p className="text-sm text-gray-600">Strategic Thinking</p>
              <Progress value={progress.skill_metrics.strategic_thinking} className="mt-2 h-1" />
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between mb-2">
                <Target className="w-5 h-5 text-blue-500" />
                <span className="text-2xl font-bold">{progress.skill_metrics.logical_reasoning}%</span>
              </div>
              <p className="text-sm text-gray-600">Logical Reasoning</p>
              <Progress value={progress.skill_metrics.logical_reasoning} className="mt-2 h-1" />
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between mb-2">
                <TrendingUp className="w-5 h-5 text-green-500" />
                <span className="text-2xl font-bold">{progress.learning_streak}</span>
              </div>
              <p className="text-sm text-gray-600">Day Streak</p>
              <div className="flex mt-2">
                {[...Array(7)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-4 h-4 rounded-sm mr-1 ${
                      i < progress.learning_streak ? 'bg-green-500' : 'bg-gray-200'
                    }`}
                  />
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* Skills Overview */}
        {progress && (
          <Card className="p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Skill Development</h2>
            <div className="space-y-3">
              {Object.entries(progress.skill_metrics).map(([skill, value]: [string, any]) => (
                <div key={skill}>
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">
                      {skill.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </span>
                    <span className="text-sm text-gray-500">{value}%</span>
                  </div>
                  <Progress value={value} className="h-2" />
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Games Grid */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-4">Available Games & Challenges</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {games.map((game) => (
              <Card key={game.id} className="p-6 hover:shadow-lg transition-shadow cursor-pointer">
                <div className="flex items-start justify-between mb-4">
                  <div className="text-4xl">{getGameIcon(game.type)}</div>
                  {game.user_rating && (
                    <Badge variant="secondary" className="flex items-center">
                      <Star className="w-3 h-3 mr-1 fill-yellow-500 text-yellow-500" />
                      {game.user_rating}
                    </Badge>
                  )}
                </div>
                
                <h3 className="font-semibold text-gray-900 mb-2">{game.name}</h3>
                <p className="text-sm text-gray-600 mb-4">{game.description}</p>
                
                {/* Difficulty Levels */}
                {game.difficulty_levels && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {game.difficulty_levels.map((level: string) => (
                      <Badge key={level} className={getDifficultyColor(level)}>
                        {level}
                      </Badge>
                    ))}
                  </div>
                )}
                
                {/* Stats */}
                <div className="space-y-2 mb-4">
                  {game.games_played !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Games Played:</span>
                      <span className="font-medium">{game.games_played}</span>
                    </div>
                  )}
                  {game.win_rate !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Win Rate:</span>
                      <span className="font-medium">{(game.win_rate * 100).toFixed(0)}%</span>
                    </div>
                  )}
                  {game.puzzles_solved !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Puzzles Solved:</span>
                      <span className="font-medium">{game.puzzles_solved}</span>
                    </div>
                  )}
                  {game.scenarios_completed !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Scenarios:</span>
                      <span className="font-medium">{game.scenarios_completed}</span>
                    </div>
                  )}
                </div>
                
                <Button className="w-full bg-green-600 hover:bg-green-700 text-white">
                  Play Now
                  <ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              </Card>
            ))}
          </div>
        </div>

        {/* Recommendations */}
        {progress?.recommendations && progress.recommendations.length > 0 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold mb-4">Personalized Recommendations</h2>
            <div className="space-y-3">
              {progress.recommendations.map((rec: string, idx: number) => (
                <div key={idx} className="flex items-start">
                  <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5 mr-3 flex-shrink-0" />
                  <p className="text-sm text-gray-700">{rec}</p>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </TestLayout>
  );
}