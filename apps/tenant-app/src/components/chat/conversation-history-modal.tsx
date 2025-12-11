'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';
import { 
  Search, 
  MessageCircle, 
  Calendar, 
  Bot, 
  Clock,
  X,
  Filter,
  ChevronDown,
  MoreHorizontal,
  Trash2,
  MessageSquare,
  Edit3,
  Check,
  X as XIcon
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { getAuthToken } from '@/services/auth';

interface Conversation {
  id: string;
  title: string;
  agent_id?: string;
  agent_name?: string;
  message_count: number;
  last_message_at: string;
  created_at: string;
  preview?: string;
}

interface ConversationHistoryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectConversation: (conversationId: string) => void;
}

export function ConversationHistoryModal({ 
  open, 
  onOpenChange, 
  onSelectConversation 
}: ConversationHistoryModalProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [filteredConversations, setFilteredConversations] = useState<Conversation[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'today' | 'week' | 'month'>('all');
  const [selectedAgent, setSelectedAgent] = useState<string>('all');
  const [availableAgents, setAvailableAgents] = useState<{ id: string; name: string }[]>([]);
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');

  // Load conversations from API
  useEffect(() => {
    if (open) {
      loadConversations();
    }
  }, [open]);

  // Filter conversations based on search and filters
  useEffect(() => {
    let filtered = conversations;

    // Search filter
    if (searchQuery) {
      filtered = filtered.filter(conv => 
        conv.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conv.preview?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conv.agent_name?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Agent filter
    if (selectedAgent !== 'all') {
      filtered = filtered.filter(conv => conv.agent_id === selectedAgent);
    }

    // Time filter
    const now = new Date();
    if (filter !== 'all') {
      filtered = filtered.filter(conv => {
        const lastMessage = new Date(conv.last_message_at);
        const diffDays = (now.getTime() - lastMessage.getTime()) / (1000 * 3600 * 24);
        
        switch (filter) {
          case 'today':
            return diffDays < 1;
          case 'week':
            return diffDays < 7;
          case 'month':
            return diffDays < 30;
          default:
            return true;
        }
      });
    }

    // Sort by last message date
    filtered.sort((a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime());

    setFilteredConversations(filtered);
  }, [conversations, searchQuery, filter, selectedAgent]);

  const loadConversations = async () => {
    setIsLoading(true);
    try {
      // Use the existing conversations API
      const token = getAuthToken();
      console.log('🔍 Loading conversations with token:', token ? 'EXISTS' : 'MISSING');

      const response = await fetch('/api/v1/conversations', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      console.log('🔍 Conversations API response:', response.status, response.statusText);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('🔍 Conversations API error:', errorText);
        throw new Error(`Failed to load conversations: ${response.status} ${errorText}`);
      }

      const data = await response.json();
      console.log('🔍 Conversations API data:', data);
      
      // Transform the data to match our interface
      const transformedConversations = data.conversations?.map((conv: any) => ({
        id: conv.id,
        title: conv.title || 'Untitled Conversation',
        agent_id: conv.agent_id,
        agent_name: conv.agent_name || 'AI Assistant',
        message_count: conv.message_count || 0,
        last_message_at: conv.last_message_at || conv.created_at,
        created_at: conv.created_at,
        preview: conv.preview
      })) || [];

      setConversations(transformedConversations);

      // Extract unique agents for filter dropdown
      const agents = transformedConversations
        .filter((conv: Conversation) => conv.agent_id && conv.agent_name)
        .reduce((acc: { id: string; name: string }[], conv: Conversation) => {
          if (!acc.find(agent => agent.id === conv.agent_id)) {
            acc.push({ id: conv.agent_id!, name: conv.agent_name! });
          }
          return acc;
        }, []);

      setAvailableAgents(agents);

    } catch (error) {
      console.error('Error loading conversations:', error);
      // Mock data for development
      const mockConversations: Conversation[] = [
        {
          id: '1',
          title: 'Research on AI Ethics',
          agent_id: 'research-agent',
          agent_name: 'Research Assistant',
          message_count: 12,
          last_message_at: new Date().toISOString(),
          created_at: new Date(Date.now() - 2 * 3600000).toISOString(),
          preview: 'Discussion about ethical implications of AI development...'
        },
        {
          id: '2', 
          title: 'Code Review Help',
          agent_id: 'dev-agent',
          agent_name: 'Development Assistant',
          message_count: 8,
          last_message_at: new Date(Date.now() - 3600000).toISOString(),
          created_at: new Date(Date.now() - 6 * 3600000).toISOString(),
          preview: 'Help with React component optimization and best practices...'
        },
        {
          id: '3',
          title: 'Creative Writing Session',
          agent_id: 'creative-agent',
          agent_name: 'Creative Assistant',
          message_count: 15,
          last_message_at: new Date(Date.now() - 24 * 3600000).toISOString(),
          created_at: new Date(Date.now() - 48 * 3600000).toISOString(),
          preview: 'Working on a short story about space exploration...'
        }
      ];
      setConversations(mockConversations);
      setAvailableAgents([
        { id: 'research-agent', name: 'Research Assistant' },
        { id: 'dev-agent', name: 'Development Assistant' },
        { id: 'creative-agent', name: 'Creative Assistant' }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectConversation = (conversationId: string) => {
    onSelectConversation(conversationId);
    onOpenChange(false);
  };

  const handleDeleteConversation = async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent conversation selection
    
    try {
      const token = getAuthToken();
      const response = await fetch(`/api/v1/conversations/${conversationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setConversations(prev => prev.filter(conv => conv.id !== conversationId));
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  };

  const handleStartRename = (conversationId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent conversation selection
    setEditingConversationId(conversationId);
    setEditingTitle(currentTitle);
  };

  const handleCancelRename = () => {
    setEditingConversationId(null);
    setEditingTitle('');
  };

  const handleSaveRename = async (conversationId: string) => {
    if (!editingTitle.trim()) {
      handleCancelRename();
      return;
    }

    try {
      const token = getAuthToken();

      const response = await fetch(`/api/v1/conversations/${conversationId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ title: editingTitle.trim() }),
      });

      if (response.ok) {
        // Update the local state
        setConversations(prev => 
          prev.map(conv => 
            conv.id === conversationId 
              ? { ...conv, title: editingTitle.trim() }
              : conv
          )
        );
        handleCancelRename();
      } else {
        console.error('Failed to rename conversation');
      }
    } catch (error) {
      console.error('Error renaming conversation:', error);
    }
  };

  const getAgentIcon = (agentName?: string) => {
    if (!agentName) return <Bot className="w-4 h-4" />;
    
    const name = agentName.toLowerCase();
    if (name.includes('research')) return <Search className="w-4 h-4" />;
    if (name.includes('dev') || name.includes('code')) return <MessageSquare className="w-4 h-4" />;
    if (name.includes('creative') || name.includes('writing')) return <MessageCircle className="w-4 h-4" />;
    return <Bot className="w-4 h-4" />;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5" />
            Conversation History
          </DialogTitle>
        </DialogHeader>

        {/* Search and Filters */}
        <div className="flex flex-col gap-4 p-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 z-10" />
            <Input
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(value) => setSearchQuery(value)}
              className="pl-10"
              clearable
            />
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Time Filter */}
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4 text-gray-500" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as any)}
                className="text-sm border rounded px-2 py-1"
              >
                <option value="all">All Time</option>
                <option value="today">Today</option>
                <option value="week">This Week</option>
                <option value="month">This Month</option>
              </select>
            </div>

            {/* Agent Filter */}
            {availableAgents.length > 0 && (
              <div className="flex items-center gap-1">
                <Bot className="w-4 h-4 text-gray-500" />
                <select
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="text-sm border rounded px-2 py-1"
                >
                  <option value="all">All Agents</option>
                  {availableAgents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <Badge variant="outline" className="ml-auto">
              {filteredConversations.length} conversations
            </Badge>
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gt-green"></div>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <MessageCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>{searchQuery ? 'No conversations match your search' : 'No conversations yet'}</p>
              <p className="text-sm mt-1">Start a new conversation to see it here</p>
            </div>
          ) : (
            filteredConversations.map((conversation) => (
              <div
                key={conversation.id}
                onClick={() => handleSelectConversation(conversation.id)}
                className="group p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      {getAgentIcon(conversation.agent_name)}
                      {editingConversationId === conversation.id ? (
                        <div className="flex items-center gap-2 flex-1">
                          <Input
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e?.target?.value || '')}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleSaveRename(conversation.id);
                              } else if (e.key === 'Escape') {
                                handleCancelRename();
                              }
                            }}
                            className="text-sm h-7 flex-1"
                            autoFocus
                            onBlur={() => handleSaveRename(conversation.id)}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-1 h-7 w-7"
                            onClick={() => handleSaveRename(conversation.id)}
                          >
                            <Check className="w-3 h-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="p-1 h-7 w-7"
                            onClick={handleCancelRename}
                          >
                            <XIcon className="w-3 h-3" />
                          </Button>
                        </div>
                      ) : (
                        <h3 className="font-medium text-gray-900 truncate">
                          {conversation.title}
                        </h3>
                      )}
                      <Badge variant="outline" className="text-xs">
                        {conversation.message_count} messages
                      </Badge>
                    </div>
                    
                    <div className="flex items-center gap-4 text-sm text-gray-500 mb-2">
                      <span className="flex items-center gap-1">
                        <Bot className="w-3 h-3" />
                        {conversation.agent_name}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDistanceToNow(new Date(conversation.last_message_at))} ago
                      </span>
                    </div>

                    {conversation.preview && (
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {conversation.preview}
                      </p>
                    )}
                  </div>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="opacity-0 group-hover:opacity-100 p-1 h-8 w-8"
                      >
                        <MoreHorizontal className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem 
                        onClick={(e) => handleStartRename(conversation.id, conversation.title, e)}
                      >
                        <Edit3 className="w-4 h-4 mr-2" />
                        Rename
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        onClick={(e) => handleDeleteConversation(conversation.id, e)}
                        className="text-red-600"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center pt-4 border-t">
          <div className="text-sm text-gray-500">
            {filteredConversations.length > 0 && (
              <span>Click any conversation to resume</span>
            )}
          </div>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}