'use client';

import packageInfo from '../../../package.json';

interface VersionDisplayProps {
  className?: string;
  showBranch?: boolean;
}

export function VersionDisplay({ className = "", showBranch = true }: VersionDisplayProps) {
  const version = packageInfo.version;
  const branch = process.env.NODE_ENV === 'development' ? 'dev' : 'community';

  return (
    <div className={`text-xs text-gray-500 ${className}`}>
      GT AI OS Community | v{version}{showBranch && `-${branch}`}
    </div>
  );
}

// Helper to get just the version string
export function getAppVersion(): string {
  return packageInfo.version;
}

// Helper to get version with branch
export function getFullVersion(): string {
  const version = packageInfo.version;
  const branch = process.env.NODE_ENV === 'development' ? 'dev' : 'community';
  return `GT AI OS Community | v${version}-${branch}`;
}