'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Eye, Check, X, Clock, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ObservableRequest } from '@/services/teams';

interface ObservableRequestCardProps {
  request: ObservableRequest;
  onApprove: (teamId: string) => Promise<void>;
  onRevoke: (teamId: string) => Promise<void>;
}

export function ObservableRequestCard({
  request,
  onApprove,
  onRevoke,
}: ObservableRequestCardProps) {
  const [isApproving, setIsApproving] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      await onApprove(request.team_id);
    } catch (error) {
      console.error('Failed to approve Team Observability request:', error);
    } finally {
      setIsApproving(false);
    }
  };

  const handleRevoke = async () => {
    setIsRevoking(true);
    try {
      await onRevoke(request.team_id);
    } catch (error) {
      console.error('Failed to revoke Team Observability request:', error);
    } finally {
      setIsRevoking(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(
      Math.ceil((date.getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
      'day'
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="border-2 border-green-200 bg-green-50 rounded-lg p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left side - Request info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
              <Eye className="w-5 h-5 text-green-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-gray-900 truncate">
                {request.team_name}
              </h3>
              <p className="text-xs text-gray-500">
                Requested by {request.requested_by_name}
              </p>
            </div>
          </div>

          <p className="text-sm text-gray-600 mb-3">
            <strong>{request.requested_by_name}</strong> wants to view your activity on the team observability dashboard.
            By approving, team managers will be able to see your conversations and usage metrics.
          </p>

          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>Requested {formatDate(request.requested_at)}</span>
            </div>
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              <span className="text-green-600 font-medium">Team Observability Status</span>
            </div>
          </div>
        </div>

        {/* Right side - Actions */}
        <div className="flex flex-col gap-2 flex-shrink-0">
          <Button
            size="sm"
            onClick={handleApprove}
            disabled={isApproving || isRevoking}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isApproving ? (
              <>
                <div className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-white border-r-transparent mr-2" />
                Approving...
              </>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                Approve
              </>
            )}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleRevoke}
            disabled={isApproving || isRevoking}
            className="border-gray-300 hover:bg-gray-100"
          >
            {isRevoking ? (
              <>
                <div className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-gray-600 border-r-transparent mr-2" />
                Declining...
              </>
            ) : (
              <>
                <X className="w-4 h-4 mr-2" />
                Decline
              </>
            )}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
