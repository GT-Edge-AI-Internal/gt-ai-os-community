'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Brain,
  MessageCircle,
  Clock,
  Users,
  Play,
  BookOpen,
  Compass,
  Lightbulb,
  Target,
  BarChart3,
  Scale
} from 'lucide-react';

interface DilemmaCardProps {
  dilemma: {
    type: string;
    name: string;
    description: string;
    topics: string[];
    skills_developed: string[];
  };
  userProgress?: {
    discussions_completed: number;
    frameworks_explored: number;
    average_depth_score: number;
    favorite_topics: string[];
  };
  onStart: (dilemmaType: string, topic: string) => void;
  onViewProgress: (dilemmaType: string) => void;
}

export function DilemmaCard({ dilemma, userProgress, onStart, onViewProgress }: DilemmaCardProps) {
  const [selectedTopic, setSelectedTopic] = useState(dilemma.topics[0]);

  const getDilemmaIcon = (dilemmaType: string) => {
    switch (dilemmaType) {
      case 'ethical_frameworks':
        return <Scale className="w-6 h-6" />;
      case 'game_theory':
        return <Target className="w-6 h-6" />;
      case 'ai_consciousness':
        return <Brain className="w-6 h-6" />;
      default:
        return <MessageCircle className="w-6 h-6" />;
    }
  };

  const getTopicDescription = (topic: string) => {
    const descriptions: Record<string, string> = {
      'trolley_problem': 'Classic ethical dilemma about sacrificing one to save many',
      'utilitarian_vs_deontological': 'Comparing outcome-based vs duty-based ethics',
      'virtue_ethics_scenarios': 'Character-based moral reasoning situations',
      'prisoners_dilemma': 'Strategic cooperation vs defection scenarios',
      'tragedy_of_commons': 'Individual vs collective resource management',
      'coordination_games': 'Mutual benefit through coordinated action',
      'chinese_room': 'The nature of understanding and consciousness in AI',
      'turing_test_ethics': 'Moral implications of AI consciousness tests',
      'ai_rights': 'Should AI systems have rights and protections?',
      'consciousness_criteria': 'What defines consciousness and sentience?'
    };
    return descriptions[topic] || 'Explore complex philosophical questions';
  };

  const getComplexityColor = (type: string) => {
    switch (type) {
      case 'ethical_frameworks':
        return 'text-blue-600';
      case 'game_theory':
        return 'text-green-600';
      case 'ai_consciousness':
        return 'text-purple-600';
      default:
        return 'text-gray-600';
    }
  };

  const getDepthScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-blue-600';
    if (score >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <Card className="hover:shadow-lg transition-shadow duration-200 border-2 hover:border-blue-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className={cn(
              "w-12 h-12 rounded-lg flex items-center justify-center",
              dilemma.type === 'ethical_frameworks' && "bg-blue-100 text-blue-600",
              dilemma.type === 'game_theory' && "bg-green-100 text-green-600",
              dilemma.type === 'ai_consciousness' && "bg-purple-100 text-purple-600"
            )}>
              {getDilemmaIcon(dilemma.type)}
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">{dilemma.name}</CardTitle>
              <p className="text-sm text-gray-600 mt-1">{dilemma.description}</p>
            </div>
          </div>
          <Badge variant="secondary" className={cn(
            "text-xs",
            dilemma.type === 'ethical_frameworks' && "bg-blue-100 text-blue-700 border-blue-200",
            dilemma.type === 'game_theory' && "bg-green-100 text-green-700 border-green-200",
            dilemma.type === 'ai_consciousness' && "bg-purple-100 text-purple-700 border-purple-200"
          )}>
            DIALOGUE
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* User Progress Stats */}
        {userProgress && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-blue-50 rounded">
              <div className="text-sm font-semibold text-blue-700">{userProgress.discussions_completed}</div>
              <div className="text-xs text-blue-600">Discussions</div>
            </div>
            <div className="p-2 bg-green-50 rounded">
              <div className="text-sm font-semibold text-green-700">{userProgress.frameworks_explored}</div>
              <div className="text-xs text-green-600">Frameworks</div>
            </div>
            <div className="p-2 bg-purple-50 rounded">
              <div className={cn("text-sm font-semibold", getDepthScoreColor(userProgress.average_depth_score))}>
                {userProgress.average_depth_score}/100
              </div>
              <div className="text-xs text-purple-600">Depth Score</div>
            </div>
          </div>
        )}

        {/* Topic Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Choose Discussion Topic
          </label>
          <div className="space-y-2">
            {dilemma.topics.map((topic) => (
              <div key={topic} className="space-y-1">
                <button
                  onClick={() => setSelectedTopic(topic)}
                  className={cn(
                    "w-full p-3 rounded-lg border text-left transition-colors",
                    selectedTopic === topic
                      ? "border-blue-300 bg-blue-50"
                      : "border-gray-200 hover:bg-gray-50"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">
                      {topic.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    {userProgress?.favorite_topics.includes(topic) && (
                      <Badge variant="secondary" className="text-xs">Favorite</Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 mt-1">
                    {getTopicDescription(topic)}
                  </p>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Skills Developed */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Skills Developed
          </label>
          <div className="flex flex-wrap gap-1">
            {dilemma.skills_developed.map((skill) => (
              <Badge key={skill} className={cn(
                "text-xs",
                dilemma.type === 'ethical_frameworks' && "bg-blue-100 text-blue-700 hover:bg-blue-200",
                dilemma.type === 'game_theory' && "bg-green-100 text-green-700 hover:bg-green-200",
                dilemma.type === 'ai_consciousness' && "bg-purple-100 text-purple-700 hover:bg-purple-200"
              )}>
                <Brain className="w-3 h-3 mr-1" />
                {skill.replace('_', ' ')}
              </Badge>
            ))}
          </div>
        </div>

        {/* Features */}
        <div className="space-y-2">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <MessageCircle className="w-4 h-4" />
            <span>Socratic dialogue with AI facilitator</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <BookOpen className="w-4 h-4" />
            <span>Multiple ethical frameworks exploration</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Compass className="w-4 h-4" />
            <span>Perspective-taking and synthesis practice</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Clock className="w-4 h-4" />
            <span>Estimated time: 20-30 minutes</span>
          </div>
        </div>

        {/* Complexity Indicator */}
        <div className={cn(
          "flex items-center justify-between p-3 rounded-lg",
          dilemma.type === 'ethical_frameworks' && "bg-blue-50",
          dilemma.type === 'game_theory' && "bg-green-50",
          dilemma.type === 'ai_consciousness' && "bg-purple-50"
        )}>
          <div className="flex items-center space-x-2">
            <Lightbulb className="w-4 h-4 text-gray-600" />
            <span className="text-sm font-medium">Complexity Level</span>
          </div>
          <span className={cn("text-sm font-semibold", getComplexityColor(dilemma.type))}>
            {dilemma.type === 'ai_consciousness' ? 'Advanced' : 
             dilemma.type === 'game_theory' ? 'Intermediate' : 'Beginner-Friendly'}
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-2 pt-2">
          <Button
            onClick={() => onStart(dilemma.type, selectedTopic)}
            className={cn(
              "flex-1",
              dilemma.type === 'ethical_frameworks' && "bg-blue-600 hover:bg-blue-700",
              dilemma.type === 'game_theory' && "bg-green-600 hover:bg-green-700",
              dilemma.type === 'ai_consciousness' && "bg-purple-600 hover:bg-purple-700"
            )}
          >
            <Play className="w-4 h-4 mr-2" />
            Start Dialogue
          </Button>
          <Button
            variant="secondary"
            onClick={() => onViewProgress(dilemma.type)}
            className={cn(
              "px-3",
              dilemma.type === 'ethical_frameworks' && "border-blue-200 text-blue-700 hover:bg-blue-50",
              dilemma.type === 'game_theory' && "border-green-200 text-green-700 hover:bg-green-50",
              dilemma.type === 'ai_consciousness' && "border-purple-200 text-purple-700 hover:bg-purple-50"
            )}
          >
            <BarChart3 className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}