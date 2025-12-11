'use client';

import { useState, useRef } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { TrendingUp, Bot, Cpu, Calendar, User, MessageSquare, FileText, Zap, Users as UsersIcon, Download, Users2 } from 'lucide-react';
import { exportChartAsPNG, generateExportFilename } from '@/lib/chart-export';

export type DateRange = 1 | 7 | 30 | 90 | 365 | 'all' | 'custom';

interface OverviewData {
  total_conversations: number;
  total_messages: number;
  total_tokens: number;
  unique_users: number;
}

interface TimeSeriesData {
  date: string;
  conversation_count: number;
  message_count: number;
  token_count: number;
  unique_users: number;
}

interface BreakdownItem {
  id: string;
  label: string;
  value: number;
  percentage: number;
  metadata?: {
    messages?: number;
    tokens?: number;
  };
}

interface TeamListItem {
  id: string;
  name: string;
  observable_count: number;
}

interface ObservableMember {
  id: string;
  email: string;
  display_name?: string;
}

interface UsageCombinedViewProps {
  overview: OverviewData;
  timeSeriesData: TimeSeriesData[];
  agentData: BreakdownItem[];
  modelData: BreakdownItem[];
  userData: BreakdownItem[];
  allUsers?: BreakdownItem[]; // Unfiltered user list for dropdown
  availableTeams?: TeamListItem[]; // Teams with Observable members
  isTeamObserver?: boolean; // Whether user is a team observer
  observabilityMode?: 'individual' | 'team'; // Current observability mode
  observableMembers?: ObservableMember[]; // Observable members for selected team
  selectedObservableMemberId?: string; // Currently selected Observable member
  onObservableMemberChange?: (memberId?: string) => void; // Observable member selection handler
  dateRange: DateRange;
  onDateRangeChange: (range: DateRange) => void;
  startDate?: string;
  endDate?: string;
  startTime?: string;
  endTime?: string;
  onCustomDateChange?: (startDate: string, endDate: string, startTime?: string, endTime?: string) => void;
  userId?: string;
  onUserChange: (userId?: string) => void;
  teamId?: string;
  onTeamChange: (teamId?: string) => void;
  onNavigateToConversations?: (filters: { userId?: string; agentId?: string; model?: string; specificDate?: string }) => void;
  isAdmin?: boolean; // Whether user has admin/developer role
}

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1'];

function formatNumber(num: number): string {
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  } else if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }
  return num.toString();
}

