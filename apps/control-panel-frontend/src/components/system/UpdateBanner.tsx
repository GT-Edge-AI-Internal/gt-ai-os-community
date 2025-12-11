'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, X, Download } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { systemApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { UpdateModal } from './UpdateModal';

interface UpdateInfo {
  available: boolean;
  current_version: string;
  latest_version: string;
  update_type: 'major' | 'minor' | 'patch';
  release_notes: string;
  released_at: string;
}

const DISMISSAL_KEY = 'gt2_update_dismissed';
const CHECK_INTERVAL = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

export function UpdateBanner() {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [isDismissed, setIsDismissed] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    checkForUpdates();

    // Set up periodic checking every 24 hours
    const interval = setInterval(checkForUpdates, CHECK_INTERVAL);

    return () => clearInterval(interval);
  }, []);

  const checkForUpdates = async () => {
    try {
      setIsChecking(true);
      const response = await systemApi.checkUpdate();
      const data = response.data as UpdateInfo;

      if (data.available) {
        setUpdateInfo(data);

        // Check if this version was previously dismissed
        const dismissalData = localStorage.getItem(DISMISSAL_KEY);
        if (dismissalData) {
          const { version, timestamp } = JSON.parse(dismissalData);
          const now = Date.now();
          const twentyFourHours = 24 * 60 * 60 * 1000;

          // Show banner if it's a different version or 24h have passed
          if (version !== data.latest_version || (now - timestamp) > twentyFourHours) {
            setIsDismissed(false);
          }
        } else {
          setIsDismissed(false);
        }
      } else {
        setUpdateInfo(null);
        setIsDismissed(true);
      }
    } catch (error) {
      console.error('Failed to check for updates:', error);
      // Silently fail - don't show error to user for background check
    } finally {
      setIsChecking(false);
    }
  };

  const handleDismiss = () => {
    if (updateInfo) {
      const dismissalData = {
        version: updateInfo.latest_version,
        timestamp: Date.now()
      };
      localStorage.setItem(DISMISSAL_KEY, JSON.stringify(dismissalData));
      setIsDismissed(true);
      toast.success('Update notification dismissed for 24 hours');
    }
  };

  const handleUpdateNow = () => {
    setShowModal(true);
  };

  const getVariantClass = () => {
    if (!updateInfo) return 'border-blue-500 bg-blue-50 text-blue-900';

    switch (updateInfo.update_type) {
      case 'major':
        return 'border-red-500 bg-red-50 text-red-900';
      case 'minor':
        return 'border-amber-500 bg-amber-50 text-amber-900';
      case 'patch':
        return 'border-blue-500 bg-blue-50 text-blue-900';
      default:
        return 'border-blue-500 bg-blue-50 text-blue-900';
    }
  };

  if (!updateInfo || isDismissed || isChecking) {
    return null;
  }

  return (
    <>
      <Alert className={`mb-4 ${getVariantClass()} border-l-4`} role="alert" aria-live="polite">
        <Download className="h-4 w-4" />
        <AlertTitle className="flex items-center justify-between pr-6">
          <span>Version {updateInfo.latest_version} available</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDismiss}
            className="absolute right-2 top-2 h-6 w-6 p-0 hover:bg-transparent"
            aria-label="Dismiss update notification"
          >
            <X className="h-4 w-4" />
          </Button>
        </AlertTitle>
        <AlertDescription className="flex items-center justify-between">
          <span>
            A new version of GT 2.0 is available. Update from v{updateInfo.current_version} to v{updateInfo.latest_version}.
          </span>
          <Button
            onClick={handleUpdateNow}
            size="sm"
            className="ml-4 shrink-0"
            aria-label="Open update dialog"
          >
            Update Now
          </Button>
        </AlertDescription>
      </Alert>

      {showModal && updateInfo && (
        <UpdateModal
          updateInfo={updateInfo}
          open={showModal}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
