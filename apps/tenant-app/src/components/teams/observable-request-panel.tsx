'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Eye, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ObservableRequestCard } from './observable-request-card';
import { usePendingObservableRequests, useApproveObservableRequest, useRevokeObservableStatus } from '@/hooks/use-teams';

export function ObservableRequestPanel() {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: requests = [], isLoading } = usePendingObservableRequests();
  const approveRequest = useApproveObservableRequest();
  const revokeRequest = useRevokeObservableStatus();

  const handleApprove = async (teamId: string) => {
    try {
      await approveRequest.mutateAsync(teamId);
      alert('Team Observability approved! Team managers can now view your activity.');
    } catch (error: any) {
      alert(`Failed to approve Team Observability request: ${error.message || 'An error occurred'}`);
    }
  };

  const handleRevoke = async (teamId: string) => {
    try {
      await revokeRequest.mutateAsync(teamId);
      alert('Team Observability request declined. Managers cannot view your activity.');
    } catch (error: any) {
      alert(`Failed to decline Team Observability request: ${error.message || 'An error occurred'}`);
    }
  };

  // Don't show panel if no requests and not loading
  if (!isLoading && requests.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6"
    >
      <div className="bg-gt-white border-2 border-green-200 rounded-lg shadow-sm overflow-hidden">
        {/* Header - Always visible */}
        <div
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-green-50 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
              <Eye className="w-5 h-5 text-green-600" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-gray-900">
                  Team Observability Requests
                </h3>
                {requests.length > 0 && (
                  <Badge className="bg-green-600 hover:bg-green-700 text-white">
                    {requests.length}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-gray-500">
                {isLoading
                  ? 'Loading requests...'
                  : `${requests.length} pending ${requests.length === 1 ? 'request' : 'requests'}`
                }
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isExpanded && requests.length > 0 && (
              <Button
                size="sm"
                className="bg-green-600 hover:bg-green-700 text-white"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsExpanded(true);
                }}
              >
                View
              </Button>
            )}
            {isExpanded ? (
              <ChevronDown className="w-5 h-5 text-gray-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-gray-400" />
            )}
          </div>
        </div>

        {/* Expandable content */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="border-t border-green-200"
            >
              <div className="p-6 space-y-3">
                {isLoading ? (
                  <div className="text-center py-8">
                    <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-green-600 border-r-transparent mb-3" />
                    <p className="text-gray-600">Loading Team Observability requests...</p>
                  </div>
                ) : requests.length > 0 ? (
                  requests.map((request) => (
                    <ObservableRequestCard
                      key={request.team_id}
                      request={request}
                      onApprove={handleApprove}
                      onRevoke={handleRevoke}
                    />
                  ))
                ) : (
                  <div className="text-center py-8">
                    <Inbox className="w-16 h-16 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">No pending Team Observability requests</p>
                    <p className="text-sm text-gray-500 mt-1">
                      You're all caught up!
                    </p>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
