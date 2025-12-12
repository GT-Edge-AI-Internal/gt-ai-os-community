'use client';

import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatDistanceToNow } from 'date-fns';
import {
  Search,
  MessageCircle,
  Calendar,
  Bot,
  Clock,
  Filter,
  MoreHorizontal,
  Trash2,
  MessageSquare,
  Edit3,
  Check,
  X as XIcon,
  History,
  Loader2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { useConversations, useArchiveConversation, useRenameConversation, type Conversation } from '@/hooks/use-conversations';
import { useAgentsMinimal } from '@/hooks/use-agents';
import { ConversationSkeleton } from '@/components/ui/skeleton-loader';
import { useChatStore } from '@/stores/chat-store';

interface ConversationHistorySidebarProps {
  onSelectConversation: (conversationId: string) => void;
  currentConversationId?: string;
}

export function ConversationHistorySidebar({
  onSelectConversation,
  currentConversationId
}: ConversationHistorySidebarProps) {
  // Filter state (now used for server-side filtering)
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'today' | 'week' | 'month'>('all');
  const [selectedAgent, setSelectedAgent] = useState<string>('all');

  // React Query hooks for data fetching with server-side filtered infinite scroll
  const {
    data,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch
  } = useConversations({
    timeFilter: filter,
    search: searchQuery || undefined,
    agentId: selectedAgent !== 'all' ? selectedAgent : undefined
  });
  const { data: availableAgents = [] } = useAgentsMinimal();
  const archiveConversation = useArchiveConversation();
  const renameConversation = useRenameConversation();
  const { unreadCounts } = useChatStore();

  // UI state
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');

  // Intersection observer for infinite scroll
  const observerTarget = useRef<HTMLDivElement>(null);

  // Flatten paginated data into single array
  const conversations = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap(page => page.conversations);
  }, [data]);

  // Get total count from last page
  const totalCount = data?.pages?.[data.pages.length - 1]?.total || 0;

  // Intersection observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const target = entries[0];
        if (target.isIntersecting && hasNextPage && !isFetchingNextPage) {
          console.log('📜 Loading more conversations...');
          fetchNextPage();
        }
      },
      { threshold: 0.1, rootMargin: '100px' }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Listen for filter events from sidebar header
  useEffect(() => {
    const handleTimeFilter = (event: CustomEvent) => {
      setFilter(event.detail as 'all' | 'today' | 'week' | 'month');
      // Query will automatically refetch due to filter change in query key
    };

    const handleAgentFilter = (event: CustomEvent) => {
      setSelectedAgent(event.detail === 'all' ? 'all' : event.detail);
      // Query will automatically refetch due to filter change in query key
    };

    const handleRefreshConversations = () => {
      console.log('🔄 Refreshing conversations...');
      refetch();
    };

    window.addEventListener('filterTime', handleTimeFilter as EventListener);
    window.addEventListener('filterAgent', handleAgentFilter as EventListener);
    window.addEventListener('refreshConversations', handleRefreshConversations);

    return () => {
      window.removeEventListener('filterTime', handleTimeFilter as EventListener);
      window.removeEventListener('filterAgent', handleAgentFilter as EventListener);
      window.removeEventListener('refreshConversations', handleRefreshConversations);
    };
  }, [refetch]);

  // Conversations are now server-side filtered - no client-side filtering needed!
  // Just use the flattened data directly
  const filteredConversations = conversations;

  // Update conversation count in header when filtered list changes
  useEffect(() => {
    const countElement = document.getElementById('conversation-count');
    if (countElement) {
      countElement.textContent = `(${filteredConversations.length})`;
    }
  }, [filteredConversations]);

  const handleSelectConversation = (conversationId: string) => {
    onSelectConversation(conversationId);
  };

  const handleArchiveConversation = async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent conversation selection

    console.log('📦 Attempting to archive conversation:', conversationId);

    try {
      await archiveConversation.mutateAsync(conversationId);
      console.log('✅ Conversation archived successfully');
    } catch (error) {
      console.error('💥 Error archiving conversation:', error);
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
      await renameConversation.mutateAsync({
        conversationId,
        title: editingTitle.trim()
      });
      handleCancelRename();
    } catch (error) {
      console.error('Error renaming conversation:', error);
    }
  };

  const getAgentIcon = (agentName?: string) => {
    if (!agentName) return <Bot className="w-3 h-3" />;
    
    const name = agentName.toLowerCase();
    if (name.includes('research')) return <Search className="w-3 h-3" />;
    if (name.includes('dev') || name.includes('code')) return <MessageSquare className="w-3 h-3" />;
    if (name.includes('creative') || name.includes('writing')) return <MessageCircle className="w-3 h-3" />;
    return <Bot className="w-3 h-3" />;
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Search */}
      <div className="mb-2 flex-shrink-0">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-500 w-3 h-3 z-10" />
          <Input
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(value) => setSearchQuery(value)}
            className="pl-7 text-xs h-6 bg-white border-gt-gray-200"
            clearable
          />
        </div>
      </div>

      {/* Active Filters */}
      <div className="mb-2 flex-shrink-0">
        <div className="flex flex-wrap gap-1">
          {searchQuery && (
            <Badge className="text-xs bg-gt-green text-white">
              Search: {searchQuery}
            </Badge>
          )}
          {filter !== 'all' && (
            <Badge className="text-xs bg-gt-green text-white">
              {filter === 'today' ? 'Today' : filter === 'week' ? 'This Week' : 'This Month'}
            </Badge>
          )}
          {selectedAgent !== 'all' && (
            <Badge className="text-xs bg-gt-green text-white">
              Agent: {availableAgents.find(a => a.id === selectedAgent)?.name || 'Selected Agent'}
            </Badge>
          )}
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-2 p-2">
            {[...Array(5)].map((_, i) => (
              <ConversationSkeleton key={i} />
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="text-center py-8 text-gray-500 px-4">
            <MessageCircle className="w-8 h-8 mx-auto mb-3 text-gray-300" />
            <p className="text-xs">{searchQuery ? 'No conversations match your search' : 'No conversations yet'}</p>
            <p className="text-xs mt-1">Start a new conversation to see it here</p>
          </div>
        ) : (
          filteredConversations.map((conversation) => {
            const unreadCount = unreadCounts[conversation.id?.toString()] || 0;

            return (
            <div
              key={conversation.id}
              onClick={() => handleSelectConversation(conversation.id)}
              className={cn(
                "group p-1.5 rounded-md hover:bg-gt-gray-100 cursor-pointer transition-all duration-300 mb-1",
                currentConversationId === conversation.id && "bg-gt-green/10",
                unreadCount > 0 && "border-l-2 border-green-500 bg-green-500/5 shadow-[0_0_12px_rgba(16,185,129,0.2)]"
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  {editingConversationId === conversation.id ? (
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <Input
                        value={editingTitle}
                        onChange={(value) => setEditingTitle(value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleSaveRename(conversation.id);
                          } else if (e.key === 'Escape') {
                            e.preventDefault();
                            handleCancelRename();
                          }
                        }}
                        className="text-xs h-6 flex-1 bg-white border border-gt-gray-300 text-gray-900 px-2 rounded focus:outline-none focus:ring-1 focus:ring-gt-green focus:border-gt-green"
                        autoFocus
                        onBlur={(e) => {
                          // Add a small delay to allow button clicks to be processed first
                          setTimeout(() => {
                            if (document.activeElement?.tagName !== 'BUTTON') {
                              handleSaveRename(conversation.id);
                            }
                          }, 100);
                        }}
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-0.5 h-6 w-6 hover:bg-gt-gray-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSaveRename(conversation.id);
                        }}
                      >
                        <Check className="w-3 h-3 text-gt-green" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-0.5 h-6 w-6 hover:bg-gt-gray-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancelRename();
                        }}
                      >
                        <XIcon className="w-3 h-3 text-gray-500" />
                      </Button>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-center gap-1">
                        {unreadCount > 0 && (
                          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)] flex-shrink-0" />
                        )}
                        {getAgentIcon(conversation.agent_name)}
                        <h3 className="font-medium text-gray-900 text-xs truncate flex-1">
                          {conversation.title}
                        </h3>
                        <span className="text-xs text-gray-500 flex-shrink-0">
                          {conversation.message_count}
                        </span>
                        {unreadCount > 0 && (
                          <span className="inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white bg-green-500 rounded-full flex-shrink-0">
                            {unreadCount}
                          </span>
                        )}
                      </div>

                      <div className="text-xs text-gray-500 truncate">
                        {conversation.agent_name} • {formatDistanceToNow(new Date(conversation.last_message_at))} ago
                      </div>
                    </div>
                  )}
                </div>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="opacity-0 group-hover:opacity-100 p-0.5 h-5 w-5 ml-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="w-3 h-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-32 z-50 bg-white border border-gray-200 shadow-lg">
                    <DropdownMenuItem 
                      onClick={(e) => handleStartRename(conversation.id, conversation.title, e)}
                    >
                      <Edit3 className="w-3 h-3 mr-2" />
                      <span className="text-xs">Rename</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={(e) => handleArchiveConversation(conversation.id, e)}
                      className="text-gray-600"
                    >
                      <Trash2 className="w-3 h-3 mr-2" />
                      <span className="text-xs">Delete</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
            );
          })
        )}

        {/* Infinite scroll trigger and loading indicator */}
        {!isLoading && filteredConversations.length > 0 && (
          <div ref={observerTarget} className="py-4">
            {isFetchingNextPage && (
              <div className="flex items-center justify-center gap-2 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-xs">Loading more conversations...</span>
              </div>
            )}
            {!hasNextPage && conversations.length > 0 && (
              <div className="text-center text-gray-400 text-xs py-2">
                <History className="w-4 h-4 mx-auto mb-1" />
                <p>All conversations loaded</p>
                <p className="text-xs mt-0.5">
                  {conversations.length} of {totalCount} total
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}