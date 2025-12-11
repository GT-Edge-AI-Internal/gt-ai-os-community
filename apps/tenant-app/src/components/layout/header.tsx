'use client';

import { useState } from 'react';
import { User } from '@/types';
import { useAuthStore } from '@/stores/auth-store';
import { useChatStore } from '@/stores/chat-store';
import { Button } from '@/components/ui/button';
import { getInitials, cn } from '@/lib/utils';
import { 
  Menu, 
  Plus, 
  MessageSquare, 
  User as UserIcon, 
  Settings, 
  LogOut,
  Wifi,
  WifiOff
} from 'lucide-react';

interface HeaderProps {
  user: User | null;
  onMenuClick: () => void;
}

export function Header({ user, onMenuClick }: HeaderProps) {
  const { logout } = useAuthStore();
  const { connected, createConversation } = useChatStore();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleNewConversation = async () => {
    await createConversation();
  };

  const handleLogout = () => {
    logout();
    setShowUserMenu(false);
  };

  return (
    <header className="bg-gt-white border-b border-gt-gray-200 px-4 py-3">
      <div className="flex items-center justify-between">
        {/* Left Section */}
        <div className="flex items-center space-x-4">
          {/* Mobile Menu Button */}
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-lg hover:bg-gt-gray-100 transition-colors"
          >
            <Menu className="w-5 h-5 text-gt-gray-600" />
          </button>
        </div>

        {/* Center Section - Removed connection status and new chat */}
        <div className="flex items-center space-x-3">
          {/* Empty for now - removed disconnected status and new chat button */}
        </div>

        {/* Right Section */}
        <div className="flex items-center space-x-3">
          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gt-gray-100 transition-colors"
            >
              <div className="w-8 h-8 bg-gt-green rounded-full flex items-center justify-center text-white text-sm font-medium">
                {user ? getInitials(user.full_name || user.email || '') : '?'}
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-sm font-medium text-gt-gray-900">
                  {user?.full_name || 'Unknown User'}
                </p>
                <p className="text-xs text-gt-gray-500 capitalize">
                  {user?.user_type?.replace('_', ' ') || 'User'}
                </p>
              </div>
            </button>

            {/* User Dropdown Menu */}
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gt-gray-200 py-1 z-50">
                {/* User Info */}
                <div className="px-4 py-3 border-b border-gt-gray-100">
                  <p className="text-sm font-medium text-gt-gray-900">
                    {user?.full_name}
                  </p>
                  <p className="text-xs text-gt-gray-500">
                    {user?.email}
                  </p>
                </div>

                {/* Menu Items */}
                <div className="py-1">
                  <button
                    className="w-full px-4 py-2 text-left text-sm text-gt-gray-700 hover:bg-gt-gray-50 flex items-center space-x-3"
                    onClick={() => setShowUserMenu(false)}
                  >
                    <UserIcon className="w-4 h-4" />
                    <span>Profile</span>
                  </button>

                  <button
                    className="w-full px-4 py-2 text-left text-sm text-gt-gray-700 hover:bg-gt-gray-50 flex items-center space-x-3"
                    onClick={() => setShowUserMenu(false)}
                  >
                    <Settings className="w-4 h-4" />
                    <span>Settings</span>
                  </button>

                  <div className="border-t border-gt-gray-100 my-1"></div>

                  <button
                    className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-3"
                    onClick={handleLogout}
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

{/* Mobile New Chat Button - Removed */}

      {/* Overlay for user menu */}
      {showUserMenu && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setShowUserMenu(false)}
        />
      )}
    </header>
  );
}