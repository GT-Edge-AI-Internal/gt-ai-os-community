'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Home page redirect
 *
 * This page has been removed. Users are redirected to the agents page.
 */
export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/agents');
  }, [router]);

  return null;
}