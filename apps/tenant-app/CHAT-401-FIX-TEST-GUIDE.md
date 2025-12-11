# Chat 401 Error Handling - Test Guide

## ✅ Implementation Complete

All fixes have been implemented to handle expired tokens during chat interactions properly.

---

## **What Was Fixed**

### **Bug 1: JWT Parsing Crash** ✅
**File:** `apps/tenant-app/src/services/auth.ts` (lines 170-198)

**Before:**
```typescript
const payload = token.split('.')[1];
const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
// ❌ Crashes if payload is undefined
```

**After:**
```typescript
// Validate input
if (!token || typeof token !== 'string') return null;
const parts = token.split('.');
if (parts.length !== 3) return null;
const payload = parts[1];
if (!payload) return null;
// ✅ Safe null checking before accessing properties
```

---

### **Bug 2: Chat Service 401 Not Triggering Logout** ✅
**File:** `apps/tenant-app/src/services/chat-service.ts`

**A. Early Detection (lines 85-108):**
```typescript
private getAuthHeaders(): Record<string, string> {
  // Check token validity BEFORE making request
  if (!isTokenValid()) {
    console.warn('ChatService: Token invalid/expired, triggering logout');
    // Trigger logout immediately
    import('@/stores/auth-store').then(({ useAuthStore }) => {
      useAuthStore.getState().logout('expired');
    });
    return headers; // No auth header - will get 401
  }
  // ...
}
```

**B. 401 Response Handling (lines 140-152):**
```typescript
if (!response.ok) {
  // Handle 401 - session expired
  if (response.status === 401) {
    const { useAuthStore } = await import('@/stores/auth-store');
    useAuthStore.getState().logout('expired');
    throw new Error('SESSION_EXPIRED'); // Special error type
  }
  // ...
}
```

---

### **Bug 3: Error Shown in Chat UI** ✅
**File:** `apps/tenant-app/src/app/chat/page.tsx` (lines 1235-1266)

**Before:**
```typescript
onError: (error: Error) => {
  // Shows ALL errors in chat
  const errorMessage: ChatMessage = {
    content: `Sorry, I encountered an error: ${error.message}`,
    // ...
  };
  setMessages(prev => [...prev, errorMessage]);
}
```

**After:**
```typescript
onError: (error: Error) => {
  // Don't show error message for session expiration
  if (error.message === 'SESSION_EXPIRED') {
    console.log('Chat: Session expired, logout triggered');
    // Clean up state
    return; // User will be redirected, don't show error
  }

  // Show error message for other errors
  const errorMessage: ChatMessage = {
    content: `Sorry, I encountered an error: ${error.message}`,
    // ...
  };
  setMessages(prev => [...prev, errorMessage]);
}
```

---

## **Quick Test (2 minutes)**

### **Method 1: Expire Token Before Chat**

1. **Login** as any user at http://localhost:3002
2. **Go to /chat** page
3. **Open DevTools Console** and run:
   ```javascript
   // Set an expired token
   localStorage.setItem('gt2_token', 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NDdhMGM1Ny1iZjJmLTQ3ODItYTZlOC0wMjA1ZTllNDE1MmUiLCJlbWFpbCI6ImRhdmlkQGd0ZWRnZS5haSIsInVzZXJfdHlwZSI6InRlbmFudF9hZG1pbiIsImV4cCI6MTc2Mjk2MzkxOSwiaWF0IjoxNzYyOTYwMzE5fQ.fake_signature');
   ```
4. **Type a message** in chat and press Enter
5. **Expected Behavior:**
   - ✅ Console log: "ChatService: Token invalid/expired, triggering logout"
   - ✅ Immediate redirect to `/login?session_expired=true`
   - ✅ Red banner: "Your session has expired. Please log in again."
   - ❌ NO error message in chat
   - ❌ NO JWT parsing crash

---

### **Method 2: Invalid Token During Chat**

1. **Login** and go to **/chat**
2. **Send one message successfully** (to verify chat works)
3. **Open DevTools Console** and run:
   ```javascript
   // Corrupt token mid-chat
   localStorage.setItem('gt2_token', 'invalid_token');
   ```
4. **Send another message**
5. **Expected Behavior:**
   - ✅ No crash
   - ✅ Console: "ChatService: Token invalid/expired, triggering logout"
   - ✅ Redirect to login with session expired banner
   - ❌ NO "Sorry, I encountered an error: HTTP 401..." in chat

---

