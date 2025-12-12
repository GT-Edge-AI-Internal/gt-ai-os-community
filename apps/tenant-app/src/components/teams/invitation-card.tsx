'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Users, UserCheck, UserX, Clock, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { TeamInvitation } from '@/services/teams';

interface InvitationCardProps {
  invitation: TeamInvitation;
  onAccept: (invitationId: string) => Promise<void>;
  onDecline: (invitationId: string) => Promise<void>;
}

export function InvitationCard({
  invitation,
  onAccept,
  onDecline,
}: InvitationCardProps) {
  const [isAccepting, setIsAccepting] = useState(false);
  const [isDeclining, setIsDeclining] = useState(false);

  const handleAccept = async () => {
    setIsAccepting(true);
    try {
      await onAccept(invitation.id);
    } catch (error) {
      console.error('Failed to accept invitation:', error);
    } finally {
      setIsAccepting(false);
    }
  };

  const handleDecline = async () => {
    setIsDeclining(true);
    try {
      await onDecline(invitation.id);
    } catch (error) {
      console.error('Failed to decline invitation:', error);
    } finally {
      setIsDeclining(false);
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
      className="border-2 border-amber-200 bg-amber-50 rounded-lg p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left side - Team info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <Users className="w-5 h-5 text-amber-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-gray-900 truncate">
                {invitation.team_name}
              </h3>
              <p className="text-xs text-gray-500">
                Invited by {invitation.owner_name}
              </p>
            </div>
          </div>

          {invitation.team_description && (
            <p className="text-sm text-gray-600 mb-3 line-clamp-2">
              {invitation.team_description}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>Invited {formatDate(invitation.invited_at)}</span>
            </div>
            <div className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              <Badge
                variant={invitation.team_permission === 'share' ? 'default' : 'secondary'}
                className="text-xs"
              >
                {invitation.team_permission === 'share' ? 'Share' : 'View'} Permission
              </Badge>
            </div>
          </div>
        </div>

        {/* Right side - Actions */}
        <div className="flex flex-col gap-2 flex-shrink-0">
          <Button
            size="sm"
            onClick={handleAccept}
            disabled={isAccepting || isDeclining}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isAccepting ? (
              <>
                <div className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-white border-r-transparent mr-2" />
                Accepting...
              </>
            ) : (
              <>
                <UserCheck className="w-4 h-4 mr-2" />
                Accept
              </>
            )}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleDecline}
            disabled={isAccepting || isDeclining}
            className="border-gray-300 hover:bg-gray-100"
          >
            {isDeclining ? (
              <>
                <div className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-gray-600 border-r-transparent mr-2" />
                Declining...
              </>
            ) : (
              <>
                <UserX className="w-4 h-4 mr-2" />
                Decline
              </>
            )}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
