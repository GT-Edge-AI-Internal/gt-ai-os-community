'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Resources page error:', error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[600px] p-6">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-16 h-16 flex items-center justify-center rounded-full bg-red-100">
            <AlertTriangle className="w-8 h-8 text-red-600" />
          </div>
          <CardTitle className="text-red-600">Failed to load resources</CardTitle>
          <CardDescription>
            There was a problem loading the AI resources page. This could be due to a network issue or server error.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-muted-foreground bg-muted p-3 rounded-md">
            <strong>Error:</strong> {error.message}
          </div>
          <div className="flex space-x-2">
            <Button onClick={reset} className="flex-1">
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
            <Button variant="secondary" onClick={() => window.location.reload()} className="flex-1">
              Reload Page
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}