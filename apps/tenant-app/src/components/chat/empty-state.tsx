'use client';

import { Button } from '@/components/ui/button';
import { 
  MessageSquare, 
  FileText, 
  Lightbulb, 
  Search, 
  PenTool,
  BarChart3,
  Plus
} from 'lucide-react';

interface EmptyStateProps {
  onNewConversation: () => void;
}

export function EmptyState({ onNewConversation }: EmptyStateProps) {
  const capabilities = [
    {
      icon: MessageSquare,
      title: 'Natural Conversations',
      description: 'Ask questions, get explanations, and have detailed discussions on any topic.'
    },
    {
      icon: FileText,
      title: 'Document Analysis',
      description: 'Upload and analyze documents, extract insights, and get summaries.'
    },
    {
      icon: PenTool,
      title: 'Content Creation',
      description: 'Write emails, reports, creative content, and professional documents.'
    },
    {
      icon: Search,
      title: 'Research Agent',
      description: 'Get help with research, fact-checking, and information gathering.'
    },
    {
      icon: BarChart3,
      title: 'Data Analysis',
      description: 'Analyze data, create insights, and generate reports from your information.'
    },
    {
      icon: Lightbulb,
      title: 'Problem Solving',
      description: 'Work through complex problems and get strategic recommendations.'
    }
  ];

  const quickStarters = [
    'Help me analyze this quarterly report...',
    'Write a professional email to...',
    'Explain the key concepts of...',
    'Summarize the main points from...',
    'Create an outline for...',
    'What are the best practices for...'
  ];

  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="max-w-4xl w-full text-center">
        {/* Header */}
        <div className="mb-12">
          <div className="w-20 h-20 bg-gradient-to-br from-gt-green to-gt-green/80 rounded-2xl mx-auto mb-6 flex items-center justify-center shadow-lg">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          
          <h1 className="text-3xl font-bold text-gt-gray-900 mb-4">
            Welcome to GT 2.0
          </h1>
          <p className="text-lg text-gt-gray-600 max-w-2xl mx-auto">
            Your intelligent AI agent for enterprise workflows. Start a conversation to unlock 
            powerful capabilities for analysis, writing, research, and problem-solving.
          </p>
        </div>

        {/* Capabilities Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {capabilities.map((capability, index) => {
            const Icon = capability.icon;
            return (
              <div 
                key={index}
                className="bg-gt-white rounded-xl p-6 border border-gt-gray-200 hover:border-gt-green/30 hover:shadow-md transition-all duration-200"
              >
                <div className="w-12 h-12 bg-gt-green/10 rounded-lg flex items-center justify-center mb-4 mx-auto">
                  <Icon className="w-6 h-6 text-gt-green" />
                </div>
                <h3 className="text-lg font-semibold text-gt-gray-900 mb-2">
                  {capability.title}
                </h3>
                <p className="text-gt-gray-600 text-sm">
                  {capability.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Quick Starters */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gt-gray-900 mb-6">
            Quick Starters
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {quickStarters.map((starter, index) => (
              <button
                key={index}
                onClick={() => {
                  // TODO: Pre-fill the chat input with this starter
                  console.log('Starter selected:', starter);
                }}
                className="text-left p-4 bg-gt-gray-50 hover:bg-gt-gray-100 rounded-lg border border-transparent hover:border-gt-green/30 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-gt-green/10 group-hover:bg-gt-green/20 rounded-lg flex items-center justify-center flex-shrink-0">
                    <MessageSquare className="w-4 h-4 text-gt-green" />
                  </div>
                  <p className="text-sm text-gt-gray-700 group-hover:text-gt-gray-900">
                    {starter}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Call to Action */}
        <div className="bg-gradient-to-r from-gt-green/5 to-gt-green/10 rounded-xl p-8 border border-gt-green/20">
          <h2 className="text-xl font-semibold text-gt-gray-900 mb-4">
            Ready to get started?
          </h2>
          <p className="text-gt-gray-600 mb-6 max-w-md mx-auto">
            Start a new conversation and experience the power of enterprise AI assistance.
          </p>
          <Button
            onClick={onNewConversation}
            variant="primary"
            size="lg"
            className="inline-flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Start New Conversation</span>
          </Button>
        </div>

        {/* Security Notice */}
        <div className="mt-8 pt-6 border-t border-gt-gray-200">
          <div className="flex items-center justify-center space-x-8 text-sm text-gt-gray-500">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span>Enterprise Secure</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span>Perfect Isolation</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
              <span>GT Edge AI Powered</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}