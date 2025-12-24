'use client';

import React, { useEffect, useState } from 'react';
import { Search, ChevronDown, ChevronUp, MessageSquare, User, Bot, Calendar, Hash, Download } from 'lucide-react';
import { ObservabilityFilters } from './observability-dashboard';
import { api } from '@/services/api';
import { ExportModal } from './export-modal';
import { cn } from '@/lib/utils';
import { getUserRole } from '@/lib/permissions';
import { Input } from '@/components/ui/input';

interface ConversationListItem {
  id: string;
  title: string;
  user_id: string;
  user_email: string;
  user_name: string;
  agent_id: string;
  agent_name: string;
  total_messages: number;
  input_tokens: number;
  output_tokens: number;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

interface MessageDetail {
  id: string;
  role: string;
  content: string;
  content_type: string;
  token_count: number;
  model_used: string | null;
  created_at: string;
}

interface ConversationDetail {
  id: string;
  title: string;
  user_email: string;
  user_name: string;
  agent_name: string;
  agent_model: string;
  total_messages: number;
  total_tokens: number;
  created_at: string;
  updated_at: string;
  messages: MessageDetail[];
}

interface ObservableMember {
  id: string;
  email: string;
  display_name?: string;
}

interface ConversationBrowserProps {
  filters?: ObservabilityFilters;
  observabilityMode?: 'individual' | 'team';
  observableMembers?: ObservableMember[];
  selectedObservableMemberId?: string;
  onObservableMemberChange?: (memberId?: string) => void;
}

export function ConversationBrowser({
  filters,
  observabilityMode = 'individual',
  observableMembers = [],
  selectedObservableMemberId,
  onObservableMemberChange
}: ConversationBrowserProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [conversationDetails, setConversationDetails] = useState<Map<string, ConversationDetail>>(new Map());
  const [loadingDetails, setLoadingDetails] = useState<Set<string>>(new Set());

  // Pagination state
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [totalConversations, setTotalConversations] = useState(0);

  // Filter state
  const [selectedUser, setSelectedUser] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('');
  const [sortBy, setSortBy] = useState('created_at:desc');
  const [dateFilter, setDateFilter] = useState<'all' | 'custom' | 1 | 7 | 30 | 90>('all');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [customStartTime, setCustomStartTime] = useState('');
  const [customEndTime, setCustomEndTime] = useState('');
  const [showCustomDatePicker, setShowCustomDatePicker] = useState(false);
  const [tempStartDate, setTempStartDate] = useState('');
  const [tempEndDate, setTempEndDate] = useState('');
  const [tempStartTime, setTempStartTime] = useState('');
  const [tempEndTime, setTempEndTime] = useState('');

  // Unfiltered reference data for dropdown options
  const [allUsers, setAllUsers] = useState<Array<{ id: string; email: string }>>([]);
  const [allAgents, setAllAgents] = useState<Array<{ id: string; name: string }>>([]);

  // Export modal state
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportMode, setExportMode] = useState<'single' | 'filtered' | 'all'>('all');
  const [exportConversationId, setExportConversationId] = useState<string | undefined>();
  const [exportConversationTitle, setExportConversationTitle] = useState<string | undefined>();

  // User role state
  const [isAdmin, setIsAdmin] = useState(false);

  // Check user role on mount
  useEffect(() => {
    const role = getUserRole();
    setIsAdmin(role === 'admin' || role === 'developer');
  }, []);

