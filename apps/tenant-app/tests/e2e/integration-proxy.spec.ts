/**
 * Playwright E2E Tests for Integration Proxy Features
 * 
 * Tests the integration management UI that consumes the Integration Proxy API,
 * covering service creation, configuration, execution, and monitoring.
 */

import { test, expect, Page } from '@playwright/test';

// Mock API responses for integration proxy endpoints
const mockIntegrations = [
  {
    id: 'test-slack-integration',
    name: 'Slack API',
    integration_type: 'communication',
    base_url: 'https://slack.com/api',
    authentication_method: 'oauth2',
    sandbox_level: 'basic',
    max_requests_per_hour: 1000,
    max_response_size_bytes: 1048576,
    timeout_seconds: 30,
    allowed_methods: ['GET', 'POST'],
    allowed_endpoints: ['/conversations.list', '/chat.postMessage'],
    blocked_endpoints: ['/admin'],
    allowed_domains: ['slack.com'],
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    created_by: 'admin@test.com'
  },
  {
    id: 'test-github-integration',
    name: 'GitHub API',
    integration_type: 'development',
    base_url: 'https://api.github.com',
    authentication_method: 'api_key',
    sandbox_level: 'restricted',
    max_requests_per_hour: 500,
    max_response_size_bytes: 2097152,
    timeout_seconds: 45,
    allowed_methods: ['GET', 'POST', 'PUT'],
    allowed_endpoints: ['/repos', '/user'],
    blocked_endpoints: ['/admin'],
    allowed_domains: ['github.com'],
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    created_by: 'admin@test.com'
  }
];

const mockIntegrationTypes = {
  integration_types: [
    {
      value: 'communication',
      label: 'Communication',
      description: 'Slack, Teams, Discord integration'
    },
    {
      value: 'development',
      label: 'Development',
      description: 'GitHub, GitLab, Jira integration'
    },
    {
      value: 'custom_api',
      label: 'Custom API',
      description: 'Custom REST/GraphQL APIs'
    }
  ]
};

const mockSandboxLevels = {
  sandbox_levels: [
    {
      value: 'none',
      label: 'No Restrictions',
      description: 'Trusted integrations with full access'
    },
    {
      value: 'basic',
      label: 'Basic Restrictions',
      description: 'Basic timeout and size limits'
    },
    {
      value: 'restricted',
      label: 'Restricted Access',
      description: 'Limited API calls and data access'
    },
    {
      value: 'strict',
      label: 'Maximum Security',
      description: 'Strict restrictions and monitoring'
    }
  ]
};

const mockAuthMethods = {
  auth_methods: [
    {
      value: 'api_key',
      label: 'API Key',
      description: 'Simple API key authentication',
      fields: ['api_key', 'key_header', 'key_prefix']
    },
    {
      value: 'oauth2',
      label: 'OAuth 2.0',
      description: 'OAuth 2.0 bearer token authentication',
      fields: ['access_token', 'refresh_token', 'client_id', 'client_secret']
    }
  ]
};

const mockUsageAnalytics = {
  integration_id: 'test-slack-integration',
  total_requests: 1250,
  successful_requests: 1198,
  error_count: 52,
  success_rate: 0.958,
  avg_execution_time_ms: 245.5,
  date_range: {
    start: '2024-01-01T00:00:00Z',
    end: '2024-01-31T23:59:59Z'
  }
};

// Helper function to setup API mocks
async function setupAPIMocks(page: Page) {
  // Mock integration listing endpoint
  await page.route('/api/v1/integrations', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockIntegrations)
      });
    }
  });

  // Mock integration creation endpoint
  await page.route('/api/v1/integrations', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          ...mockIntegrations[0],
          id: 'new-integration-' + Date.now()
        })
      });
    }
  });

  // Mock integration execution endpoint
  await page.route('/api/v1/integrations/execute', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          status_code: 200,
          data: { message: 'Integration executed successfully' },
          headers: { 'content-type': 'application/json' },
          execution_time_ms: 245,
          sandbox_applied: true,
          restrictions_applied: ['timeout_limited_to_30s', 'endpoint_validation'],
          error_message: null
        })
      });
    }
  });

  // Mock usage analytics endpoint
  await page.route('/api/v1/integrations/*/usage', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockUsageAnalytics)
    });
  });

  // Mock catalog endpoints
  await page.route('/api/v1/integrations/catalog/types', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockIntegrationTypes)
    });
  });

  await page.route('/api/v1/integrations/catalog/sandbox-levels', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockSandboxLevels)
    });
  });

  await page.route('/api/v1/integrations/catalog/auth-methods', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockAuthMethods)
    });
  });
}

