'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Conversations page redirect
 * 
 * This page has been removed. Users are redirected to the chat page.
 */
export default function ConversationsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/chat');
  }, [router]);

  return null;
}