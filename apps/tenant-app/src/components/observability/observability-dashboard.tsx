'use client';

import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Filter, Database } from 'lucide-react';
import { UsageCombinedView } from './usage-combined-view';
import { StorageBreakdown } from './storage-breakdown';
import { ConversationBrowser } from './conversation-browser';
import { api } from '@/services/api';
import { getUserRole } from '@/lib/permissions';

export type DateRange = 1 | 7 | 30 | 90 | 365 | 'all' | 'custom';

export interface ObservabilityFilters {
  dateRange: DateRange;
  startDate?: string; // ISO date string for custom range
  endDate?: string;   // ISO date string for custom range
  startTime?: string; // HH:MM format for custom range
  endTime?: string;   // HH:MM format for custom range
  userId?: string;
  agentId?: string;
  model?: string;
  specificDate?: string;
  teamId?: string;  // Team filter for team observers
}

/**
 * ObservabilityDashboard - Main observability dashboard component
 * Available to all authenticated users with role-based data filtering:
 * - Admins/Developers: See all platform activity with user filtering
 * - Team Observers (owners/managers): See Observable team members' activity with team filtering
 * - Analysts/Students: See only their personal activity
 */
interface UsageData {
  overview: any;
  time_series: any[];
  breakdown_by_user: any[];
  breakdown_by_agent: any[];
  breakdown_by_model: any[];
}