test.describe('Integration Proxy Management', () => {
  
  test.beforeEach(async ({ page }) => {
    await setupAPIMocks(page);
    await page.goto('/integrations');
  });

  test('should display integration overview dashboard', async ({ page }) => {
    // Check page title and navigation
    await expect(page).toHaveTitle(/Integrations.*GT 2.0/);
    await expect(page.locator('h1')).toContainText('External Integrations');
    
    // Check overview stats cards
    await expect(page.locator('[data-testid="total-integrations"]')).toBeVisible();
    await expect(page.locator('[data-testid="active-integrations"]')).toBeVisible();
    await expect(page.locator('[data-testid="requests-today"]')).toBeVisible();
    await expect(page.locator('[data-testid="success-rate"]')).toBeVisible();
    
    // Check that integrations are loaded and displayed
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(2);
    await expect(page.locator('text=Slack API')).toBeVisible();
    await expect(page.locator('text=GitHub API')).toBeVisible();
  });

  test('should filter integrations by type', async ({ page }) => {
    // Navigate to integrations list
    await page.click('[data-testid="integrations-tab"]');
    
    // Apply communication filter
    await page.click('[data-testid="filter-communication"]');
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(1);
    await expect(page.locator('text=Slack API')).toBeVisible();
    await expect(page.locator('text=GitHub API')).not.toBeVisible();
    
    // Apply development filter
    await page.click('[data-testid="filter-development"]');
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(1);
    await expect(page.locator('text=GitHub API')).toBeVisible();
    await expect(page.locator('text=Slack API')).not.toBeVisible();
    
    // Clear filters
    await page.click('[data-testid="clear-filters"]');
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(2);
  });

  test('should open create integration modal', async ({ page }) => {
    // Click create integration button
    await page.click('button:has-text("New Integration")');
    
    // Check modal is open
    await expect(page.locator('[data-testid="create-integration-modal"]')).toBeVisible();
    await expect(page.locator('h2:has-text("Create Integration")')).toBeVisible();
    
    // Check form fields are present
    await expect(page.locator('[data-testid="integration-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="integration-type"]')).toBeVisible();
    await expect(page.locator('[data-testid="base-url"]')).toBeVisible();
    await expect(page.locator('[data-testid="auth-method"]')).toBeVisible();
    await expect(page.locator('[data-testid="sandbox-level"]')).toBeVisible();
  });

  test('should create new integration with API key authentication', async ({ page }) => {
    // Open create modal
    await page.click('button:has-text("New Integration")');
    
    // Fill in form fields
    await page.fill('[data-testid="integration-name"]', 'Test API Integration');
    await page.selectOption('[data-testid="integration-type"]', 'custom_api');
    await page.fill('[data-testid="base-url"]', 'https://api.example.com');
    await page.selectOption('[data-testid="auth-method"]', 'api_key');
    await page.selectOption('[data-testid="sandbox-level"]', 'basic');
    
    // Fill authentication details
    await page.fill('[data-testid="api-key"]', 'test-api-key-123');
    await page.fill('[data-testid="key-header"]', 'X-API-Key');
    
    // Configure rate limits
    await page.fill('[data-testid="max-requests"]', '500');
    await page.fill('[data-testid="timeout"]', '30');
    
    // Submit form
    await page.click('button:has-text("Create Integration")');
    
    // Check success message
    await expect(page.locator('[data-testid="success-message"]')).toContainText('Integration created successfully');
    
    // Modal should close
    await expect(page.locator('[data-testid="create-integration-modal"]')).not.toBeVisible();
  });

  test('should create OAuth2 integration with advanced settings', async ({ page }) => {
    // Open create modal
    await page.click('button:has-text("New Integration")');
    
    // Fill basic fields
    await page.fill('[data-testid="integration-name"]', 'OAuth2 Service');
    await page.selectOption('[data-testid="integration-type"]', 'communication');
    await page.fill('[data-testid="base-url"]', 'https://api.oauth-service.com');
    await page.selectOption('[data-testid="auth-method"]', 'oauth2');
    await page.selectOption('[data-testid="sandbox-level"]', 'restricted');
    
    // Fill OAuth2 credentials
    await page.fill('[data-testid="access-token"]', 'oauth-access-token-123');
    await page.fill('[data-testid="client-id"]', 'client-id-456');
    await page.fill('[data-testid="client-secret"]', 'client-secret-789');
    
    // Configure advanced settings
    await page.click('[data-testid="advanced-settings-toggle"]');
    await page.fill('[data-testid="allowed-endpoints"]', '/api/v1/channels,/api/v1/messages');
    await page.fill('[data-testid="blocked-endpoints"]', '/admin,/config');
    await page.check('[data-testid="enable-method-restrictions"]');
    await page.uncheck('[data-testid="allow-delete"]');
    
    // Submit form
    await page.click('button:has-text("Create Integration")');
    
    // Verify success
    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
  });

  test('should validate form inputs', async ({ page }) => {
    // Open create modal
    await page.click('button:has-text("New Integration")');
    
    // Try to submit empty form
    await page.click('button:has-text("Create Integration")');
    
    // Check validation errors
    await expect(page.locator('[data-testid="name-error"]')).toContainText('Name is required');
    await expect(page.locator('[data-testid="url-error"]')).toContainText('Base URL is required');
    
    // Fill invalid URL
    await page.fill('[data-testid="base-url"]', 'not-a-url');
    await expect(page.locator('[data-testid="url-error"]')).toContainText('Please enter a valid URL');
    
    // Fill invalid rate limit
    await page.fill('[data-testid="max-requests"]', '-1');
    await expect(page.locator('[data-testid="rate-limit-error"]')).toContainText('Must be a positive number');
  });

  test('should display integration details', async ({ page }) => {
    // Click on an integration card
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    
    // Check details panel is open
    await expect(page.locator('[data-testid="integration-details"]')).toBeVisible();
    await expect(page.locator('h2:has-text("Slack API")')).toBeVisible();
    
    // Check configuration details
    await expect(page.locator('[data-testid="integration-type"]')).toContainText('Communication');
    await expect(page.locator('[data-testid="sandbox-level"]')).toContainText('Basic Restrictions');
    await expect(page.locator('[data-testid="auth-method"]')).toContainText('OAuth 2.0');
    await expect(page.locator('[data-testid="rate-limit"]')).toContainText('1000/hour');
    
    // Check endpoint restrictions
    await expect(page.locator('[data-testid="allowed-endpoints"]')).toBeVisible();
    await expect(page.locator('[data-testid="blocked-endpoints"]')).toBeVisible();
  });

  test('should execute integration with test request', async ({ page }) => {
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    
    // Switch to testing tab
    await page.click('[data-testid="test-tab"]');
    
    // Configure test request
    await page.selectOption('[data-testid="http-method"]', 'GET');
    await page.fill('[data-testid="endpoint"]', '/conversations.list');
    await page.fill('[data-testid="test-params"]', '{"limit": 10}');
    
    // Execute test
    await page.click('button:has-text("Execute Test")');
    
    // Check test results
    await expect(page.locator('[data-testid="test-results"]')).toBeVisible();
    await expect(page.locator('[data-testid="response-status"]')).toContainText('200');
    await expect(page.locator('[data-testid="execution-time"]')).toContainText('245ms');
    await expect(page.locator('[data-testid="sandbox-applied"]')).toContainText('Yes');
    
    // Check restrictions applied
    await expect(page.locator('[data-testid="restrictions"]')).toContainText('timeout_limited_to_30s');
    await expect(page.locator('[data-testid="restrictions"]')).toContainText('endpoint_validation');
  });

  test('should display usage analytics', async ({ page }) => {
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    
    // Switch to analytics tab
    await page.click('[data-testid="analytics-tab"]');
    
    // Check analytics data
    await expect(page.locator('[data-testid="total-requests"]')).toContainText('1,250');
    await expect(page.locator('[data-testid="success-rate"]')).toContainText('95.8%');
    await expect(page.locator('[data-testid="avg-response-time"]')).toContainText('245.5ms');
    await expect(page.locator('[data-testid="error-count"]')).toContainText('52');
    
    // Check time range selector
    await expect(page.locator('[data-testid="time-range-selector"]')).toBeVisible();
    
    // Test different time ranges
    await page.selectOption('[data-testid="time-range-selector"]', '7d');
    await expect(page.locator('[data-testid="date-range"]')).toBeVisible();
  });

  test('should handle integration errors gracefully', async ({ page }) => {
    // Mock error response
    await page.route('/api/v1/integrations/execute', async route => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          status_code: 400,
          data: null,
          headers: {},
          execution_time_ms: 50,
          sandbox_applied: true,
          restrictions_applied: ['endpoint_validation'],
          error_message: 'Invalid endpoint: blocked by security policy'
        })
      });
    });
    
    // Open integration and test
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    await page.click('[data-testid="test-tab"]');
    await page.fill('[data-testid="endpoint"]', '/admin/users');
    await page.click('button:has-text("Execute Test")');
    
    // Check error is displayed
    await expect(page.locator('[data-testid="error-message"]')).toContainText('Invalid endpoint: blocked by security policy');
    await expect(page.locator('[data-testid="response-status"]')).toContainText('400');
  });

  test('should edit integration configuration', async ({ page }) => {
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("GitHub API")');
    
    // Click edit button
    await page.click('[data-testid="edit-integration"]');
    
    // Check edit modal is open
    await expect(page.locator('[data-testid="edit-integration-modal"]')).toBeVisible();
    
    // Modify settings
    await page.fill('[data-testid="max-requests"]', '750');
    await page.selectOption('[data-testid="sandbox-level"]', 'strict');
    
    // Save changes
    await page.click('button:has-text("Save Changes")');
    
    // Check success message
    await expect(page.locator('[data-testid="update-success"]')).toBeVisible();
    
    // Verify changes are reflected
    await expect(page.locator('[data-testid="rate-limit"]')).toContainText('750/hour');
    await expect(page.locator('[data-testid="sandbox-level"]')).toContainText('Maximum Security');
  });

  test('should delete integration with confirmation', async ({ page }) => {
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("GitHub API")');
    
    // Click delete button
    await page.click('[data-testid="delete-integration"]');
    
    // Check confirmation dialog
    await expect(page.locator('[data-testid="delete-confirmation"]')).toBeVisible();
    await expect(page.locator('text=Are you sure you want to delete')).toBeVisible();
    
    // Cancel first
    await page.click('button:has-text("Cancel")');
    await expect(page.locator('[data-testid="delete-confirmation"]')).not.toBeVisible();
    
    // Try again and confirm
    await page.click('[data-testid="delete-integration"]');
    await page.fill('[data-testid="confirm-name"]', 'GitHub API');
    await page.click('button:has-text("Delete Integration")');
    
    // Check integration is removed
    await expect(page.locator('[data-testid="integration-card"]:has-text("GitHub API")')).not.toBeVisible();
    await expect(page.locator('[data-testid="delete-success"]')).toBeVisible();
  });

  test('should search and filter integrations', async ({ page }) => {
    // Navigate to integrations list
    await page.click('[data-testid="integrations-tab"]');
    
    // Use search
    await page.fill('[data-testid="search-integrations"]', 'Slack');
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(1);
    await expect(page.locator('text=Slack API')).toBeVisible();
    
    // Clear search
    await page.fill('[data-testid="search-integrations"]', '');
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(2);
    
    // Filter by sandbox level
    await page.selectOption('[data-testid="sandbox-filter"]', 'basic');
    await expect(page.locator('[data-testid="integration-card"]')).toHaveCount(1);
    await expect(page.locator('text=Slack API')).toBeVisible();
  });

  test('should display integration health status', async ({ page }) => {
    // Check health indicators on cards
    await expect(page.locator('[data-testid="health-indicator"]:has-text("Healthy")')).toHaveCount(2);
    
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    
    // Check health details
    await expect(page.locator('[data-testid="health-status"]')).toContainText('Healthy');
    await expect(page.locator('[data-testid="last-health-check"]')).toBeVisible();
    await expect(page.locator('[data-testid="response-time"]')).toBeVisible();
    
    // Test health check
    await page.click('[data-testid="run-health-check"]');
    await expect(page.locator('[data-testid="health-check-running"]')).toBeVisible();
  });

  test('should handle rate limiting notifications', async ({ page }) => {
    // Mock rate limit exceeded response
    await page.route('/api/v1/integrations/execute', async route => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          status_code: 429,
          data: null,
          headers: { 'x-rate-limit-remaining': '0' },
          execution_time_ms: 5,
          sandbox_applied: true,
          restrictions_applied: ['rate_limit_exceeded'],
          error_message: 'Rate limit exceeded: 1000 requests per hour'
        })
      });
    });
    
    // Execute test that will hit rate limit
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    await page.click('[data-testid="test-tab"]');
    await page.click('button:has-text("Execute Test")');
    
    // Check rate limit notification
    await expect(page.locator('[data-testid="rate-limit-warning"]')).toBeVisible();
    await expect(page.locator('[data-testid="rate-limit-warning"]')).toContainText('Rate limit exceeded');
    await expect(page.locator('[data-testid="response-status"]')).toContainText('429');
  });

});