export function UsageCombinedView({
  overview,
  timeSeriesData,
  agentData,
  modelData,
  userData,
  allUsers,
  availableTeams,
  isTeamObserver = false,
  observabilityMode = 'individual',
  observableMembers = [],
  selectedObservableMemberId,
  onObservableMemberChange,
  dateRange,
  onDateRangeChange,
  startDate,
  endDate,
  startTime,
  endTime,
  onCustomDateChange,
  userId,
  onUserChange,
  teamId,
  onTeamChange,
  onNavigateToConversations,
  isAdmin = false
}: UsageCombinedViewProps) {
  const [timeSeriesMetric, setTimeSeriesMetric] = useState<'conversations' | 'messages' | 'tokens'>('conversations');
  const [breakdownType, setBreakdownType] = useState<'agents' | 'models'>('agents');
  const [displayTimezone, setDisplayTimezone] = useState<'local' | 'utc'>('local');
  const [showCustomDatePicker, setShowCustomDatePicker] = useState(false);
  const [tempStartDate, setTempStartDate] = useState('');
  const [tempEndDate, setTempEndDate] = useState('');
  const [tempStartTime, setTempStartTime] = useState('');
  const [tempEndTime, setTempEndTime] = useState('');
  const [isExporting, setIsExporting] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  // Detect user's browser timezone
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const currentBreakdownData = breakdownType === 'agents' ? agentData : modelData;
  const top10Breakdown = currentBreakdownData.slice(0, 10);

  // Transform time series data for display with adaptive formatting
  // Backend returns mixed granularity (day/hour/minute) based on data density
  const chartData = timeSeriesData.map(d => {
    // Parse the full timestamp from backend to preserve actual conversation times
    // Backend returns ISO format with T or space-separated format depending on granularity
    const dateObj = new Date(d.date);

    // Detect granularity by parsing the timestamp
    // Use UTC methods when in UTC mode, local methods when in local mode
    const hours = displayTimezone === 'utc' ? dateObj.getUTCHours() : dateObj.getHours();
    const minutes = displayTimezone === 'utc' ? dateObj.getUTCMinutes() : dateObj.getMinutes();
    const seconds = displayTimezone === 'utc' ? dateObj.getUTCSeconds() : dateObj.getSeconds();

    // Has time if any hour/minute/second is non-zero (not midnight)
    const hasTime = hours !== 0 || minutes !== 0 || seconds !== 0;
    const hasMinute = minutes !== 0 || seconds !== 0;

    // Use dynamic timezone based on user selection
    const tz = displayTimezone === 'utc' ? 'UTC' : browserTimezone;

    // Determine if we're in a narrow time window (within 3 days)
    const daysDiff = timeSeriesData.length > 0
      ? (new Date(timeSeriesData[timeSeriesData.length - 1].date).getTime() - new Date(timeSeriesData[0].date).getTime()) / (1000 * 60 * 60 * 24)
      : 0;
    const isNarrowWindow = daysDiff <= 3;

    // X-axis label: Show date only, unless narrow window with time data
    let xAxisLabel: string;
    if (isNarrowWindow && hasTime) {
      // Narrow window with time: "Jan 1, 3pm" or "Jan 1, 3:45pm"
      if (hasMinute) {
        xAxisLabel = dateObj.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          hour12: true,
          timeZone: tz
        });
      } else {
        xAxisLabel = dateObj.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          hour12: true,
          timeZone: tz
        });
      }
    } else {
      // Default: Just date "Jan 1"
      xAxisLabel = dateObj.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        timeZone: tz
      });
    }

    // Full timestamp for tooltip - always show maximum available detail
    // Get timezone abbreviation for display
    const tzAbbr = displayTimezone === 'utc' ? 'UTC' : dateObj.toLocaleString('en-US', {
      timeZoneName: 'short',
      timeZone: tz
    }).split(' ').pop() || '';

    let fullTimestamp: string;
    if (hasMinute) {
      // Has minute data: "Jan 1, 2025 at 3:45 PM EST"
      fullTimestamp = dateObj.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
        timeZone: tz
      }) + ' ' + tzAbbr;
    } else if (hasTime) {
      // Has hour data: "Jan 1, 2025 at 3 PM EST"
      fullTimestamp = dateObj.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        hour12: true,
        timeZone: tz
      }) + ' ' + tzAbbr;
    } else {
      // Daily data: "Jan 1, 2025"
      fullTimestamp = dateObj.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        timeZone: tz
      });
    }

    return {
      date: xAxisLabel,
      fullDate: fullTimestamp,
      originalDate: d.date, // Keep original ISO timestamp for click handler
      value: timeSeriesMetric === 'conversations' ? d.conversation_count :
             timeSeriesMetric === 'messages' ? d.message_count :
             d.token_count
    };
  });

  // Transform breakdown data for chart - use selected metric
  const breakdownChartData = top10Breakdown.map(item => {
    const conversations = item.value;
    const messages = item.metadata?.messages || 0;
    const tokens = item.metadata?.tokens || 0;

    const displayValue = timeSeriesMetric === 'conversations' ? conversations :
                        timeSeriesMetric === 'messages' ? messages :
                        tokens;

    return {
      name: item.label.length > 80 ? item.label.substring(0, 80) + '...' : item.label,
      fullName: item.label,
      id: item.id, // Keep original ID for click handler
      value: displayValue,
      conversations,
      messages,
      tokens,
      percentage: item.percentage
    };
  });

  // Custom tick component with proper width-based wrapping
  const CustomYAxisTick = ({ x, y, payload }: any) => {
    const maxCharsPerLine = 40; // Increased to use available white space
    const maxLines = 2; // Prevent excessive vertical expansion
    const lineHeight = 12;

    const wrapText = (text: string, maxChars: number, maxLines: number): string[] => {
      if (text.length <= maxChars) return [text];

      const words = text.split(' ');
      const lines: string[] = [];
      let currentLine = '';

      for (const word of words) {
        if (lines.length >= maxLines - 1) {
          // On last line, truncate if needed
          const remaining = maxChars - currentLine.length - 1;
          if (remaining >= 4) { // Space for "..."
            currentLine += (currentLine ? ' ' : '') + word.substring(0, remaining - 3) + '...';
          } else if (!currentLine) {
            currentLine = word.substring(0, maxChars - 3) + '...';
          } else {
            currentLine += '...';
          }
          break;
        }

        const testLine = currentLine ? `${currentLine} ${word}` : word;

        if (testLine.length <= maxChars) {
          currentLine = testLine;
        } else {
          if (currentLine) lines.push(currentLine);
          currentLine = word.length > maxChars ? word.substring(0, maxChars - 3) + '...' : word;
        }
      }

      if (currentLine && lines.length < maxLines) {
        lines.push(currentLine);
      }

      return lines;
    };

    const lines = wrapText(payload.value, maxCharsPerLine, maxLines);

    // Center multi-line text vertically
    const totalHeight = lines.length * lineHeight;
    const yOffset = -(totalHeight / 2 - lineHeight / 2);

    return (
      <g transform={`translate(${x},${y + yOffset})`}>
        {lines.map((line, index) => (
          <text
            key={index}
            x={0}
            y={0}
            dy={index * lineHeight + 4}
            textAnchor="end"
            fill="#6b7280"
            fontSize={11}
          >
            {line}
          </text>
        ))}
      </g>
    );
  };

  const getMetricColor = () => {
    switch (timeSeriesMetric) {
      case 'conversations': return '#10b981';
      case 'messages': return '#3b82f6';
      case 'tokens': return '#f59e0b';
    }
  };

  const getMetricLabel = () => {
    switch (timeSeriesMetric) {
      case 'conversations': return 'Conversations';
      case 'messages': return 'Messages';
      case 'tokens': return 'Tokens';
    }
  };

  const TimeSeriesTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
          <p className="text-sm text-gt-gray-600 mb-1">{payload[0].payload.fullDate}</p>
          <p className="text-sm font-medium" style={{ color: getMetricColor() }}>
            {payload[0].value.toLocaleString()} {timeSeriesMetric}
          </p>
        </div>
      );
    }
    return null;
  };

  const BreakdownTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white border border-gt-gray-200 rounded-lg p-3 shadow-lg">
          <p className="font-medium text-gt-gray-900 mb-2">{data.fullName}</p>
          <p className="text-sm text-gt-gray-600">
            <span className="font-medium text-gt-green">{data.conversations.toLocaleString()}</span> conversations
          </p>
          <p className="text-sm text-gt-gray-600">
            <span className="font-medium text-blue-600">{data.messages.toLocaleString()}</span> messages
          </p>
          <p className="text-sm text-gt-gray-600">
            <span className="font-medium text-orange-500">{data.tokens.toLocaleString()}</span> tokens
          </p>
          <p className="text-sm text-gt-gray-500 mt-1">{data.percentage.toFixed(1)}% of total</p>
        </div>
      );
    }
    return null;
  };

  const handleExportChart = async () => {
    if (!chartRef.current) return;

    setIsExporting(true);
    try {
      // Generate filename based on current view settings
      const dateRangeStr = dateRange === 'custom' && startDate && endDate
        ? `${startDate}_to_${endDate}`
        : dateRange === 'all'
        ? 'all_time'
        : `${dateRange}d`;

      const filename = generateExportFilename(timeSeriesMetric, dateRangeStr);

      await exportChartAsPNG({
        element: chartRef.current,
        filename,
        backgroundColor: '#ffffff',
      });
    } catch (error) {
      console.error('Failed to export chart:', error);
      alert('Failed to export chart. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="bg-white border border-gt-gray-200 rounded-lg p-6">
      {/* Header with Title and Filters */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gt-gray-900 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-gt-green" />
          Usage Overview
        </h3>

        <div className="flex items-center gap-2">
          {/* Individual Mode Filters */}
          {observabilityMode === 'individual' && (
            <>
              {/* User Filter - Show for admin/developer roles only in individual mode */}
              {isAdmin && (
                <div className="flex items-center gap-2 border border-gt-gray-200 rounded-lg px-3 py-1.5">
                  <User className="w-4 h-4 text-gt-gray-500" />
                  <select
                    value={userId || ''}
                    onChange={(e) => onUserChange(e.target.value || undefined)}
                    className="bg-transparent border-none text-sm font-medium text-gt-gray-900 cursor-pointer focus:outline-none"
                  >
                    <option value="">All Users</option>
                    {(allUsers || userData).map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}

          {/* Team Mode Filters */}
          {observabilityMode === 'team' && (
            <>
              {/* Team Filter - Show for team observers */}
              {isTeamObserver && availableTeams && availableTeams.length > 0 && (
                <div className="flex items-center gap-2 border border-green-200 bg-green-50 rounded-lg px-3 py-1.5 min-w-[140px] w-40">
                  <Users2 className="w-4 h-4 text-gt-green flex-shrink-0" />
                  <select
                    value={teamId || ''}
                    onChange={(e) => onTeamChange?.(e.target.value || undefined)}
                    className="bg-transparent border-none text-sm font-medium text-green-900 cursor-pointer focus:outline-none truncate flex-1 min-w-0"
                  >
                    <option value="all">Team</option>
                    {availableTeams.map((team) => (
                      <option key={team.id} value={team.id}>
                        {team.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Team Observability Filter - Always show in team mode */}
              <div className="flex items-center gap-2 border border-green-200 bg-green-50 rounded-lg px-3 py-1.5 min-w-[140px] w-40">
                <User className="w-4 h-4 text-gt-green flex-shrink-0" />
                <select
                  value={selectedObservableMemberId || ''}
                  onChange={(e) => onObservableMemberChange?.(e.target.value || undefined)}
                  disabled={observableMembers.length === 0}
                  className={`bg-transparent border-none text-sm font-medium text-green-900 focus:outline-none truncate flex-1 min-w-0 ${
                    observableMembers.length === 0 ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
                  }`}
                >
                  {observableMembers.length === 0 ? (
                    <option value="">User</option>
                  ) : (
                    <>
                      <option value="">User</option>
                      {observableMembers.map((member) => (
                        <option key={member.id} value={member.id}>
                          {member.display_name || member.email}
                        </option>
                      ))}
                    </>
                  )}
                </select>
              </div>
            </>
          )}

          {/* Date Range Selector - always show dropdown */}
          <div className="flex flex-col gap-2 min-w-[140px] w-40">
            <div className="flex items-center gap-2 border border-gt-gray-200 rounded-lg px-3 py-1.5 overflow-hidden">
              <Calendar className="w-4 h-4 text-gt-gray-500 flex-shrink-0" />
              <select
                value={dateRange}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value === 'custom') {
                    setShowCustomDatePicker(true);
                    setTempStartDate(startDate || '');
                    setTempEndDate(endDate || '');
                    setTempStartTime(startTime || '');
                    setTempEndTime(endTime || '');
                  } else if (value === 'all') {
                    onDateRangeChange('all');
                  } else {
                    onDateRangeChange(parseInt(value) as DateRange);
                  }
                }}
                className="bg-transparent border-none text-sm font-medium text-gt-gray-900 cursor-pointer focus:outline-none flex-1 min-w-0"
              >
                <option value={1}>Last 24 hours</option>
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last year</option>
                <option value="all">All Time</option>
                <option value="custom">Custom Range...</option>
              </select>
            </div>

            {/* Show custom date range as clickable badge when active */}
            {dateRange === 'custom' && startDate && endDate && (
              <button
                onClick={() => {
                  setShowCustomDatePicker(true);
                  setTempStartDate(startDate);
                  setTempEndDate(endDate);
                  setTempStartTime(startTime || '');
                  setTempEndTime(endTime || '');
                }}
                className="text-xs text-gt-gray-600 hover:text-gt-green transition-colors text-left"
              >
                📅 {new Date(startDate + 'T12:00:00').toLocaleDateString()} - {new Date(endDate + 'T12:00:00').toLocaleDateString()}
              </button>
            )}
          </div>

          {/* Custom Date Range Modal */}
          {showCustomDatePicker && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
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
                      if (tempStartDate && tempEndDate && onCustomDateChange) {
                        // Call the combined callback that sets dateRange='custom' + dates + times atomically
                        onCustomDateChange(tempStartDate, tempEndDate, tempStartTime || undefined, tempEndTime || undefined);
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

          {/* Timezone Toggle */}
          <div className="flex items-center gap-1 bg-gt-gray-100 rounded-lg p-1">
            <button
              onClick={() => setDisplayTimezone('local')}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                displayTimezone === 'local'
                  ? 'bg-white text-gt-gray-900 shadow-sm'
                  : 'text-gt-gray-600 hover:text-gt-gray-900'
              }`}
              title={`Show times in your local timezone (${browserTimezone})`}
            >
              Local
            </button>
            <button
              onClick={() => setDisplayTimezone('utc')}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                displayTimezone === 'utc'
                  ? 'bg-white text-gt-gray-900 shadow-sm'
                  : 'text-gt-gray-600 hover:text-gt-gray-900'
              }`}
              title="Show times in UTC"
            >
              UTC
            </button>
          </div>

          {/* Export Button */}
          <button
            onClick={handleExportChart}
            disabled={isExporting}
            className="flex items-center gap-2 px-3 py-1.5 bg-gt-green text-white rounded-lg text-sm font-medium hover:bg-gt-green-dark transition-colors disabled:bg-gt-gray-300 disabled:cursor-not-allowed"
            title="Export chart as PNG"
          >
            <Download className="w-4 h-4" />
            {isExporting ? 'Exporting...' : 'Export Chart'}
          </button>
        </div>
      </div>

      {/* Chart Content Wrapper (for export) */}
      <div ref={chartRef} data-export-target className="bg-white p-4">
        {/* Filter Context Banner (included in export) */}
        <div className="mb-4 pb-3 border-b border-gt-gray-200">
          <div className="flex items-center justify-between text-sm text-gt-gray-600">
            <div className="flex items-center gap-4">
              <span className="font-medium text-gt-gray-900">Usage Overview</span>
              <span>Metric: <span className="font-medium" style={{ color: getMetricColor() }}>{getMetricLabel()}</span></span>
              <span>Date Range: <span className="font-medium">{
                dateRange === 'custom' && startDate && endDate
                  ? `${new Date(startDate + 'T12:00:00').toLocaleDateString()} - ${new Date(endDate + 'T12:00:00').toLocaleDateString()}`
                  : dateRange === 'all'
                  ? 'All Time'
                  : `Last ${dateRange} ${dateRange === 1 ? 'day' : 'days'}`
              }</span></span>
              {userId && <span>User: <span className="font-medium">{userData.find(u => u.id === userId)?.label || 'Unknown'}</span></span>}
            </div>
            <span className="text-xs">Timezone: {displayTimezone === 'utc' ? 'UTC' : browserTimezone}</span>
          </div>
        </div>

        {/* Compact Metrics Readouts */}
        <div className="grid grid-cols-4 gap-4 mb-6 pb-6 border-b border-gt-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <MessageSquare className="w-5 h-5 text-gt-green" />
          </div>
          <div>
            <p className="text-xs text-gt-gray-600">Total Conversations</p>
            <p className="text-xl font-bold text-gt-gray-900">{formatNumber(overview.total_conversations)}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-xs text-gt-gray-600">Total Messages</p>
            <p className="text-xl font-bold text-gt-gray-900">{formatNumber(overview.total_messages)}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-orange-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <Zap className="w-5 h-5 text-orange-500" />
          </div>
          <div>
            <p className="text-xs text-gt-gray-600">Tokens Consumed</p>
            <p className="text-xl font-bold text-gt-gray-900">{formatNumber(overview.total_tokens)}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <UsersIcon className="w-5 h-5 text-gt-green" />
          </div>
          <div>
            <p className="text-xs text-gt-gray-600">Active Users</p>
            <p className="text-xl font-bold text-gt-gray-900">{formatNumber(overview.unique_users)}</p>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {/* Time Series Chart - Full Width */}
        <div>
          {/* Metric Toggle */}
          <div className="flex items-center gap-2 mb-4">
            <button
              onClick={() => setTimeSeriesMetric('conversations')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                timeSeriesMetric === 'conversations'
                  ? 'bg-gt-green text-white'
                  : 'bg-gt-gray-100 text-gt-gray-600 hover:bg-gt-gray-200'
              }`}
            >
              Conversations
            </button>
            <button
              onClick={() => setTimeSeriesMetric('messages')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                timeSeriesMetric === 'messages'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gt-gray-100 text-gt-gray-600 hover:bg-gt-gray-200'
              }`}
            >
              Messages
            </button>
            <button
              onClick={() => setTimeSeriesMetric('tokens')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                timeSeriesMetric === 'tokens'
                  ? 'bg-orange-500 text-white'
                  : 'bg-gt-gray-100 text-gt-gray-600 hover:bg-gt-gray-200'
              }`}
            >
              Tokens
            </button>
          </div>

          {/* Time Series Chart */}
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={getMetricColor()} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={getMetricColor()} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 12 }} />
                <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} domain={[0, 'auto']} />
                <Tooltip content={<TimeSeriesTooltip />} />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={getMetricColor()}
                  strokeWidth={2}
                  fill="url(#colorValue)"
                  onClick={(data: any) => {
                    if (onNavigateToConversations && data?.payload?.originalDate) {
                      onNavigateToConversations({
                        specificDate: data.payload.originalDate,
                        userId: userId // Preserve current user filter
                      });
                    }
                  }}
                  cursor="pointer"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-gt-gray-500">
              <p>No time series data available</p>
            </div>
          )}
        </div>

        {/* Agent/Model Breakdown - Below Time Series */}
        <div>
          {/* Breakdown Toggle with Metric Label */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setBreakdownType('agents')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1 ${
                  breakdownType === 'agents'
                    ? 'bg-gt-green text-white'
                    : 'bg-gt-gray-100 text-gt-gray-600 hover:bg-gt-gray-200'
                }`}
              >
                <Bot className="w-4 h-4" />
                Agents
              </button>
              <button
                onClick={() => setBreakdownType('models')}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1 ${
                  breakdownType === 'models'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gt-gray-100 text-gt-gray-600 hover:bg-gt-gray-200'
                }`}
              >
                <Cpu className="w-4 h-4" />
                Models
              </button>
            </div>
            <span className="text-sm text-gt-gray-500">
              Showing: <span className="font-medium" style={{ color: getMetricColor() }}>{getMetricLabel()}</span>
            </span>
          </div>

          {/* Breakdown Chart */}
          {breakdownChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={Math.max(200, breakdownChartData.length * 40 + 40)}>
              <BarChart
                data={breakdownChartData}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 137, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="fullName"
                  stroke="#6b7280"
                  width={133}
                  tick={<CustomYAxisTick />}
                  interval={0}
                />
                <Tooltip content={<BreakdownTooltip />} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {breakdownChartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                      onClick={() => {
                        if (onNavigateToConversations && entry.id) {
                          if (breakdownType === 'agents') {
                            onNavigateToConversations({ agentId: entry.id, userId });
                          } else {
                            // Model name is stored in the id field for models
                            onNavigateToConversations({ model: entry.id, userId });
                          }
                        }
                      }}
                      cursor="pointer"
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-gt-gray-500">
              <p>No {breakdownType} data available</p>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