### **Method 3: Test JWT Parsing Protection**

Run in browser console after visiting any page:

```javascript
// Test null token
const auth = await import('./src/services/auth.ts');
console.log('Null token:', auth.parseTokenPayload(null));
// Expected: null (no crash)

// Test invalid token
console.log('Invalid:', auth.parseTokenPayload('not.a.jwt'));
// Expected: null (no crash)

// Test empty string
console.log('Empty:', auth.parseTokenPayload(''));
// Expected: null (no crash)
```

---

## **Error Flow (Fixed)**

### **Before Fix:**
```
User sends message with expired token
    ↓
getAuthHeaders() returns headers without checking token
    ↓
fetch() → Backend returns 401
    ↓
throw new Error("HTTP 401: ...")
    ↓
onError handler receives Error
    ↓
❌ Shows error in chat UI
❌ JWT parsing crashes on next operation
```

### **After Fix:**
```
User sends message with expired token
    ↓
getAuthHeaders() checks isTokenValid()
    ↓
Token invalid → logout('expired') triggered
    ↓
Still sends request (will get 401)
    ↓
401 response → logout('expired') again (defensive)
    ↓
throw new Error('SESSION_EXPIRED')
    ↓
onError handler sees SESSION_EXPIRED
    ↓
✅ Skips error message
✅ User redirected to login
✅ Session expired banner shown
```

---

## **Console Messages to Look For**

### **Success Indicators:**

```
ChatService: Token invalid/expired, triggering logout
Chat: Session expired, logout triggered
AuthGuard: Invalid or missing token, logging out
```

### **Warning Messages (Expected):**

```
parseTokenPayload: Invalid token (null or not string)
parseTokenPayload: Invalid JWT format (not 3 parts)
parseTokenPayload: Missing payload section
```

### **Error Messages (Should NOT Appear):**

```
❌ Failed to parse JWT payload: TypeError: Cannot read properties of undefined
❌ Sorry, I encountered an error: HTTP 401: {"error":{"message":"Authentication required"...
❌ 🌊 Streaming error: Error: HTTP 401: Unauthorized
```

---

## **Testing Checklist**

- [ ] **JWT parsing handles null** - No crash on `parseTokenPayload(null)`
- [ ] **JWT parsing handles invalid format** - No crash on malformed tokens
- [ ] **Chat detects expired token before request** - `getAuthHeaders` triggers logout
- [ ] **Chat handles 401 response** - Triggers logout, throws SESSION_EXPIRED
- [ ] **Error handler skips SESSION_EXPIRED** - No error shown in chat
- [ ] **User redirected to login** - With session expired banner
- [ ] **Banner displays correctly** - Red alert with message
- [ ] **URL cleans up** - `?session_expired=true` removed after 100ms

---

## **Debugging**

If session timeout handling still fails:

1. **Check console for warnings:**
   ```javascript
   // Should see:
   "ChatService: Token invalid/expired, triggering logout"
   ```

2. **Verify token monitor is running:**
   ```javascript
   // After login, check every 30 seconds for automatic detection
   const store = JSON.parse(localStorage.getItem('auth-store'));
   console.log('Token monitor interval:', store.state.tokenMonitorInterval);
   ```

3. **Check network tab:**
   - Look for POST to `/api/v1/chat/completions`
   - Should return 401 if token expired
   - Should NOT see multiple retry attempts

4. **Container logs:**
   ```bash
   docker logs gentwo-tenant-frontend --tail 50
   docker logs gentwo-tenant-backend --tail 50
   ```

---

## **Files Modified**

1. ✅ `apps/tenant-app/src/services/auth.ts` - JWT parsing safety
2. ✅ `apps/tenant-app/src/services/chat-service.ts` - 401 detection
3. ✅ `apps/tenant-app/src/app/chat/page.tsx` - SESSION_EXPIRED handling

**Total lines changed:** ~60 lines across 3 files
**Risk level:** Low (defensive coding, backward compatible)
**Status:** ✅ Complete, running in Docker with hot reload

---

## **Related Fixes**

This fix complements the earlier session timeout work:
- Token monitor in auth-store (checks every 30 seconds)
- Centralized logout method
- AuthGuard reactive to auth state changes
- 401 handlers in API layer and React Query

Together, these ensure users are **always** redirected to login when their session expires, regardless of where in the app they are or what they're doing.

---

**Last Updated:** January 2025
**Docker Container:** gentwo-tenant-frontend (hot reload active)