test.describe('Integration Proxy Security Features', () => {
  
  test.beforeEach(async ({ page }) => {
    await setupAPIMocks(page);
    await page.goto('/integrations');
  });

  test('should display sandbox restrictions clearly', async ({ page }) => {
    // Open integration with strict sandbox
    await page.click('[data-testid="integration-card"]:has-text("GitHub API")');
    
    // Check sandbox level display
    await expect(page.locator('[data-testid="sandbox-level"]')).toContainText('Restricted Access');
    
    // Check restrictions list
    await expect(page.locator('[data-testid="sandbox-restrictions"]')).toBeVisible();
    await expect(page.locator('[data-testid="timeout-limit"]')).toContainText('30 seconds');
    await expect(page.locator('[data-testid="size-limit"]')).toContainText('2 MB');
    await expect(page.locator('[data-testid="method-restrictions"]')).toBeVisible();
  });

  test('should show endpoint restrictions warnings', async ({ page }) => {
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    await page.click('[data-testid="test-tab"]');
    
    // Try blocked endpoint
    await page.fill('[data-testid="endpoint"]', '/admin');
    
    // Should show warning
    await expect(page.locator('[data-testid="endpoint-warning"]')).toContainText('This endpoint is blocked');
    await expect(page.locator('button:has-text("Execute Test")')).toBeDisabled();
    
    // Try allowed endpoint
    await page.fill('[data-testid="endpoint"]', '/conversations.list');
    await expect(page.locator('[data-testid="endpoint-warning"]')).not.toBeVisible();
    await expect(page.locator('button:has-text("Execute Test")')).toBeEnabled();
  });

  test('should display security audit log', async ({ page }) => {
    // Open integration details
    await page.click('[data-testid="integration-card"]:has-text("Slack API")');
    
    // Switch to audit tab
    await page.click('[data-testid="audit-tab"]');
    
    // Check audit log entries
    await expect(page.locator('[data-testid="audit-log"]')).toBeVisible();
    await expect(page.locator('[data-testid="audit-entry"]')).toHaveCount.greaterThan(0);
    
    // Check audit entry details
    await expect(page.locator('[data-testid="audit-action"]')).toBeVisible();
    await expect(page.locator('[data-testid="audit-timestamp"]')).toBeVisible();
    await expect(page.locator('[data-testid="audit-user"]')).toBeVisible();
    
    // Filter audit log
    await page.selectOption('[data-testid="audit-filter"]', 'execution');
    await expect(page.locator('[data-testid="audit-entry"]')).toBeVisible();
  });

});