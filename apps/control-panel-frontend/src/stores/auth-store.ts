import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '@/lib/api';
import toast from 'react-hot-toast';

// Local User type definition
interface User {
  id: number;
  email: string;
  full_name: string;
  user_type: string;
  tenant_id?: number;
  capabilities?: any[];
  created_at?: string;
  updated_at?: string;
  tfa_setup_pending?: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  requiresTfa: boolean;
  tfaConfigured: boolean;
}

interface AuthActions {
  login: (email: string, password: string) => Promise<{ success: boolean; requiresTfa?: boolean }>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  changePassword: (currentPassword: string, newPassword: string) => Promise<boolean>;
  completeTfaLogin: (token: string, user: User) => void;
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set, get) => ({
      // State
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      requiresTfa: false,
      tfaConfigured: false,

      // Actions
      login: async (email: string, password: string) => {
        try {
          set({ isLoading: true });

          const response = await authApi.login(email, password);
          console.log('Login response:', response.data);

          const data = response.data;

          // Check if TFA is required
          if (data.requires_tfa === true) {
            console.log('TFA required, configured:', data.tfa_configured);

            // Validate super_admin role BEFORE allowing TFA flow
            if (data.user_type !== 'super_admin') {
              set({ isLoading: false });
              toast.error('Control Panel access requires super admin privileges');
              return { success: false, requiresTfa: false };
            }

            set({
              requiresTfa: true,
              tfaConfigured: data.tfa_configured,
              isLoading: false,
              isAuthenticated: false,
            });

            return { success: true, requiresTfa: true };
          }

          // Normal login without TFA
          const { access_token, user } = data;

          // Validate super_admin role for Control Panel access
          if (user.user_type !== 'super_admin') {
            set({ isLoading: false });
            toast.error('Control Panel access requires super admin privileges');
            return { success: false, requiresTfa: false };
          }

          set({
            user,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
            requiresTfa: false,
            tfaConfigured: false,
          });

          toast.success(`Welcome back, ${user.full_name}!`);
          return { success: true, requiresTfa: false };

        } catch (error: any) {
          console.error('Login error:', error);
          set({ isLoading: false });

          const message = error.response?.data?.error?.message || 'Login failed';
          toast.error(message);

          return { success: false };
        }
      },

      completeTfaLogin: (token: string, user: User) => {
        // Validate super_admin role for Control Panel access
        if (user.user_type !== 'super_admin') {
          set({ isLoading: false });
          toast.error('Control Panel access requires super admin privileges');
          return;
        }

        set({
          user,
          token,
          isAuthenticated: true,
          requiresTfa: false,
          tfaConfigured: false,
          isLoading: false,
        });
        toast.success(`Welcome back, ${user.full_name}!`);
      },

      logout: () => {
        try {
          // Call logout endpoint (fire and forget)
          authApi.logout().catch(() => {
            // Ignore errors on logout
          });
        } catch {
          // Ignore errors
        }

        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
          requiresTfa: false,
          tfaConfigured: false,
        });

        toast.success('Logged out successfully');
      },

      checkAuth: async () => {
        const { token } = get();
        console.log('CheckAuth called with token:', token ? 'exists' : 'none');
        
        if (!token) {
          console.log('No token, setting unauthenticated');
          set({ isLoading: false, isAuthenticated: false });
          return;
        }

        try {
          set({ isLoading: true });
          
          const response = await authApi.me();
          console.log('Me API response:', response.data);
          const user = response.data.data;
          console.log('Extracted user from /me:', user);
          
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
          
        } catch (error) {
          console.error('CheckAuth failed:', error);
          // Token is invalid, clear auth state
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      },

      updateUser: (userData: Partial<User>) => {
        const { user } = get();
        if (user) {
          set({
            user: { ...user, ...userData }
          });
        }
      },

      changePassword: async (currentPassword: string, newPassword: string) => {
        try {
          await authApi.changePassword(currentPassword, newPassword);
          toast.success('Password changed successfully');
          return true;
        } catch (error: any) {
          const message = error.response?.data?.error?.message || 'Password change failed';
          toast.error(message);
          return false;
        }
      },
    }),
    {
      name: 'gt2-auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        requiresTfa: state.requiresTfa,
        tfaConfigured: state.tfaConfigured,
      }),
    }
  )
);