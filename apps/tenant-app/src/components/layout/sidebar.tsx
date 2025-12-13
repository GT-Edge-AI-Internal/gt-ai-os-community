'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ConversationHistorySidebar } from '@/components/chat/conversation-history-sidebar';
import {
  MessageCircle,
  X,
  Bot,
  Brain,
  Globe,
  Database,
  Menu,
  LogOut,
  ChevronLeft,
  ChevronRight,
  History,
  Search,
  MoreHorizontal,
  Clock,
  Filter,
  BarChart3,
  Users,
  Moon,
  Sun
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { VersionDisplay } from '@/components/ui/version-display';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { User } from '@/types';
import { useAuthStore } from '@/stores/auth-store';
import { useChatStore } from '@/stores/chat-store';
import { getInitials } from '@/lib/utils';
import { getAuthToken, getTenantInfo } from '@/services/auth';
import { getUserRole } from '@/lib/permissions';
import { useTheme } from '@/providers/theme-provider';

interface SidebarProps {
  user: User | null;
  onCollapseChange?: (collapsed: boolean) => void;
  onSelectConversation?: (conversationId: string) => void;
}

export function Sidebar({ user, onCollapseChange, onSelectConversation }: SidebarProps) {
  const pathname = usePathname();
  const { logout } = useAuthStore();
  const { unreadCounts } = useChatStore();
  const { theme, toggleTheme } = useTheme();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [tenantInfo, setTenantInfo] = useState<{name: string; domain: string} | null>(null);
  const [availableAgents, setAvailableAgents] = useState<{id: string, name: string}[]>([]);
  const [isCollapsed, setIsCollapsed] = useState(() => {
    // Load saved state from localStorage on initial render
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('gt-sidebar-collapsed');
      return saved ? JSON.parse(saved) : false;
    }
    return false;
  });
  
  // Track if user has ever interacted with the sidebar
  const [hasUserInteracted, setHasUserInteracted] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('gt-sidebar-collapsed') !== null;
    }
    return false;
  });
  const [showPulse, setShowPulse] = useState(false);
  const [isTabHovered, setIsTabHovered] = useState(false);
  const [isNarrowScreen, setIsNarrowScreen] = useState(false);
  const [userManuallyExpanded, setUserManuallyExpanded] = useState(false);

  // Fetch tenant display name from control panel (via Next.js API route)
  // Cache in sessionStorage to persist across navigation
  useEffect(() => {
    const fetchTenantDisplayName = async () => {
      if (typeof window === 'undefined') return;

      try {
        const localTenantInfo = getTenantInfo();
        if (!localTenantInfo) return;

        // Check if we have cached tenant display name in sessionStorage
        const cachedTenantName = sessionStorage.getItem('gt2_tenant_display_name');
        if (cachedTenantName) {
          // Use cached value immediately
          setTenantInfo({
            domain: localTenantInfo.domain,
            name: cachedTenantName,
            id: localTenantInfo.id
          });
          return;
        }

        // Fetch tenant display name via Next.js API route (avoids CORS)
        const response = await fetch('/api/tenant-info');

        if (response.ok) {
          const data = await response.json();
          const displayName = data.name || localTenantInfo.name;

          // Cache the display name in sessionStorage
          sessionStorage.setItem('gt2_tenant_display_name', displayName);

          // Update with correct display name from control panel
          setTenantInfo({
            domain: localTenantInfo.domain,
            name: displayName,
            id: localTenantInfo.id
          });
        } else {
          // If API fails, use localStorage value
          setTenantInfo(localTenantInfo);
        }
      } catch (error) {
        console.error('Failed to fetch tenant display name:', error);
        // On error, use localStorage value
        const tenant = getTenantInfo();
        if (tenant) {
          setTenantInfo(tenant);
        }
      }
    };

    fetchTenantDisplayName();
  }, []);

  // Check screen width and auto-collapse on narrow screens
  useEffect(() => {
    const checkScreenWidth = () => {
      const screenWidth = window.innerWidth;
      const sidebarWidth = 320; // w-80 = 320px
      const minMainContentWidth = 400; // Minimum space needed for main content
      const collisionPoint = sidebarWidth + minMainContentWidth; // 720px

      const isNarrow = screenWidth < 1024; // lg breakpoint
      const isVeryNarrow = screenWidth < 768; // md breakpoint
      const wouldOverlap = screenWidth < collisionPoint; // Hard boundary at 720px

      setIsNarrowScreen(isNarrow);

      // Auto-collapse on narrow screens if user has never interacted with the sidebar
      if (isNarrow && !isCollapsed && !hasUserInteracted) {
        setIsCollapsed(true);
      }

      // Force collapse on very narrow screens regardless of user interaction
      if (isVeryNarrow && !isCollapsed) {
        setIsCollapsed(true);
        setUserManuallyExpanded(false); // Reset manual override on very narrow screens
      }

      // HARD BOUNDARY: Force collapse when sidebar would overlap main content
      if (wouldOverlap && !isCollapsed) {
        setIsCollapsed(true);
        setUserManuallyExpanded(false); // Reset manual override when hitting boundary
      }

      // Reset manual override when going back to wide screen
      if (!isNarrow) {
        setUserManuallyExpanded(false);
      }
    };

    if (typeof window !== 'undefined') {
      // Only run checkScreenWidth on mount and resize, not on every render
      checkScreenWidth();
      window.addEventListener('resize', checkScreenWidth);
      return () => window.removeEventListener('resize', checkScreenWidth);
    }
  }, []); // Remove dependencies to prevent running on state changes

  // Helper to check if any navigation page is active
  const isNavActive = ['/chat', '/agents', '/datasets', '/teams', '/observability'].some(path =>
    pathname === path || pathname.startsWith(path + '/')
  );
  
  // Profile menu is no longer used for navigation, only for sign out

  // Save collapse state to localStorage whenever it changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('gt-sidebar-collapsed', JSON.stringify(isCollapsed));
      onCollapseChange?.(isCollapsed);
    }
  }, [isCollapsed, onCollapseChange]);

  // Load user's available agents - ONLY on chat page for performance
  useEffect(() => {
    const loadUserAgents = async () => {
      try {
        const token = getAuthToken();
        if (!token) return;

        // Use lightweight minimal endpoint for better performance
        const response = await fetch('/api/v1/agents/minimal', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const agents = await response.json();
          console.log('🤖 Loaded minimal agents for filtering:', agents);
          setAvailableAgents(agents);
        }
      } catch (error) {
        console.error('Error loading user agents:', error);
      }
    };

    // Load agents once on first mount, cache for entire session
    // No pathname check - agents needed for filter dropdown on all pages
    if (availableAgents.length === 0) {
      loadUserAgents();
    }
  }, [availableAgents.length]);

  const handleCollapseToggle = () => {
    setShowPulse(true);
    const newCollapsedState = !isCollapsed;
    const screenWidth = window.innerWidth;
    const sidebarWidth = 320; // w-80 = 320px
    const minMainContentWidth = 400; // Minimum space needed for main content
    const collisionPoint = sidebarWidth + minMainContentWidth; // 720px

    const isVeryNarrow = screenWidth < 768; // md breakpoint
    const wouldOverlap = screenWidth < collisionPoint; // Hard boundary

    // Prevent expansion on very narrow screens
    if (!newCollapsedState && isVeryNarrow) {
      setTimeout(() => setShowPulse(false), 300);
      return; // Don't expand on very narrow screens
    }

    // HARD BOUNDARY: Prevent expansion when it would overlap main content
    if (!newCollapsedState && wouldOverlap) {
      setTimeout(() => setShowPulse(false), 300);
      return; // Don't expand when it would cause overlap
    }

    setIsCollapsed(newCollapsedState);
    setIsTabHovered(false); // Reset hover state when toggling
    setHasUserInteracted(true); // Mark that user has interacted with sidebar

    // If user is expanding on a narrow screen, mark as manual override
    if (!newCollapsedState && isNarrowScreen && !isVeryNarrow && !wouldOverlap) {
      setUserManuallyExpanded(true);
    }

    setTimeout(() => setShowPulse(false), 300);
  };

  return (
    <div className={cn(
      "relative h-full transition-all duration-700 ease-out",
      isCollapsed ? "w-16" : "w-80"
    )}>
      {/* Collapsed Menu - Always visible when collapsed */}
      <div className={cn(
        "absolute top-4 left-0 bottom-4 z-50 flex flex-col items-center justify-start transition-all duration-300 ease-out",
        isCollapsed ? "w-16 opacity-100 translate-x-0 delay-300" : "w-16 opacity-0 translate-x-0 pointer-events-none delay-0"
      )}>
        {/* Logo with Expand Arrow */}
        <div
          className={cn(
            "cursor-pointer p-2 rounded-xl transition-all duration-200 backdrop-blur-md border",
            isTabHovered
              ? "shadow-md"
              : ""
          )}
          style={{
            backgroundColor: isTabHovered ? 'rgba(255, 255, 255, 0.7)' : 'var(--gt-gray-100)',
            borderColor: isTabHovered ? 'rgba(255, 255, 255, 0.6)' : 'var(--gt-gray-200)'
          }}
          onMouseEnter={() => setIsTabHovered(true)}
          onMouseLeave={() => setIsTabHovered(false)}
          onClick={handleCollapseToggle}
        >
            <div className="relative flex items-center justify-center min-w-5 h-5">
              {/* GT Logo */}
              <Image
                src="/gt-small-logo.png"
                alt="GT Logo"
                width={35}
                height={21}
                className={cn(
                  "w-8 h-auto transition-all duration-300",
                  isTabHovered ? "opacity-40" : "opacity-90"
                )}
                priority
              />
              
              {/* Arrow Reveal Overlay */}
              <div className={cn(
                "absolute inset-0 flex items-center justify-center transition-all duration-300",
                isTabHovered ? "opacity-100" : "opacity-0"
              )}>
                <ChevronRight className={cn(
                  "w-4 h-4 transition-all duration-300",
                  showPulse && "text-gt-green"
                )} style={{ color: showPulse ? 'var(--gt-green)' : 'var(--gt-gray-900)' }} />
              </div>
            </div>
          </div>

          {/* Main Navigation Icons */}
          <div className="flex flex-col space-y-2 mt-4">
            <Link
              href="/agents"
              className={cn(
                "p-2 rounded-xl transition-all duration-200 backdrop-blur-md border",
                pathname === '/agents' && "shadow-md"
              )}
              style={{
                backgroundColor: pathname === '/agents' ? 'rgba(0, 208, 132, 0.2)' : 'var(--gt-gray-100)',
                borderColor: pathname === '/agents' ? 'rgba(0, 208, 132, 0.4)' : 'var(--gt-gray-200)'
              }}
            >
              <Bot className="w-5 h-5 transition-colors" style={{ color: pathname === '/agents' ? 'var(--gt-green)' : 'var(--gt-gray-700)' }} />
            </Link>

            <Link
              href="/datasets"
              className={cn(
                "p-2 rounded-xl transition-all duration-200 backdrop-blur-md border",
                pathname === '/datasets' && "shadow-md"
              )}
              style={{
                backgroundColor: pathname === '/datasets' ? 'rgba(0, 208, 132, 0.2)' : 'var(--gt-gray-100)',
                borderColor: pathname === '/datasets' ? 'rgba(0, 208, 132, 0.4)' : 'var(--gt-gray-200)'
              }}
            >
              <Database className="w-5 h-5 transition-colors" style={{ color: pathname === '/datasets' ? 'var(--gt-green)' : 'var(--gt-gray-700)' }} />
            </Link>

            <Link
              href="/teams"
              className={cn(
                "p-2 rounded-xl transition-all duration-200 backdrop-blur-md border",
                pathname === '/teams' && "shadow-md"
              )}
              style={{
                backgroundColor: pathname === '/teams' ? 'rgba(0, 208, 132, 0.2)' : 'var(--gt-gray-100)',
                borderColor: pathname === '/teams' ? 'rgba(0, 208, 132, 0.4)' : 'var(--gt-gray-200)'
              }}
            >
              <Users className="w-5 h-5 transition-colors" style={{ color: pathname === '/teams' ? 'var(--gt-green)' : 'var(--gt-gray-700)' }} />
            </Link>

            {/* Observability - All Users */}
            <Link
              href="/observability"
              className={cn(
                "p-2 rounded-xl transition-all duration-200 backdrop-blur-md border",
                pathname === '/observability' && "shadow-md"
              )}
              style={{
                backgroundColor: pathname === '/observability' ? 'rgba(0, 208, 132, 0.2)' : 'var(--gt-gray-100)',
                borderColor: pathname === '/observability' ? 'rgba(0, 208, 132, 0.4)' : 'var(--gt-gray-200)'
              }}
            >
              <BarChart3 className="w-5 h-5 transition-colors" style={{ color: pathname === '/observability' ? 'var(--gt-green)' : 'var(--gt-gray-700)' }} />
            </Link>
          </div>

          {/* Conversation History Icon (when collapsed) */}
          <div className="flex-1">
            <div className="mt-4 flex justify-center">
              <button
                onClick={() => {
                  const screenWidth = window.innerWidth;
                  const sidebarWidth = 320; // w-80 = 320px
                  const minMainContentWidth = 400; // Minimum space needed for main content
                  const collisionPoint = sidebarWidth + minMainContentWidth; // 720px

                  const isVeryNarrow = screenWidth < 768; // md breakpoint
                  const wouldOverlap = screenWidth < collisionPoint; // Hard boundary

                  // Only expand if it won't cause overlap
                  if (!isVeryNarrow && !wouldOverlap) {
                    setIsCollapsed(false);
                    setUserManuallyExpanded(true);
                  }
                }}
                className="p-2 rounded-xl transition-all duration-200 backdrop-blur-md border cursor-pointer"
                style={{
                  backgroundColor: 'var(--gt-gray-100)',
                  borderColor: 'var(--gt-gray-200)'
                }}
              >
                <History className="w-5 h-5" style={{ color: 'var(--gt-gray-700)' }} />
              </button>
            </div>
          </div>


          {/* Profile Icon */}
          <div className="mt-4">
            <div
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="p-2 rounded-xl transition-all duration-200 backdrop-blur-md border relative cursor-pointer"
              style={{
                backgroundColor: 'var(--gt-gray-100)',
                borderColor: 'var(--gt-gray-200)'
              }}
            >
              <div className="w-6 h-6 bg-gt-green rounded-full flex items-center justify-center text-white text-xs font-medium">
                {user ? getInitials(user.full_name || user.email || '') : '?'}
              </div>

              {/* User Menu Dropdown for collapsed state */}
              {showUserMenu && (
                <div className="absolute left-full bottom-0 ml-2 rounded-lg shadow-lg border py-1 z-50 min-w-48" style={{ backgroundColor: 'var(--gt-white)', borderColor: 'var(--gt-gray-200)' }}>
                  <button
                    className="w-full px-4 py-2 text-left text-sm flex items-center space-x-3"
                    style={{ color: 'var(--gt-gray-700)' }}
                    onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--gt-gray-50)'}
                    onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={toggleTheme}
                  >
                    {theme === 'dark' ? (
                      <>
                        <Sun className="w-4 h-4" />
                        <span>Light mode</span>
                      </>
                    ) : (
                      <>
                        <Moon className="w-4 h-4" />
                        <span>Dark mode</span>
                      </>
                    )}
                  </button>
                  <button
                    className="w-full px-4 py-2 text-left text-sm flex items-center space-x-3"
                    style={{ color: '#dc2626' }}
                    onMouseOver={(e: React.MouseEvent<HTMLButtonElement>) => e.currentTarget.style.backgroundColor = '#fef2f2'}
                    onMouseOut={(e: React.MouseEvent<HTMLButtonElement>) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => {
                      logout();
                      setShowUserMenu(false);
                    }}
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

      {/* Full Sidebar - Same interface for all screen sizes */}
      <div
        className={cn(
          'absolute top-0 left-0 bottom-0 w-80 z-40 transform transition-all duration-500 ease-out flex flex-col overflow-hidden',
          isCollapsed ? 'opacity-0 -translate-x-full pointer-events-none delay-0' : 'opacity-100 translate-x-0 delay-200'
        )}
        style={{
          background: `linear-gradient(to right, var(--gt-white) 90%, var(--gt-gray-100))`
        }}
      >
        {/* Header - Unified interface for all screen sizes */}
        <div className="flex items-center p-4 relative">
          <div className="flex items-center space-x-3">
            <a href="https://gtedge.ai" target="_blank" rel="noopener noreferrer">
              <Image
                src="/gtedgeai-green-logo.jpeg"
                alt="GT Edge AI Logo"
                width={1536}
                height={462}
                className="h-20 w-auto cursor-pointer hover:opacity-80 transition-opacity"
                priority
              />
            </a>
          </div>
          
          {/* Collapse arrow - always visible on all screen sizes */}
          <button
            onClick={handleCollapseToggle}
            className={cn(
              "absolute right-7 p-2 rounded-lg transition-all duration-200",
              showPulse ? "bg-gt-green animate-pulse" : "hover:bg-gt-gray-200"
            )}
          >
            <ChevronLeft className="w-4 h-4 text-black transform transition-transform duration-200" />
          </button>
        </div>

        {/* Tenant Name - Above Navigation */}
        {tenantInfo && (
          <div className="px-4 pb-2 flex justify-center">
            <div className="px-4 py-2 rounded-lg border" style={{ backgroundColor: 'var(--gt-gray-100)', borderColor: 'var(--gt-gray-200)' }}>
              <p className="text-base font-semibold text-center break-words max-w-full" style={{ color: 'var(--gt-gray-800)' }}>
                {tenantInfo.name}
              </p>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="px-4 pb-4">
          <div className={cn(
            "p-3 rounded-lg transition-colors duration-200 border border-gt-gray-300",
            isNavActive ? "bg-gt-green/10" : "bg-gt-gray-800"
          )}>
            <nav className="space-y-1">
              <Link
                href="/agents"
                className={cn(
                  "flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors",
                  pathname === '/agents'
                    ? "bg-gt-green text-white"
                    : isNavActive
                      ? "text-gt-gray-800 hover:bg-gt-green/20"
                      : "text-white hover:bg-gt-gray-700"
                )}
              >
                <Bot className="w-4 h-4" />
                <span>Agents</span>
              </Link>
              <Link
                href="/datasets"
                className={cn(
                  "flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors",
                  pathname === '/datasets'
                    ? "bg-gt-green text-white"
                    : isNavActive
                      ? "text-gt-gray-800 hover:bg-gt-green/20"
                      : "text-white hover:bg-gt-gray-700"
                )}
              >
                <Database className="w-4 h-4" />
                <span>Datasets</span>
              </Link>
              <Link
                href="/teams"
                className={cn(
                  "flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors",
                  pathname === '/teams'
                    ? "bg-gt-green text-white"
                    : isNavActive
                      ? "text-gt-gray-800 hover:bg-gt-green/20"
                      : "text-white hover:bg-gt-gray-700"
                )}
              >
                <Users className="w-4 h-4" />
                <span>Teams</span>
              </Link>
              {/* Observability - All Users */}
              <Link
                href="/observability"
                className={cn(
                  "flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors",
                  pathname === '/observability'
                    ? "bg-gt-green text-white"
                    : isNavActive
                      ? "text-gt-gray-800 hover:bg-gt-green/20"
                      : "text-white hover:bg-gt-gray-700"
                )}
              >
                <BarChart3 className="w-4 h-4" />
                <span>Observability</span>
              </Link>
            {/* AI Literacy and Services hidden for MVP - will be redesigned later */}
            {/* <Link
              href="/games"
              onClick={onClose}
              className={cn(
                "flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors",
                pathname === '/games' 
                  ? "bg-gt-green/10 text-gt-green" 
                  : "text-gt-gray-700 hover:bg-gt-gray-50"
              )}
            >
              <Brain className="w-4 h-4" />
              <span>AI Literacy</span>
            </Link>
            <Link
              href="/services"
              onClick={onClose}
              className={cn(
                "flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors",
                pathname === '/services' 
                  ? "bg-gt-green/10 text-gt-green" 
                  : "text-gt-gray-700 hover:bg-gt-gray-50"
              )}
            >
              <Globe className="w-4 h-4" />
              <span>Services</span>
            </Link> */}
            </nav>
          </div>
        </div>

        {/* Conversation History (All pages) */}
        <div className="flex-1 px-4 pb-4 min-h-0">
          <div
            className="h-full max-h-full p-3 rounded-lg transition-colors duration-200 border flex flex-col overflow-hidden"
            style={{ backgroundColor: 'var(--gt-gray-50)', borderColor: 'var(--gt-gray-200)' }}
          >
            {/* Navigation Header */}
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <div className="flex items-center space-x-2">
                <History className="w-4 h-4" style={{ color: 'var(--gt-gray-700)' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--gt-gray-800)' }}>Conversations</span>
                <span className="text-xs ml-2" style={{ color: 'var(--gt-gray-500)' }} id="conversation-count">
                  {/* Count will be updated by conversation component */}
                </span>
                {/* Green pulse indicator when there are unread messages */}
                {Object.keys(unreadCounts).length > 0 && (
                  <div className="flex items-center gap-1 ml-1">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
                    <span className="text-xs text-green-500 font-semibold">
                      {Object.values(unreadCounts).reduce((sum, count) => sum + count, 0)}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex items-center space-x-1">
                {/* Time Filter Dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="p-1 h-6 w-6 text-gt-gray-600 hover:text-gt-gray-800"
                      title="Filter by time"
                    >
                      <Clock className="w-3 h-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-32 z-50 bg-gt-white border border-gray-200 shadow-lg">
                    <DropdownMenuItem onClick={() => window.dispatchEvent(new CustomEvent('filterTime', { detail: 'all' }))}>
                      All Time
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => window.dispatchEvent(new CustomEvent('filterTime', { detail: 'today' }))}>
                      Today
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => window.dispatchEvent(new CustomEvent('filterTime', { detail: 'week' }))}>
                      This Week
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => window.dispatchEvent(new CustomEvent('filterTime', { detail: 'month' }))}>
                      This Month
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Agent Filter Dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="p-1 h-6 w-6 text-gt-gray-600 hover:text-gt-gray-800"
                      title="Filter by agent"
                    >
                      <Filter className="w-3 h-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-40 z-50 bg-gt-white border border-gray-200 shadow-lg max-h-[300px] overflow-y-auto">
                    <DropdownMenuItem onClick={() => window.dispatchEvent(new CustomEvent('filterAgent', { detail: 'all' }))}>
                      All Agents
                    </DropdownMenuItem>
                    {availableAgents.map(agent => (
                      <DropdownMenuItem
                        key={agent.id}
                        onClick={() => window.dispatchEvent(new CustomEvent('filterAgent', { detail: agent.id }))}
                      >
                        {agent.name}
                      </DropdownMenuItem>
                    ))}
                    {availableAgents.length === 0 && (
                      <DropdownMenuItem disabled>
                        No agents found
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Conversation History Content */}
            <div className="flex-1 min-h-0 overflow-hidden">
              <ConversationHistorySidebar
                onSelectConversation={onSelectConversation || ((conversationId) => {
                  // Fallback: Navigate to chat page and load conversation
                  window.location.href = `/chat?conversation=${conversationId}`;
                })}
                currentConversationId={undefined}
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4">
          {/* User Profile Section */}
          <div className="mt-4">
            <div className="relative">
              <div
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="w-full flex items-center space-x-3 px-3 py-2 text-sm rounded-lg transition-colors cursor-pointer border"
                style={{ backgroundColor: 'var(--gt-gray-100)', borderColor: 'var(--gt-gray-200)' }}
                onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--gt-gray-200)'}
                onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'var(--gt-gray-100)'}
              >
                  <div className="w-8 h-8 bg-gt-green rounded-full flex items-center justify-center text-white text-sm font-medium">
                    {user ? getInitials(user.full_name || user.email || '') : '?'}
                  </div>
                  <div className="flex-1 text-left">
                    <p className="font-medium" style={{ color: 'var(--gt-gray-900)' }}>
                      {user?.full_name || 'Unknown User'}
                    </p>
                    <p className="text-xs capitalize" style={{ color: 'var(--gt-gray-600)' }}>
                      {user?.user_type?.replace('_', ' ') || 'User'}
                    </p>
                  </div>
                </div>

                {/* User Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute bottom-full left-0 right-0 mb-2 rounded-lg shadow-lg border py-1 z-50" style={{ backgroundColor: 'var(--gt-white)', borderColor: 'var(--gt-gray-200)' }}>
                  <button
                    className="w-full px-4 py-2 text-left text-sm flex items-center space-x-3"
                    style={{ color: 'var(--gt-gray-700)' }}
                    onMouseOver={(e: React.MouseEvent<HTMLButtonElement>) => e.currentTarget.style.backgroundColor = 'var(--gt-gray-50)'}
                    onMouseOut={(e: React.MouseEvent<HTMLButtonElement>) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={toggleTheme}
                  >
                    {theme === 'dark' ? (
                      <>
                        <Sun className="w-4 h-4" />
                        <span>Light mode</span>
                      </>
                    ) : (
                      <>
                        <Moon className="w-4 h-4" />
                        <span>Dark mode</span>
                      </>
                    )}
                  </button>
                  <button
                    className="w-full px-4 py-2 text-left text-sm flex items-center space-x-3"
                    style={{ color: '#dc2626' }}
                    onMouseOver={(e: React.MouseEvent<HTMLButtonElement>) => e.currentTarget.style.backgroundColor = '#fef2f2'}
                    onMouseOut={(e: React.MouseEvent<HTMLButtonElement>) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => {
                      logout();
                      setShowUserMenu(false);
                    }}
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Version Info */}
          <div className="mt-4 pt-4 border-t border-gt-gray-200">
            <div className="text-center">
              <p className="text-xs text-gt-gray-500">
                GT AI OS Community | v2.0.33
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Overlay for user menu */}
      {showUserMenu && (
        <div 
          className="fixed inset-0 z-30" 
          onClick={() => setShowUserMenu(false)}
        />
      )}
    </div>
  );
}