export function ObservabilityDashboard() {
  const [filters, setFilters] = useState<ObservabilityFilters>({
    dateRange: 'all'
  });
  const [activeTab, setActiveTab] = useState<'overview' | 'conversations' | 'storage'>('overview');
  const [usageData, setUsageData] = useState<UsageData | null>(null);
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [availableTeams, setAvailableTeams] = useState<any[]>([]);
  const [observableMembers, setObservableMembers] = useState<any[]>([]);
  const [selectedObservableMemberId, setSelectedObservableMemberId] = useState<string | undefined>();
  const [observabilityMode, setObservabilityMode] = useState<'individual' | 'team'>('individual');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string>('student');
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [isTeamObserver, setIsTeamObserver] = useState<boolean>(false);

  // Check user role on mount
  useEffect(() => {
    const role = getUserRole();
    setUserRole(role);
    setIsAdmin(role === 'admin' || role === 'developer');
  }, []);

  // Fetch filter options (users list for admins, teams list for team observers)
  // Re-fetch when team selection changes in team mode to get team-scoped agents/datasets
  useEffect(() => {
    async function fetchFilterOptions() {
      try {
        // Build URL with team_id parameter when in team mode
        let url = '/api/v1/observability/filters';
        if (observabilityMode === 'team' && filters.teamId && filters.teamId !== 'all') {
          url += `?team_id=${filters.teamId}`;
        } else if (observabilityMode === 'team' && filters.teamId === 'all') {
          url += '?team_id=all';
        }

        console.log('[Observability] Fetching filter options from:', url);
        const response = await api.get(url);

        if (response.data?.users) {
          // Transform to match BreakdownItem format
          setAllUsers(response.data.users.map((u: any) => ({
            id: u.id,
            label: u.email,
            value: 0,
            percentage: 0
          })));
        }

        if (response.data?.teams) {
          // Team observer - store teams list
          setAvailableTeams(response.data.teams);
          setIsTeamObserver(true);
        }
      } catch (err) {
        console.error('Failed to fetch filter options:', err);
      }
    }

    // Fetch for admins or team observers (anyone who can see multiple users)
    if (isAdmin || userRole === 'analyst') {
      fetchFilterOptions();
    }
  }, [isAdmin, userRole, observabilityMode, filters.teamId]);

  // Fetch Observable members when in team mode
  useEffect(() => {
    async function fetchObservableMembers() {
      console.log('[Observability] ===== FETCHING OBSERVABLE MEMBERS =====');
      console.log('[Observability] Mode:', observabilityMode);
      console.log('[Observability] TeamId:', filters.teamId);
      console.log('[Observability] isTeamObserver:', isTeamObserver);
      console.log('[Observability] Current observableMembers length:', observableMembers.length);

      if (observabilityMode !== 'team') {
        console.log('[Observability] Not in team mode, clearing Observable members');
        setObservableMembers([]);
        setSelectedObservableMemberId(undefined);
        return;
      }

      try {
        let response;
        if (filters.teamId === 'all' || !filters.teamId) {
          // "All Teams" mode - fetch all Observable members across all teams
          console.log('[Observability] Fetching all Observable members across all teams');
          response = await api.get('/api/v1/observability/teams/observable-members');
        } else {
          // Specific team mode - fetch Observable members for this team
          console.log('[Observability] Fetching Observable members for team:', filters.teamId);
          response = await api.get(`/api/v1/observability/teams/${filters.teamId}/observable-members`);
        }

        console.log('[Observability] Observable members response:', response.data);

        if (response.data?.members) {
          console.log('[Observability] Setting', response.data.members.length, 'Observable members');
          console.log('[Observability] Members:', response.data.members.map((m: any) => m.email || m.display_name).join(', '));
          setObservableMembers(response.data.members);
        } else {
          console.log('[Observability] No members in response');
          console.log('[Observability] Response structure:', Object.keys(response.data || {}));
          setObservableMembers([]);
        }
      } catch (err) {
        console.error('[Observability] Failed to fetch Observable members:', err);
        setObservableMembers([]);
      }
      console.log('[Observability] =====================================');
    }

    fetchObservableMembers();
  }, [observabilityMode, filters.teamId]);

  // Handle mode switching - clear inappropriate filters and initialize team mode with 'All Teams'
  useEffect(() => {
    if (observabilityMode === 'individual') {
      // Clear team-specific filters completely
      setFilters(prev => ({
        ...prev,
        teamId: undefined,
        userId: undefined  // Explicitly clear to force backend to derive from token
      }));
      setSelectedObservableMemberId(undefined);
      setObservableMembers([]);
    } else {
      // Clear individual user filter when switching to team mode
      // Initialize with "All Teams" by default
      setFilters(prev => ({ ...prev, userId: undefined, teamId: 'all' }));
    }
  }, [observabilityMode]);

  // Fetch all usage data once when filters or selected member change
  // Note: observabilityMode removed from dependencies to prevent race condition
  // (mode switching already updates filters, so filters dependency is sufficient)
  useEffect(() => {
    if (activeTab === 'overview') {
      fetchUsageData();
    }
  }, [filters, activeTab, selectedObservableMemberId]);

  async function fetchUsageData() {
    setLoading(true);
    setError(null);

    // Comprehensive debugging for mode-based filtering
    console.log('[Fetch Debug] ===== FETCHING USAGE DATA =====');
    console.log('[Fetch Debug] Observability Mode:', observabilityMode);
    console.log('[Fetch Debug] Filters object:', JSON.stringify(filters, null, 2));
    console.log('[Fetch Debug] Selected Observable Member:', selectedObservableMemberId);
    console.log('[Fetch Debug] Active Tab:', activeTab);

    try {
      const params = new URLSearchParams();

      // Handle date range
      if (filters.dateRange === 'all') {
        // Don't send days parameter for all time
      } else if (filters.dateRange === 'custom') {
        // Combine date + time into ISO timestamps
        if (filters.startDate) {
          const startDateTime = `${filters.startDate}T${filters.startTime || '00:00:00'}Z`;
          params.append('start_date', startDateTime);
        }
        if (filters.endDate) {
          const endDateTime = `${filters.endDate}T${filters.endTime || '23:59:59'}Z`;
          params.append('end_date', endDateTime);
        }
      } else {
        params.append('days', filters.dateRange.toString());
      }

      // In individual mode, use filters.userId
      // In team mode, use selectedObservableMemberId if set, otherwise don't filter by user
      if (observabilityMode === 'individual' && filters.userId) {
        params.append('user_id', filters.userId);
      } else if (observabilityMode === 'team' && selectedObservableMemberId) {
        params.append('user_id', selectedObservableMemberId);
      }

      // Only send team_id in team mode when a team is actually selected
      if (observabilityMode === 'team' && filters.teamId) {
        params.append('team_id', filters.teamId);
      }

      console.log('[Fetch Debug] URL parameters being sent:', params.toString());
      console.log('[Fetch Debug] Full URL:', `/api/v1/observability/usage?${params.toString()}`);
      console.log('[Fetch Debug] =====================================');

      const response = await api.get(`/api/v1/observability/usage?${params.toString()}`);
      if (response.data) {
        setUsageData(response.data);
      }
    } catch (err: any) {
      console.error('Failed to fetch usage data:', err);
      setError(err.response?.data?.detail || 'Failed to load usage data');
    } finally {
      setLoading(false);
    }
  }

  function handleChartClick(newFilters: { userId?: string; agentId?: string; model?: string; specificDate?: string }) {
    // Merge new filters with existing ones
    setFilters({
      ...filters,
      ...newFilters
    });
    // Switch to conversations tab
    setActiveTab('conversations');
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <BarChart3 className="w-8 h-8 text-gt-green" />
              Observability
              {!isAdmin && !isTeamObserver && (
                <span className="ml-2 px-3 py-1 bg-blue-100 text-blue-700 text-sm font-medium rounded-full">
                  My Activity
                </span>
              )}
              {isTeamObserver && !isAdmin && observabilityMode === 'team' && (
                <span className="ml-2 px-3 py-1 bg-green-100 text-green-700 text-sm font-medium rounded-full">
                  Team Observability
                </span>
              )}
            </h1>
            <p className="text-gray-600 mt-1">
              {isAdmin
                ? 'Monitor usage, track activity, and view conversations across your tenant'
                : isTeamObserver
                ? observabilityMode === 'individual'
                  ? 'Monitor your personal usage, track your activity, and view your conversations'
                  : 'Monitor team observability usage and track their activity'
                : 'Monitor your personal usage, track your activity, and view your conversations'
              }
            </p>
          </div>

          {/* Mode Switcher Buttons - only show for team observers (not admins) */}
          {isTeamObserver && !isAdmin && (
            <div className="flex items-center gap-1 bg-gt-gray-100 rounded-lg p-1">
              <button
                onClick={() => setObservabilityMode('individual')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  observabilityMode === 'individual'
                    ? 'bg-white text-gt-green shadow-sm'
                    : 'text-gt-gray-600 hover:text-gt-gray-900'
                }`}
              >
                Individual
              </button>
              <button
                onClick={() => setObservabilityMode('team')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  observabilityMode === 'team'
                    ? 'bg-white text-gt-green shadow-sm'
                    : 'text-gt-gray-600 hover:text-gt-gray-900'
                }`}
              >
                Team
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gt-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`
              py-4 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'overview'
                ? 'border-gt-green text-gt-green'
                : 'border-transparent text-gt-gray-500 hover:text-gt-gray-700 hover:border-gt-gray-300'
              }
            `}
          >
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Usage Overview
            </div>
          </button>
          <button
            onClick={() => setActiveTab('conversations')}
            className={`
              py-4 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'conversations'
                ? 'border-gt-green text-gt-green'
                : 'border-transparent text-gt-gray-500 hover:text-gt-gray-700 hover:border-gt-gray-300'
              }
            `}
          >
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4" />
              Conversations
            </div>
          </button>
          <button
            onClick={() => setActiveTab('storage')}
            className={`
              py-4 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'storage'
                ? 'border-gt-green text-gt-green'
                : 'border-transparent text-gt-gray-500 hover:text-gt-gray-700 hover:border-gt-gray-300'
              }
            `}
          >
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Storage
            </div>
          </button>
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Subtle loading indicator */}
          {loading && (
            <div className="flex items-center justify-center py-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gt-green"></div>
              <span className="ml-2 text-sm text-gt-gray-600">Updating data...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-6">
              <p className="text-red-800 font-medium">Failed to load usage data</p>
              <p className="text-red-600 text-sm mt-1">{error}</p>
            </div>
          )}

          {usageData && (
            <div className={loading ? 'opacity-60 pointer-events-none transition-opacity' : 'transition-opacity'}>
              {/* Combined Usage Overview: Time Series + Agent/Model Breakdown */}
              <UsageCombinedView
                overview={usageData.overview}
                timeSeriesData={usageData.time_series}
                agentData={usageData.breakdown_by_agent}
                modelData={usageData.breakdown_by_model}
                userData={usageData.breakdown_by_user}
                allUsers={allUsers}
                dateRange={filters.dateRange}
                onDateRangeChange={(range) => setFilters({ ...filters, dateRange: range })}
                startDate={filters.startDate}
                endDate={filters.endDate}
                startTime={filters.startTime}
                endTime={filters.endTime}
                onCustomDateChange={(startDate, endDate, startTime, endTime) => setFilters({ ...filters, dateRange: 'custom', startDate, endDate, startTime, endTime })}
                userId={filters.userId}
                onUserChange={(userId) => setFilters({ ...filters, userId })}
                teamId={filters.teamId}
                onTeamChange={(teamId) => setFilters({ ...filters, teamId })}
                availableTeams={availableTeams}
                isTeamObserver={isTeamObserver}
                observabilityMode={observabilityMode}
                observableMembers={observableMembers}
                selectedObservableMemberId={selectedObservableMemberId}
                onObservableMemberChange={(memberId) => setSelectedObservableMemberId(memberId)}
                onNavigateToConversations={handleChartClick}
                isAdmin={isAdmin}
              />
            </div>
          )}

          {/* Initial loading state - only show when no data exists yet */}
          {!usageData && !error && loading && (
            <div className="text-center py-16">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gt-green mx-auto"></div>
              <p className="text-gt-gray-600 mt-4">Loading usage data...</p>
            </div>
          )}
        </div>
      )}

      {/* Conversations Tab */}
      {activeTab === 'conversations' && (
        <ConversationBrowser
          filters={filters}
          observabilityMode={observabilityMode}
          observableMembers={observableMembers}
          selectedObservableMemberId={selectedObservableMemberId}
          onObservableMemberChange={(memberId) => setSelectedObservableMemberId(memberId)}
        />
      )}

      {/* Storage Tab */}
      {activeTab === 'storage' && (
        <StorageBreakdown
          observabilityMode={observabilityMode}
          teamId={filters.teamId}
          isTeamObserver={isTeamObserver}
        />
      )}
    </div>
  );
}
