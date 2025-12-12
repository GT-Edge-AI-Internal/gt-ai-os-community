'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Bell, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { InvitationCard } from './invitation-card';
import { usePendingInvitations, useAcceptInvitation, useDeclineInvitation } from '@/hooks/use-teams';

export function InvitationPanel() {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: invitations = [], isLoading } = usePendingInvitations();
  const acceptInvitation = useAcceptInvitation();
  const declineInvitation = useDeclineInvitation();

  const handleAccept = async (invitationId: string) => {
    try {
      console.log('🔍 Accepting invitation:', {
        invitationId,
        timestamp: new Date().toISOString()
      });
      await acceptInvitation.mutateAsync(invitationId);
      console.log('✅ Invitation accepted successfully');
      alert('Invitation accepted! You are now a member of the team.');
    } catch (error: any) {
      console.error('❌ Failed to accept invitation:', {
        invitationId,
        error: error.message,
        fullError: error
      });
      alert(`Failed to accept invitation: ${error.message || 'An error occurred'}`);
    }
  };

  const handleDecline = async (invitationId: string) => {
    try {
      await declineInvitation.mutateAsync(invitationId);
      alert('Invitation declined. The invitation has been removed.');
    } catch (error: any) {
      alert(`Failed to decline invitation: ${error.message || 'An error occurred'}`);
    }
  };

  // Don't show panel if no invitations and not loading
  if (!isLoading && invitations.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6"
    >
      <div className="bg-white border-2 border-amber-200 rounded-lg shadow-sm overflow-hidden">
        {/* Header - Always visible */}
        <div
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full px-6 py-4 flex items-center justify-between hover:bg-amber-50 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
              <Bell className="w-5 h-5 text-amber-600" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-gray-900">
                  Team Invitations
                </h3>
                {invitations.length > 0 && (
                  <Badge className="bg-amber-500 hover:bg-amber-600 text-white">
                    {invitations.length}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-gray-500">
                {isLoading
                  ? 'Loading invitations...'
                  : `${invitations.length} pending ${invitations.length === 1 ? 'invitation' : 'invitations'}`
                }
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isExpanded && invitations.length > 0 && (
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
              className="border-t border-amber-200"
            >
              <div className="p-6 space-y-3">
                {isLoading ? (
                  <div className="text-center py-8">
                    <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-amber-500 border-r-transparent mb-3" />
                    <p className="text-gray-600">Loading invitations...</p>
                  </div>
                ) : invitations.length > 0 ? (
                  invitations.map((invitation) => (
                    <InvitationCard
                      key={invitation.id}
                      invitation={invitation}
                      onAccept={handleAccept}
                      onDecline={handleDecline}
                    />
                  ))
                ) : (
                  <div className="text-center py-8">
                    <Inbox className="w-16 h-16 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">No pending invitations</p>
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