  // Fetch filter options - refetch when observability mode or team changes
  useEffect(() => {
    async function fetchFilterOptions() {
      try {
        const params = new URLSearchParams();

        // Pass team_id when in team mode to get filtered agents
        if (observabilityMode === 'team' && filters?.teamId) {
          params.append('team_id', filters.teamId);
        }

        const response = await api.get(`/api/v1/observability/filters?${params.toString()}`);
        if (response.data) {
          setAllUsers(response.data.users.map((u: any) => ({ id: u.id, email: u.email })));
          setAllAgents(response.data.agents.map((a: any) => ({ id: a.id, name: a.name })));
        }
      } catch (err) {
        console.error('Failed to fetch filter options:', err);
      }
    }
    fetchFilterOptions();
  }, [observabilityMode, filters?.teamId]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setCurrentPage(0); // Reset to first page on search
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Initialize dropdowns from parent filters when conversations load
  useEffect(() => {
    if (!filters || conversations.length === 0) return;

    // Map parent filter IDs to dropdown values
    if (filters.userId) {
      const userConversation = conversations.find(c => c.user_id === filters.userId);
      if (userConversation && selectedUser !== userConversation.user_email) {
        setSelectedUser(userConversation.user_email);
      }
    }

    if (filters.agentId) {
      const agentConversation = conversations.find(c => c.agent_id === filters.agentId);
      if (agentConversation && selectedAgent !== agentConversation.agent_name) {
        setSelectedAgent(agentConversation.agent_name);
      }
    }
  }, [filters, conversations]);

  // Sync internal date state with parent filters
  useEffect(() => {
    if (!filters) return;

    if (filters.dateRange === 'custom' && filters.startDate && filters.endDate) {
      setDateFilter('custom');
      setCustomStartDate(filters.startDate);
      setCustomEndDate(filters.endDate);
      setCustomStartTime(filters.startTime || '');
      setCustomEndTime(filters.endTime || '');
    } else if (filters.dateRange === 'all') {
      setDateFilter('all');
      setCustomStartDate('');
      setCustomEndDate('');
      setCustomStartTime('');
      setCustomEndTime('');
    } else if (typeof filters.dateRange === 'number') {
      setDateFilter(filters.dateRange);
      setCustomStartDate('');
      setCustomEndDate('');
      setCustomStartTime('');
      setCustomEndTime('');
    }
  }, [filters?.dateRange, filters?.startDate, filters?.endDate, filters?.startTime, filters?.endTime]);

  useEffect(() => {
    fetchConversations();
  }, [filters, debouncedSearch, currentPage, pageSize, selectedUser, selectedAgent, sortBy, dateFilter, customStartDate, customEndDate, customStartTime, customEndTime, selectedObservableMemberId, observabilityMode]);

  async function fetchConversations() {
    setLoading(true);
    setError(null);

    try {
      const [orderBy, orderDirection] = sortBy.split(':');

      // Build params with parent filters taking precedence over internal state
      const params: Record<string, string> = {
        limit: pageSize.toString(),
        skip: (currentPage * pageSize).toString(),
        order_by: orderBy,
        order_direction: orderDirection
      };

      // Add search if present
      if (debouncedSearch) {
        params.search = debouncedSearch;
      }

      // Date filtering - use internal state (now synced with parent filters)
      if (dateFilter !== 'all') {
        if (dateFilter === 'custom' && customStartDate && customEndDate) {
          // Combine date + time into ISO timestamps (add :00 seconds since time input is HH:MM)
          const startDateTime = `${customStartDate}T${customStartTime ? customStartTime + ':00' : '00:00:00'}Z`;
          const endDateTime = `${customEndDate}T${customEndTime ? customEndTime + ':00' : '23:59:59'}Z`;
          params.start_date = startDateTime;
          params.end_date = endDateTime;
        } else if (typeof dateFilter === 'number') {
          params.days = dateFilter.toString();
        }
      }

      // Internal state filters (lower priority)
      if (selectedUser && userEmailToId.get(selectedUser)) {
        params.user_id = userEmailToId.get(selectedUser)!;
      }
      if (selectedAgent && agentNameToId.get(selectedAgent)) {
        params.agent_id = agentNameToId.get(selectedAgent)!;
      }

      // Parent-specific filters (non-date) override internal state
      if (filters?.userId) {
        params.user_id = filters.userId;
      }
      if (filters?.agentId) {
        params.agent_id = filters.agentId;
      }
      if (filters?.model) {
        params.model = filters.model;
      }
      if (filters?.specificDate) {
        params.specific_date = filters.specificDate;
      }
      if (filters?.teamId) {
        params.team_id = filters.teamId;
      }

      // Observable member filtering (team mode)
      if (observabilityMode === 'team' && selectedObservableMemberId) {
        params.observable_member_id = selectedObservableMemberId;
      }

      const queryParams = new URLSearchParams(params);

      const response = await api.get<ConversationListItem[]>(
        `/api/v1/observability/conversations?${queryParams.toString()}`
      );

      if (response.data) {
        setConversations(response.data);
        setTotalConversations(response.data.length); // Note: Backend doesn't return total count yet
      }
    } catch (err: any) {
      console.error('Failed to fetch conversations:', err);
      setError(err.response?.data?.detail || 'Failed to load conversations');
    } finally {
      setLoading(false);
    }
  }

  async function toggleRow(conversationId: string) {
    if (expandedRows.has(conversationId)) {
      // Collapse row
      const newExpanded = new Set(expandedRows);
      newExpanded.delete(conversationId);
      setExpandedRows(newExpanded);
    } else {
      // Expand row - fetch details if not already loaded
      const newExpanded = new Set(expandedRows);
      newExpanded.add(conversationId);
      setExpandedRows(newExpanded);

      if (!conversationDetails.has(conversationId)) {
        await fetchConversationDetail(conversationId);
      }
    }
  }

  async function fetchConversationDetail(conversationId: string) {
    setLoadingDetails(new Set(loadingDetails).add(conversationId));

    try {
      const response = await api.get<ConversationDetail>(
        `/api/v1/observability/conversations/${conversationId}`
      );

      if (response.data) {
        setConversationDetails(new Map(conversationDetails).set(conversationId, response.data));
      }
    } catch (err: any) {
      console.error('Failed to fetch conversation detail:', err);
      alert('Failed to load conversation details');
    } finally {
      const newLoading = new Set(loadingDetails);
      newLoading.delete(conversationId);
      setLoadingDetails(newLoading);
    }
  }

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'user': return 'bg-blue-100 text-blue-800';
      case 'agent': return 'bg-green-100 text-green-800';
      case 'system': return 'bg-gray-100 text-gray-800';
      case 'tool': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Use unfiltered reference data for dropdown options
  // Keep full objects to preserve unique IDs for React keys
  const uniqueUsers = React.useMemo(() =>
    allUsers.sort((a, b) => a.email.localeCompare(b.email)),
    [allUsers]
  );

  const uniqueAgents = React.useMemo(() =>
    allAgents.sort((a, b) => a.name.localeCompare(b.name)),
    [allAgents]
  );

  // Create lookup maps from email/name to ID using reference data
  const userEmailToId = React.useMemo(() => {
    const map = new Map<string, string>();
    allUsers.forEach(u => map.set(u.email, u.id));
    return map;
  }, [allUsers]);

  const agentNameToId = React.useMemo(() => {
    const map = new Map<string, string>();
    allAgents.forEach(a => map.set(a.name, a.id));
    return map;
  }, [allAgents]);

  // Clear all filters
  function clearFilters() {
    setSelectedUser('');
    setSelectedAgent('');
    setSortBy('created_at:desc');
    setSearchQuery('');
    setDateFilter('all');
    setCustomStartDate('');
    setCustomEndDate('');
    setCustomStartTime('');
    setCustomEndTime('');
    setCurrentPage(0);
    onObservableMemberChange?.(undefined);
  }

  function openExportModal(mode: 'single' | 'filtered' | 'all', conversationId?: string, conversationTitle?: string) {
    setExportMode(mode);
    setExportConversationId(conversationId);
    setExportConversationTitle(conversationTitle);
    setShowExportModal(true);
  }

  function closeExportModal() {
    setShowExportModal(false);
    setExportConversationId(undefined);
    setExportConversationTitle(undefined);
  }

  const totalPages = Math.ceil(totalConversations / pageSize);

  if (loading && conversations.length === 0) {
    return (
      <div className="bg-gt-white border border-gt-gray-200 rounded-lg p-6">
        <div className="h-8 bg-gt-gray-200 rounded w-64 mb-4 animate-pulse"></div>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gt-gray-100 rounded animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <p className="text-red-800 font-medium">Failed to load conversations</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="bg-gt-white border border-gt-gray-200 rounded-lg overflow-hidden">
      {/* Filter Bar */}
      <div className="p-6 border-b border-gt-gray-200 space-y-4">
        {/* Search and Filters Row */}
        <div className="flex flex-wrap gap-3 items-start">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gt-gray-400 z-10" />
            <Input
              type="text"
              placeholder="Search conversations and messages..."
              value={searchQuery}
              onChange={(value) => setSearchQuery(value)}
              className="pl-9 text-sm"
              clearable
            />
          </div>

          {/* Observable Member Filter - Show in team mode */}
          {observabilityMode === 'team' && observableMembers && observableMembers.length > 0 && (
            <div className="flex items-center gap-2 border border-green-200 bg-green-50 rounded-lg px-3 py-1.5 min-w-[140px] w-40">
              <User className="w-4 h-4 text-gt-green flex-shrink-0" />
              <select
                value={selectedObservableMemberId || ''}
                onChange={(e) => {
                  onObservableMemberChange?.(e.target.value || undefined);
                  setCurrentPage(0);
                }}
                disabled={observableMembers.length === 0}
                className="bg-transparent border-none text-sm font-medium text-green-900 focus:outline-none truncate flex-1 min-w-0"
              >
                <option value="">User</option>
                {observableMembers.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.display_name || member.email}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* User Filter - Show for admins in individual mode only */}
          {observabilityMode === 'individual' && isAdmin && (
            <div className="flex items-center gap-2 border border-gt-gray-300 rounded-lg px-3 py-1.5 min-w-[140px] w-40 bg-gt-white">
              <User className="w-4 h-4 text-gt-gray-500 flex-shrink-0" />
              <select
                value={selectedUser}
                onChange={(e) => {
                  setSelectedUser(e.target.value);
                  setCurrentPage(0);
                }}
                className="bg-transparent border-none text-sm font-medium text-gt-gray-900 focus:outline-none truncate flex-1 min-w-0"
              >
                <option value="">All Users</option>
                {uniqueUsers.map(user => (
                  <option key={user.id} value={user.email}>
                    {user.email}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Agent Filter */}
          <div className="relative min-w-[140px] w-40">
            <select
              value={selectedAgent}
              onChange={(e) => {
                setSelectedAgent(e.target.value);
                setCurrentPage(0);
              }}
              className="w-full appearance-none border border-gt-gray-300 rounded-lg pl-3 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green bg-gt-white cursor-pointer text-transparent"
              style={{ backgroundImage: 'none' }}
            >
              <option value="">All Agents</option>
              {uniqueAgents.map(agent => (
                <option key={agent.id} value={agent.name}>{agent.name}</option>
              ))}
            </select>
            <div className="absolute inset-y-0 left-0 right-8 flex items-center pl-3 pointer-events-none">
              <span className="text-sm text-gt-gray-900 truncate">
                {selectedAgent ? 'Selected Agent' : 'All Agents'}
              </span>
            </div>
            <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
              <ChevronDown className="w-4 h-4 text-gt-gray-500" />
            </div>
          </div>

          {/* Date Range Filter - always show dropdown */}
          <div className="flex flex-col gap-2 min-w-[140px] w-40">
            <select
              value={dateFilter}
              onChange={(e) => {
                const value = e.target.value;
                if (value === 'custom') {
                  setShowCustomDatePicker(true);
                  setTempStartDate(customStartDate || '');
                  setTempEndDate(customEndDate || '');
                  setTempStartTime(customStartTime || '00:00');
                  setTempEndTime(customEndTime || '23:59');
                } else if (value === 'all') {
                  setDateFilter('all');
                  setCustomStartDate('');
                  setCustomEndDate('');
                  setCurrentPage(0);
                } else {
                  setDateFilter(parseInt(value) as 1 | 7 | 30 | 90);
                  setCustomStartDate('');
                  setCustomEndDate('');
                  setCurrentPage(0);
                }
              }}
              className="border border-gt-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green bg-gt-white"
            >
              <option value="all">All Time</option>
              <option value={1}>Last 24 hours</option>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value="custom">Custom Range...</option>
            </select>

            {/* Show custom date range as clickable badge when active */}
            {dateFilter === 'custom' && customStartDate && customEndDate && (
              <button
                onClick={() => {
                  setShowCustomDatePicker(true);
                  setTempStartDate(customStartDate);
                  setTempEndDate(customEndDate);
                  setTempStartTime(customStartTime || '00:00');
                  setTempEndTime(customEndTime || '23:59');
                }}
                className="text-xs text-gt-gray-600 hover:text-gt-green transition-colors text-left px-2"
              >
                📅 {new Date(customStartDate + 'T12:00:00').toLocaleDateString()} - {new Date(customEndDate + 'T12:00:00').toLocaleDateString()}
              </button>
            )}
          </div>

          {/* Sort Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value);
              setCurrentPage(0);
            }}
            className="border border-gt-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green bg-gt-white min-w-[160px] w-44"
          >
            <option value="created_at:desc">Created (Newest)</option>
            <option value="created_at:asc">Created (Oldest)</option>
            <option value="total_messages:desc">Messages (High)</option>
            <option value="total_messages:asc">Messages (Low)</option>
            <option value="input_tokens:desc">Input Tokens (High)</option>
            <option value="input_tokens:asc">Input Tokens (Low)</option>
            <option value="output_tokens:desc">Output Tokens (High)</option>
            <option value="output_tokens:asc">Output Tokens (Low)</option>
          </select>

          {/* Clear Filters Button */}
          {(selectedUser || selectedAgent || sortBy !== 'created_at:desc' || searchQuery || dateFilter !== 'all') && (
            <button
              onClick={clearFilters}
              className="px-3 py-2 text-sm text-gt-gray-600 hover:text-gt-gray-900 hover:bg-gt-gray-50 rounded-lg transition-colors whitespace-nowrap"
            >
              Clear All
            </button>
          )}

          {/* Export Results Button */}
          <button
            onClick={() => openExportModal(
              selectedUser || selectedAgent || searchQuery ? 'filtered' : 'all'
            )}
            className="px-4 py-2 bg-gt-green text-white rounded-lg hover:bg-gt-green-dark transition-colors flex items-center gap-2 text-sm font-medium whitespace-nowrap"
          >
            <Download className="w-4 h-4" />
            Export Results
          </button>
        </div>

        {/* Active Filters Badges */}
        {(selectedUser || selectedAgent || filters?.model || filters?.specificDate || (filters?.dateRange === 'custom' && filters?.startDate && filters?.endDate) || (dateFilter === 'custom' && customStartDate && customEndDate)) && (
          <div className="flex gap-2 flex-wrap">
            {selectedUser && (
              <span className="inline-flex items-center gap-1 bg-gt-green/10 text-gt-green px-3 py-1 rounded-full text-xs font-medium">
                <User className="w-3 h-3" />
                User: {selectedUser}
                <button
                  onClick={() => setSelectedUser('')}
                  className="hover:bg-gt-green/20 rounded-full p-0.5"
                >
                  ×
                </button>
              </span>
            )}
            {selectedAgent && (
              <span className="inline-flex items-center gap-1 bg-gt-green/10 text-gt-green px-3 py-1 rounded-full text-xs font-medium">
                <Bot className="w-3 h-3" />
                Agent: {selectedAgent}
                <button
                  onClick={() => setSelectedAgent('')}
                  className="hover:bg-gt-green/20 rounded-full p-0.5"
                >
                  ×
                </button>
              </span>
            )}
            {filters?.model && (
              <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-xs font-medium">
                Model: {filters.model}
              </span>
            )}
            {filters?.specificDate && (
              <span className="inline-flex items-center gap-1 bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-medium">
                <Calendar className="w-3 h-3" />
                Date: {new Date(filters.specificDate).toLocaleDateString()}
              </span>
            )}
            {(dateFilter === 'custom' && customStartDate && customEndDate) && (
              <span className="inline-flex items-center gap-1 bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-medium">
                <Calendar className="w-3 h-3" />
                Range: {new Date(customStartDate + 'T12:00:00').toLocaleDateString()} - {new Date(customEndDate + 'T12:00:00').toLocaleDateString()}
                <button
                  onClick={() => {
                    setDateFilter('all');
                    setCustomStartDate('');
                    setCustomEndDate('');
                  }}
                  className="hover:bg-green-200 rounded-full p-0.5"
                >
                  ×
                </button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Custom Date & Time Range Modal */}
      {showCustomDatePicker && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gt-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gt-gray-900 mb-4">Custom Date & Time Range</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gt-gray-700 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={tempStartDate}
                  onChange={(e) => setTempStartDate(e.target.value)}
                  className="w-full border border-gt-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gt-gray-700 mb-1">
                  Start Time (optional)
                </label>
                <input
                  type="time"
                  value={tempStartTime}
                  onChange={(e) => setTempStartTime(e.target.value)}
                  className="w-full border border-gt-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green"
                  placeholder="00:00"
                />
                <p className="text-xs text-gt-gray-500 mt-1">Defaults to 00:00:00 if not specified</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gt-gray-700 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={tempEndDate}
                  onChange={(e) => setTempEndDate(e.target.value)}
                  className="w-full border border-gt-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gt-gray-700 mb-1">
                  End Time (optional)
                </label>
                <input
                  type="time"
                  value={tempEndTime}
                  onChange={(e) => setTempEndTime(e.target.value)}
                  className="w-full border border-gt-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green"
                  placeholder="23:59"
                />
                <p className="text-xs text-gt-gray-500 mt-1">Defaults to 23:59:59 if not specified</p>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCustomDatePicker(false);
                }}
                className="flex-1 px-4 py-2 border border-gt-gray-300 rounded-lg text-sm font-medium text-gt-gray-700 hover:bg-gt-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (tempStartDate && tempEndDate) {
                    // Atomically set both the date/time filter and the custom values
                    setCustomStartDate(tempStartDate);
                    setCustomEndDate(tempEndDate);
                    setCustomStartTime(tempStartTime);
                    setCustomEndTime(tempEndTime);
                    setDateFilter('custom');
                    setCurrentPage(0);
                  }
                  setShowCustomDatePicker(false);
                }}
                disabled={!tempStartDate || !tempEndDate}
                className="flex-1 px-4 py-2 bg-gt-green text-white rounded-lg text-sm font-medium hover:bg-gt-green-dark transition-colors disabled:bg-gt-gray-300 disabled:cursor-not-allowed"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gt-gray-200">
          <thead className="bg-gt-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gt-gray-500 uppercase tracking-wider w-8">
                {/* Expand icon column */}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Conversation Title
              </th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                User
              </th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Agent
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-2 py-3 text-center text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Messages
              </th>
              <th className="px-2 py-3 text-center text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Input
              </th>
              <th className="px-2 py-3 text-center text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Output
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gt-gray-500 uppercase tracking-wider">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="bg-gt-white divide-y divide-gt-gray-200">
            {conversations.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-6 py-12 text-center">
                  <MessageSquare className="w-12 h-12 text-gt-gray-300 mx-auto mb-3" />
                  <p className="text-gt-gray-600">
                    {searchQuery ? 'No conversations match your search' : 'No conversations found'}
                  </p>
                </td>
              </tr>
            ) : (
              conversations.map((conv) => {
                const isExpanded = expandedRows.has(conv.id);
                const detail = conversationDetails.get(conv.id);
                const isLoadingDetail = loadingDetails.has(conv.id);

                return (
                  <React.Fragment key={conv.id}>
                    {/* Main Row */}
                    <tr
                      className="hover:bg-gt-gray-50 cursor-pointer transition-colors"
                      onClick={() => toggleRow(conv.id)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {isExpanded ? (
                          <ChevronUp className="w-5 h-5 text-gt-green" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-gt-gray-400" />
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gt-gray-900 font-medium max-w-[300px]">
                        {conv.title}
                      </td>
                      <td className="px-3 py-4 text-sm text-gt-gray-600 max-w-[180px]">
                        <div className="truncate">{conv.user_name || 'Unknown'}</div>
                        <div className="text-xs text-gt-gray-500 truncate">{conv.user_email}</div>
                      </td>
                      <td className="px-3 py-4 text-sm text-gt-gray-600 max-w-[150px]">
                        {conv.agent_name}
                      </td>
                      <td className="px-2 py-4 text-xs">
                        <div className="flex flex-col items-center gap-1">
                          <div className={cn(
                            "w-2 h-2 rounded-full",
                            conv.is_archived ? "bg-gray-400" : "bg-green-500"
                          )} />
                          <span className="text-gt-gray-600 whitespace-nowrap">
                            {conv.is_archived ? 'Deleted' : 'Active'}
                          </span>
                        </div>
                      </td>
                      <td className="px-2 py-4 whitespace-nowrap text-sm text-gt-gray-600 text-center">
                        {conv.total_messages}
                      </td>
                      <td className="px-2 py-4 whitespace-nowrap text-sm text-gt-gray-600 text-center">
                        {conv.input_tokens.toLocaleString()}
                      </td>
                      <td className="px-2 py-4 whitespace-nowrap text-sm text-gt-gray-600 text-center">
                        {conv.output_tokens.toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-sm text-gt-gray-600 min-w-[100px]">
                        <div>{new Date(conv.created_at).toLocaleDateString()}</div>
                        <div className="text-xs text-gt-gray-500">{new Date(conv.created_at).toLocaleTimeString()}</div>
                      </td>
                    </tr>

                    {/* Expanded Row - Messages */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={9} className="px-6 py-4 bg-gt-gray-50">
                          {isLoadingDetail ? (
                            <div className="text-center py-8">
                              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gt-green mx-auto"></div>
                              <p className="text-gt-gray-600 mt-3 text-sm">Loading messages...</p>
                            </div>
                          ) : detail ? (
                            <div className="space-y-3">
                              <div className="flex items-center justify-between mb-4">
                                <h4 className="font-medium text-gt-gray-900">Messages</h4>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm text-gt-gray-600">
                                    Model: {detail.agent_model}
                                  </span>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openExportModal('single', conv.id, conv.title);
                                    }}
                                    className="p-2 text-gt-green hover:bg-gt-green/10 rounded-lg transition-colors"
                                    title="Export this conversation"
                                  >
                                    <Download className="w-4 h-4" />
                                  </button>
                                </div>
                              </div>
                              {detail.messages.map((message, idx) => (
                                <div
                                  key={message.id}
                                  className="bg-gt-white border border-gt-gray-200 rounded-lg p-4"
                                >
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <span className={`px-2 py-1 rounded text-xs font-medium uppercase ${getRoleColor(message.role)}`}>
                                        {message.role}
                                      </span>
                                      {message.model_used && (
                                        <span className="text-xs text-gt-gray-500">
                                          {message.model_used}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex items-center gap-3 text-xs text-gt-gray-500">
                                      <span>{message.token_count} tokens</span>
                                      <span>{new Date(message.created_at).toLocaleTimeString()}</span>
                                    </div>
                                  </div>
                                  <div className="prose prose-sm max-w-none">
                                    <pre className="whitespace-pre-wrap break-all font-sans text-sm text-gt-gray-700 bg-gt-gray-50 p-3 rounded overflow-x-auto" style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                                      {message.content}
                                    </pre>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-center text-gt-gray-600 py-4">Failed to load messages</p>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {conversations.length > 0 && (
        <div className="px-6 py-4 border-t border-gt-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm text-gt-gray-600">Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(0);
              }}
              className="border border-gt-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-gt-green"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-gt-gray-600">
              Page {currentPage + 1}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0}
                className="px-3 py-1 border border-gt-gray-300 rounded text-sm hover:bg-gt-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={conversations.length < pageSize}
                className="px-3 py-1 border border-gt-gray-300 rounded text-sm hover:bg-gt-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export Modal */}
      {showExportModal && (() => {
        // Build complete filter object including conversation browser's internal filters
        // Must include startDate/endDate for custom date range filtering to work
        const activeFilters = {
          dateRange: dateFilter !== 'all' ? dateFilter : (filters?.dateRange || 30),
          startDate: customStartDate || filters?.startDate,
          endDate: customEndDate || filters?.endDate,
          startTime: customStartTime || filters?.startTime,
          endTime: customEndTime || filters?.endTime,
          specificDate: filters?.specificDate,
          userId: selectedUser ? userEmailToId.get(selectedUser) : undefined,
          agentId: selectedAgent ? agentNameToId.get(selectedAgent) : undefined
        };

        return (
          <ExportModal
            filters={activeFilters}
            onClose={closeExportModal}
            mode={exportMode}
            conversationId={exportConversationId}
            conversationTitle={exportConversationTitle}
            searchQuery={debouncedSearch}
          />
        );
      })()}
    </div>
  );
}
