import { useEffect } from 'react';

/**
 * Custom hook to set the page title dynamically for client components
 * Format: GT AI OS | <Page Name>
 */
export function usePageTitle(pageTitle: string) {
  useEffect(() => {
    document.title = `GT AI OS | ${pageTitle}`;
    
    // Cleanup: restore default title on unmount
    return () => {
      document.title = 'GT AI OS';
    };
  }, [pageTitle]);
}
