'use client';

import { useEffect, useState } from 'react';
import { Download, Trash2, Upload, HardDrive, Loader2, AlertCircle } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Card, CardContent } from '@/components/ui/card';
import { systemApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface Backup {
  id: string;
  uuid: string;
  created_at: string;
  backup_type: 'manual' | 'scheduled' | 'pre_update';
  size: number;
  version: string;
  is_valid: boolean;
  description?: string;
  download_url?: string;
}

interface StorageInfo {
  used: number;
  total: number;
  available: number;
}

export function BackupManager() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [storageInfo, setStorageInfo] = useState<StorageInfo>({
    used: 0,
    total: 100,
    available: 100
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [operatingBackupId, setOperatingBackupId] = useState<string | null>(null);

  useEffect(() => {
    fetchBackups();
  }, []);

  const fetchBackups = async () => {
    try {
      setIsLoading(true);
      const response = await systemApi.listBackups();
      const data = response.data;

      setBackups(data.backups || []);
      if (data.storage) {
        setStorageInfo(data.storage);
      }
    } catch (error) {
      console.error('Failed to fetch backups:', error);
      toast.error('Failed to load backups');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateBackup = async (type: 'manual' | 'scheduled' | 'pre_update') => {
    setIsCreating(true);
    try {
      await systemApi.createBackup(type);
      const typeLabel = type === 'pre_update' ? 'Pre-update' : type.charAt(0).toUpperCase() + type.slice(1);
      toast.success(`${typeLabel} backup created successfully`);
      fetchBackups();
    } catch (error) {
      console.error('Failed to create backup:', error);
      toast.error('Failed to create backup');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDownloadBackup = async (backup: Backup) => {
    try {
      setOperatingBackupId(backup.uuid);

      if (backup.download_url) {
        // Create a download link
        const link = document.createElement('a');
        link.href = backup.download_url;
        link.download = `backup-${backup.uuid}.tar.gz`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        toast.success('Backup download started');
      } else {
        toast.error('Download URL not available');
      }
    } catch (error) {
      console.error('Failed to download backup:', error);
      toast.error('Failed to download backup');
    } finally {
      setOperatingBackupId(null);
    }
  };

  const handleRestoreBackup = async (backupId: string) => {
    const confirmed = confirm(
      'Are you sure you want to restore this backup? This will replace all current data and restart the system.'
    );

    if (!confirmed) return;

    try {
      setOperatingBackupId(backupId);
      await systemApi.restoreBackup(backupId);
      toast.success('Backup restore initiated. System will restart shortly...');

      // Wait a few seconds then reload
      setTimeout(() => {
        window.location.reload();
      }, 3000);
    } catch (error) {
      console.error('Failed to restore backup:', error);
      toast.error('Failed to restore backup');
      setOperatingBackupId(null);
    }
  };

  const handleDeleteBackup = async (backupId: string) => {
    const confirmed = confirm('Are you sure you want to delete this backup? This action cannot be undone.');

    if (!confirmed) return;

    try {
      setOperatingBackupId(backupId);
      await systemApi.deleteBackup(backupId);
      toast.success('Backup deleted successfully');
      fetchBackups();
    } catch (error) {
      console.error('Failed to delete backup:', error);
      toast.error('Failed to delete backup');
    } finally {
      setOperatingBackupId(null);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getBackupTypeBadge = (type: string) => {
    switch (type) {
      case 'manual':
        return <Badge className="bg-blue-600">Manual</Badge>;
      case 'scheduled':
        return <Badge className="bg-green-600">Scheduled</Badge>;
      case 'pre_update':
        return <Badge className="bg-purple-600">Pre-Update</Badge>;
      default:
        return <Badge>{type}</Badge>;
    }
  };

  const getStatusBadge = (isValid: boolean) => {
    if (isValid) {
      return <Badge variant="default" className="bg-green-600">Valid</Badge>;
    } else {
      return <Badge variant="destructive">Invalid</Badge>;
    }
  };

  const storagePercentage = (storageInfo.used / storageInfo.total) * 100;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Loading backups...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Create Backup Button */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium">Backup Management</h3>
          <p className="text-sm text-muted-foreground">Create and manage system backups</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button disabled={isCreating}>
              {isCreating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Create Backup
                </>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleCreateBackup('manual')}>
              <HardDrive className="mr-2 h-4 w-4" />
              Manual Backup
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleCreateBackup('scheduled')}>
              <HardDrive className="mr-2 h-4 w-4" />
              Scheduled Backup
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleCreateBackup('pre_update')}>
              <HardDrive className="mr-2 h-4 w-4" />
              Pre-Update Backup
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Backups Table */}
      {backups.length > 0 ? (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {backups.map((backup) => (
                <TableRow key={backup.id}>
                  <TableCell className="font-medium">
                    {formatDate(backup.created_at)}
                  </TableCell>
                  <TableCell>{getBackupTypeBadge(backup.backup_type)}</TableCell>
                  <TableCell>{formatBytes(backup.size || 0)}</TableCell>
                  <TableCell className="font-mono text-sm">v{backup.version || 'unknown'}</TableCell>
                  <TableCell>{getStatusBadge(backup.is_valid)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end space-x-2">
                      {backup.is_valid && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownloadBackup(backup)}
                            disabled={operatingBackupId === backup.uuid}
                            aria-label="Download backup"
                          >
                            {operatingBackupId === backup.uuid ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Download className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRestoreBackup(backup.uuid)}
                            disabled={operatingBackupId === backup.uuid}
                            aria-label="Restore backup"
                          >
                            Restore
                          </Button>
                        </>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteBackup(backup.uuid)}
                        disabled={operatingBackupId === backup.uuid}
                        aria-label="Delete backup"
                      >
                        {operatingBackupId === backup.uuid ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4 text-red-600" />
                        )}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No backups found</h3>
            <p className="text-sm text-muted-foreground mb-4 text-center">
              Create your first backup to protect your data
            </p>
          </CardContent>
        </Card>
      )}

      {/* Storage Usage */}
      <Card>
        <CardContent className="p-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Storage Usage</span>
              <span className="text-muted-foreground">
                {formatBytes(storageInfo.used)} / {formatBytes(storageInfo.total)}
              </span>
            </div>
            <Progress value={storagePercentage} className="h-2" />
            <p className="text-xs text-muted-foreground">
              {formatBytes(storageInfo.available)} available
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
