/**
 * Unit tests for login page component
 */
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRouter } from 'next/navigation'
import LoginPage from '../../app/auth/login/page'
import { useAuthStore } from '../../stores/auth-store'

// Mock next/navigation
jest.mock('next/navigation')
const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>

// Mock auth store
jest.mock('../../stores/auth-store')
const mockUseAuthStore = useAuthStore as jest.MockedFunction<typeof useAuthStore>

// Mock toast
jest.mock('react-hot-toast', () => ({
  success: jest.fn(),
  error: jest.fn()
}))

describe('LoginPage', () => {
  const mockPush = jest.fn()
  const mockReplace = jest.fn()
  const mockLogin = jest.fn()

  beforeEach(() => {
    mockUseRouter.mockReturnValue({
      push: mockPush,
      replace: mockReplace,
      refresh: jest.fn(),
      back: jest.fn(),
      forward: jest.fn(),
      prefetch: jest.fn()
    })

    mockUseAuthStore.mockReturnValue({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      login: mockLogin,
      logout: jest.fn(),
      checkAuth: jest.fn(),
      updateUser: jest.fn(),
      changePassword: jest.fn()
    })

    jest.clearAllMocks()
  })

  test('renders login form correctly', () => {
    render(<LoginPage />)

    expect(screen.getByText('GT 2.0 Control Panel')).toBeInTheDocument()
    expect(screen.getByText('Sign in to your administrator account')).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  test('displays demo credentials', () => {
    render(<LoginPage />)

    expect(screen.getByText('Demo credentials:')).toBeInTheDocument()
    expect(screen.getByText('admin@gt2.dev / admin123')).toBeInTheDocument()
  })

  test('validates required fields', async () => {
    const user = userEvent.setup()
    render(<LoginPage />)

    const submitButton = screen.getByRole('button', { name: /sign in/i })
    
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
    })
  })

  test('validates email format', async () => {
    const user = userEvent.setup()
    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const submitButton = screen.getByRole('button', { name: /sign in/i })

    await user.type(emailInput, 'invalid-email')
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
    })
  })

  test('submits form with valid credentials', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValue(true)

    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /sign in/i })

    await user.type(emailInput, 'admin@gt2.dev')
    await user.type(passwordInput, 'admin123')
    await user.click(submitButton)

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin@gt2.dev', 'admin123')
    })
  })

  test('redirects to dashboard on successful login', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValue(true)

    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /sign in/i })

    await user.type(emailInput, 'admin@gt2.dev')
    await user.type(passwordInput, 'admin123')
    await user.click(submitButton)

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard')
    })
  })

  test('shows loading state during submission', async () => {
    const user = userEvent.setup()
    mockLogin.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve(true), 100)))

    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /sign in/i })

    await user.type(emailInput, 'admin@gt2.dev')
    await user.type(passwordInput, 'admin123')
    await user.click(submitButton)

    expect(screen.getByText(/signing in/i)).toBeInTheDocument()
    expect(submitButton).toBeDisabled()
  })

  test('handles failed login attempt', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValue(false)

    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const submitButton = screen.getByRole('button', { name: /sign in/i })

    await user.type(emailInput, 'admin@gt2.dev')
    await user.type(passwordInput, 'wrongpassword')
    await user.click(submitButton)

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin@gt2.dev', 'wrongpassword')
    })

    expect(mockPush).not.toHaveBeenCalled()
  })

  test('toggles password visibility', async () => {
    const user = userEvent.setup()
    render(<LoginPage />)

    const passwordInput = screen.getByLabelText(/password/i) as HTMLInputElement
    const toggleButton = screen.getByRole('button', { name: '' }) // Password toggle button

    expect(passwordInput.type).toBe('password')

    await user.click(toggleButton)
    expect(passwordInput.type).toBe('text')

    await user.click(toggleButton)
    expect(passwordInput.type).toBe('password')
  })

  test('redirects if already authenticated', () => {
    mockUseAuthStore.mockReturnValue({
      user: { id: 1, email: 'test@example.com', full_name: 'Test User', user_type: 'super_admin' },
      token: 'mock-token',
      isLoading: false,
      isAuthenticated: true,
      login: mockLogin,
      logout: jest.fn(),
      checkAuth: jest.fn(),
      updateUser: jest.fn(),
      changePassword: jest.fn()
    })

    render(<LoginPage />)

    expect(mockReplace).toHaveBeenCalledWith('/dashboard')
  })

  test('shows loading store state', () => {
    mockUseAuthStore.mockReturnValue({
      user: null,
      token: null,
      isLoading: true,
      isAuthenticated: false,
      login: mockLogin,
      logout: jest.fn(),
      checkAuth: jest.fn(),
      updateUser: jest.fn(),
      changePassword: jest.fn()
    })

    render(<LoginPage />)

    const submitButton = screen.getByRole('button', { name: /signing in/i })
    expect(submitButton).toBeDisabled()
  })

  test('keyboard navigation works correctly', async () => {
    const user = userEvent.setup()
    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)

    await user.click(emailInput)
    await user.keyboard('{Tab}')
    
    expect(passwordInput).toHaveFocus()
  })

  test('form submission on Enter key', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValue(true)

    render(<LoginPage />)

    const emailInput = screen.getByLabelText(/email/i)
    const passwordInput = screen.getByLabelText(/password/i)

    await user.type(emailInput, 'admin@gt2.dev')
    await user.type(passwordInput, 'admin123')
    await user.keyboard('{Enter}')

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin@gt2.dev', 'admin123')
    })
  })
})