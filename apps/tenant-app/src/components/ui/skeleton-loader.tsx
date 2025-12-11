/**
 * Skeleton Loading Components
 *
 * Provides animated placeholder components for better perceived performance
 * while data is loading.
 */

import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton component with pulse animation
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-gray-200',
        className
      )}
    />
  );
}

/**
 * Skeleton for agent cards in gallery view
 */
export function AgentCardSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="animate-pulse space-y-3">
        {/* Header with avatar and name */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gray-200 rounded-full" />
          <div className="flex-1">
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
            <div className="h-3 bg-gray-200 rounded w-1/2" />
          </div>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <div className="h-3 bg-gray-200 rounded w-full" />
          <div className="h-3 bg-gray-200 rounded w-5/6" />
        </div>

        {/* Tags */}
        <div className="flex space-x-2">
          <div className="h-6 bg-gray-200 rounded-full w-16" />
          <div className="h-6 bg-gray-200 rounded-full w-20" />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for conversation list items
 */
export function ConversationSkeleton() {
  return (
    <div className="p-2 rounded-lg">
      <div className="animate-pulse space-y-2">
        <div className="flex items-center justify-between">
          <div className="h-3 bg-gray-200 rounded w-2/3" />
          <div className="h-2 bg-gray-200 rounded w-12" />
        </div>
        <div className="h-2 bg-gray-200 rounded w-1/2" />
      </div>
    </div>
  );
}

/**
 * Skeleton for agent quick tiles (quick view)
 */
export function AgentQuickTileSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
      <div className="animate-pulse space-y-4">
        {/* Icon and title */}
        <div className="flex items-center space-x-3">
          <div className="w-12 h-12 bg-gray-200 rounded-lg" />
          <div className="flex-1">
            <div className="h-5 bg-gray-200 rounded w-2/3 mb-2" />
            <div className="h-3 bg-gray-200 rounded w-1/3" />
          </div>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <div className="h-3 bg-gray-200 rounded w-full" />
          <div className="h-3 bg-gray-200 rounded w-4/5" />
        </div>

        {/* Action buttons */}
        <div className="flex space-x-2 pt-2">
          <div className="h-9 bg-gray-200 rounded flex-1" />
          <div className="h-9 bg-gray-200 rounded w-20" />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for dataset cards
 */
export function DatasetCardSkeleton() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="animate-pulse space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-6 bg-gray-200 rounded-full w-16" />
        </div>

        {/* Description */}
        <div className="space-y-2">
          <div className="h-3 bg-gray-200 rounded w-full" />
          <div className="h-3 bg-gray-200 rounded w-3/4" />
        </div>

        {/* Stats */}
        <div className="flex space-x-4 pt-2">
          <div className="h-3 bg-gray-200 rounded w-20" />
          <div className="h-3 bg-gray-200 rounded w-24" />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton grid for multiple cards
 */
export function SkeletonGrid({
  count = 6,
  CardComponent = AgentCardSkeleton
}: {
  count?: number;
  CardComponent?: React.ComponentType;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <CardComponent key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton list for conversations
 */
export function SkeletonList({
  count = 10
}: {
  count?: number;
}) {
  return (
    <div className="space-y-1">
      {Array.from({ length: count }).map((_, i) => (
        <ConversationSkeleton key={i} />
      ))}
    </div>
  );
}
