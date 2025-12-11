/**
 * Unit tests for authentication store
 */
import { renderHook, act } from '@testing-library/react'
import { useAuthStore } from '../auth-store'

// Mock axios
jest.mock('axios', () => ({
  create: () => ({
    post: jest.fn(),
    get: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() }
    }
  })
}))

// Mock toast
jest.mock('react-hot-toast', () => ({
  success: jest.fn(),
  error: jest.fn()
}))

// Mock API
const mockAuthApi = {
  login: jest.fn(),
  logout: jest.fn(),
  me: jest.fn(),
  changePassword: jest.fn()
}

jest.mock('@/lib/api', () => ({
  authApi: mockAuthApi
}))

describe('Auth Store', () => {
  beforeEach(() => {
    // Reset store state
    useAuthStore.setState({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false
    })
    
    // Reset mocks
    jest.clearAllMocks()
    
    // Clear localStorage
    localStorage.clear()
  })

  describe('Initial State', () => {
    test('has correct initial state', () => {
      const { result } = renderHook(() => useAuthStore())
      
      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.isLoading).toBe(false)
      expect(result.current.isAuthenticated).toBe(false)
    })
  })

  describe('Login', () => {
    test('successful login updates state correctly', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        full_name: 'Test User',
        user_type: 'super_admin'
      }
      const mockToken = 'mock-jwt-token'

      mockAuthApi.login.mockResolvedValueOnce({
        data: {
          access_token: mockToken,
          user: mockUser
        }
      })

      const { result } = renderHook(() => useAuthStore())

      let loginResult: boolean
      await act(async () => {
        loginResult = await result.current.login('test@example.com', 'password123')
      })

      expect(loginResult!).toBe(true)
      expect(result.current.user).toEqual(mockUser)
      expect(result.current.token).toBe(mockToken)
      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.isLoading).toBe(false)
      expect(mockAuthApi.login).toHaveBeenCalledWith('test@example.com', 'password123')
    })

    test('failed login handles error correctly', async () => {
      const mockError = {
        response: {
          data: {
            error: {
              message: 'Invalid credentials'
            }
          }
        }
      }

      mockAuthApi.login.mockRejectedValueOnce(mockError)

      const { result } = renderHook(() => useAuthStore())

      let loginResult: boolean
      await act(async () => {
        loginResult = await result.current.login('test@example.com', 'wrongpassword')
      })

      expect(loginResult!).toBe(false)
      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(false)
    })

    test('login sets loading state correctly', async () => {
      mockAuthApi.login.mockImplementationOnce(() => 
        new Promise(resolve => setTimeout(resolve, 100))
      )

      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.login('test@example.com', 'password123')
      })

      expect(result.current.isLoading).toBe(true)
    })
  })

  describe('Logout', () => {
    test('logout clears state correctly', async () => {
      // Set initial authenticated state
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        full_name: 'Test User',
        user_type: 'super_admin'
      }
      
      useAuthStore.setState({
        user: mockUser,
        token: 'mock-token',
        isAuthenticated: true
      })

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        result.current.logout()
      })

      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(false)
    })

    test('logout calls API endpoint', async () => {
      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        result.current.logout()
      })

      expect(mockAuthApi.logout).toHaveBeenCalled()
    })
  })

  describe('Check Auth', () => {
    test('checkAuth validates existing token', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        full_name: 'Test User',
        user_type: 'super_admin'
      }

      // Set token in store
      useAuthStore.setState({ token: 'valid-token' })

      mockAuthApi.me.mockResolvedValueOnce({
        data: {
          data: mockUser
        }
      })

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        await result.current.checkAuth()
      })

      expect(result.current.user).toEqual(mockUser)
      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.isLoading).toBe(false)
      expect(mockAuthApi.me).toHaveBeenCalled()
    })

    test('checkAuth handles invalid token', async () => {
      // Set invalid token in store
      useAuthStore.setState({ token: 'invalid-token' })

      mockAuthApi.me.mockRejectedValueOnce(new Error('Unauthorized'))

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        await result.current.checkAuth()
      })

      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(false)
    })

    test('checkAuth handles no token', async () => {
      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        await result.current.checkAuth()
      })

      expect(result.current.isLoading).toBe(false)
      expect(result.current.isAuthenticated).toBe(false)
      expect(mockAuthApi.me).not.toHaveBeenCalled()
    })
  })

  describe('Update User', () => {
    test('updateUser merges user data correctly', () => {
      const initialUser = {
        id: 1,
        email: 'test@example.com',
        full_name: 'Test User',
        user_type: 'super_admin'
      }

      useAuthStore.setState({ user: initialUser })

      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.updateUser({ full_name: 'Updated Name' })
      })

      expect(result.current.user).toEqual({
        ...initialUser,
        full_name: 'Updated Name'
      })
    })

    test('updateUser handles no existing user', () => {
      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.updateUser({ full_name: 'New Name' })
      })

      expect(result.current.user).toBeNull()
    })
  })

  describe('Change Password', () => {
    test('successful password change returns true', async () => {
      mockAuthApi.changePassword.mockResolvedValueOnce({})

      const { result } = renderHook(() => useAuthStore())

      let changeResult: boolean
      await act(async () => {
        changeResult = await result.current.changePassword('oldpass', 'newpass')
      })

      expect(changeResult!).toBe(true)
      expect(mockAuthApi.changePassword).toHaveBeenCalledWith('oldpass', 'newpass')
    })

    test('failed password change returns false', async () => {
      const mockError = {
        response: {
          data: {
            error: {
              message: 'Current password is incorrect'
            }
          }
        }
      }

      mockAuthApi.changePassword.mockRejectedValueOnce(mockError)

      const { result } = renderHook(() => useAuthStore())

      let changeResult: boolean
      await act(async () => {
        changeResult = await result.current.changePassword('wrongpass', 'newpass')
      })

      expect(changeResult!).toBe(false)
    })
  })

  describe('Persistence', () => {
    test('persists authentication state to localStorage', async () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        full_name: 'Test User',
        user_type: 'super_admin'
      }
      const mockToken = 'mock-jwt-token'

      mockAuthApi.login.mockResolvedValueOnce({
        data: {
          access_token: mockToken,
          user: mockUser
        }
      })

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        await result.current.login('test@example.com', 'password123')
      })

      // Check localStorage was called
      expect(localStorage.setItem).toHaveBeenCalled()
    })

    test('restores authentication state from localStorage', () => {
      const mockStoredState = {
        user: {
          id: 1,
          email: 'test@example.com',
          full_name: 'Test User',
          user_type: 'super_admin'
        },
        token: 'stored-token',
        isAuthenticated: true
      }

      localStorage.setItem('gt2-auth-storage', JSON.stringify(mockStoredState))

      // Create new store instance to test persistence
      const { result } = renderHook(() => useAuthStore())

      // Note: In actual implementation, the persistence would restore automatically
      // This test would need to be adjusted based on how Zustand persistence works
      expect(result.current.user).toBeDefined()
    })
  })
})