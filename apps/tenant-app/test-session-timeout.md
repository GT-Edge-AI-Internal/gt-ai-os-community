# Session Timeout Testing Guide

## Quick Test (30 seconds)

### Option A: Manual Token Corruption (Fastest)

1. **Login** as `david@gtedge.ai` at http://localhost:3002
2. **Open DevTools** (F12 or Cmd+Option+I)
3. **Go to Console tab** and run:
   ```javascript
   // Set an expired token
   localStorage.setItem('gt2_token', 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NDdhMGM1Ny1iZjJmLTQ3ODItYTZlOC0wMjA1ZTllNDE1MmUiLCJlbWFpbCI6ImRhdmlkQGd0ZWRnZS5haSIsInVzZXJfdHlwZSI6InRlbmFudF9hZG1pbiIsImV4cCI6MTc2Mjk2MzkxOSwiaWF0IjoxNzYyOTYwMzE5fQ.fake_signature');

   // Force a page navigation to trigger auth check
   window.location.reload();
   ```

4. **Expected Result** (immediate):
   - Redirect to `/login?session_expired=true`
   - Red banner at top: "Your session has expired. Please log in again."
   - URL cleans up to `/login` after 100ms

### Option B: Trigger Token Monitor (30 seconds)

1. **Login** as `david@gtedge.ai` at http://localhost:3002
2. **Stay on any page** (don't navigate)
3. **Open DevTools Console** and run:
   ```javascript
   // Set an expired token
   localStorage.setItem('gt2_token', 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NDdhMGM1Ny1iZjJmLTQ3ODItYTZlOC0wMjA1ZTllNDE1MmUiLCJlbWFpbCI6ImRhdmlkQGd0ZWRnZS5haSIsInVzZXJfdHlwZSI6InRlbmFudF9hZG1pbiIsImV4cCI6MTc2Mjk2MzkxOSwiaWF0IjoxNzYyOTYwMzE5fQ.fake_signature');

   // DON'T reload - wait for monitor
   console.log('Token set to expired. Monitor will detect in max 30 seconds...');
   ```

4. **Wait up to 30 seconds**
5. **Expected Result**:
   - Automatic redirect without any user action
   - Session expired message appears
   - Console log: "AuthGuard: Invalid or missing token, logging out"

### Option C: 401 Response from API

1. **Login** as `david@gtedge.ai`
2. **Open DevTools Console** and run:
   ```javascript
   // Corrupt the token to trigger 401
   localStorage.setItem('gt2_token', 'invalid_token_will_get_401');

   // Make any API call (e.g., fetch agents)
   fetch('/api/v1/agents', {
     headers: {
       'Authorization': 'Bearer invalid_token_will_get_401',
       'X-Tenant-Domain': 'test-company'
     }
   }).then(() => console.log('API call made - should trigger logout'));
   ```

3. **Expected Result** (immediate):
   - 401 response from backend
   - Automatic logout and redirect
   - Session expired message

---

## Full Testing Checklist

### ✅ Test Cases

- [ ] **Manual logout** - Click logout button, redirect works
- [ ] **Expired token (monitor)** - Detected within 30 seconds
- [ ] **Expired token (navigation)** - Detected on page change
- [ ] **401 from API** - Immediate redirect on unauthorized response
- [ ] **Session message** - Banner shows "Your session has expired"
- [ ] **URL cleanup** - Query param removed after message shown
- [ ] **No duplicate redirects** - Single, clean redirect
- [ ] **Monitor lifecycle** - Starts on login, stops on logout

### 🔍 What to Look For

**In Browser Console:**
```
AuthGuard: Invalid or missing token, logging out
```

**In Network Tab:**
- No duplicate `/login` requests
- Clean redirect flow

**In Application/Storage:**
- `gt2_token`, `gt2_user`, `gt2_tenant` all cleared
- `auth-store` localStorage updated to `isAuthenticated: false`

**On Login Page:**
- Red banner at top of page
- Alert icon visible
- Message: "Your session has expired. Please log in again."
- Banner fades after URL cleanup

---

## Debugging

If session timeout isn't working:

1. **Check token monitor is running:**
   ```javascript
   // In console after login:
   const store = JSON.parse(localStorage.getItem('auth-store'));
   console.log('Is Authenticated:', store.state.isAuthenticated);

   // Monitor should be running - check logs every 30 seconds
   ```

2. **Check for errors:**
   ```javascript
   // Watch for auth errors
   window.addEventListener('error', (e) => console.error('Error:', e));
   ```

3. **Verify token expiration:**
   ```javascript
   const token = localStorage.getItem('gt2_token');
   if (token) {
     const payload = JSON.parse(atob(token.split('.')[1]));
     const now = Math.floor(Date.now() / 1000);
     console.log('Token expired:', payload.exp < now);
     console.log('Expires at:', new Date(payload.exp * 1000));
   }
   ```

4. **Check container logs:**
   ```bash
   docker logs gentwo-tenant-frontend --tail 50
   docker logs gentwo-tenant-backend --tail 50
   ```

---

## Implementation Details

### Files Modified
- `apps/tenant-app/src/stores/auth-store.ts` - Token monitor + centralized logout
- `apps/tenant-app/src/services/api.ts` - 401 handler
- `apps/tenant-app/src/lib/providers.tsx` - React Query handler
- `apps/tenant-app/src/services/index.ts` - Error handler
- `apps/tenant-app/src/components/auth/auth-guard.tsx` - Reactive to auth changes
- `apps/tenant-app/src/app/login/login-page-client.tsx` - Session expired message

### How It Works

1. **On Login**: `startTokenMonitor()` begins checking token every 30 seconds
2. **Monitor Detection**: If token expired, calls `logout('expired')`
3. **API 401**: All 401 responses call `logout('unauthorized')`
4. **Centralized Logout**:
   - Stops monitor
   - Clears localStorage
   - Updates Zustand store
   - Redirects to `/login?session_expired=true`
5. **Login Page**: Detects query param, shows banner, cleans URL
6. **AuthGuard**: Subscribes to store, redirects if `isAuthenticated` becomes false

---

**Status**: ✅ Implemented and running in Docker (hot reload active)
