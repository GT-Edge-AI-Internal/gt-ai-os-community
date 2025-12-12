import { cn } from '@/lib/utils';

interface LoadingScreenProps {
  message?: string;
  className?: string;
}

export function LoadingScreen({ 
  message = 'Loading...', 
  className 
}: LoadingScreenProps) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center min-h-screen bg-gt-white',
      className
    )}>
      <div className="flex flex-col items-center space-y-4">
        {/* GT 2.0 Logo/Spinner */}
        <div className="relative">
          <div className="w-16 h-16 border-4 border-gt-gray-200 rounded-full animate-spin">
            <div className="absolute top-0 left-0 w-4 h-4 bg-gt-green rounded-full transform -translate-x-2 -translate-y-2"></div>
          </div>
          
          {/* Neural network animation */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex space-x-1">
              <div className="w-1 h-1 bg-gt-green rounded-full animate-neural-pulse"></div>
              <div className="w-1 h-1 bg-gt-green rounded-full animate-neural-pulse" style={{ animationDelay: '0.2s' }}></div>
              <div className="w-1 h-1 bg-gt-green rounded-full animate-neural-pulse" style={{ animationDelay: '0.4s' }}></div>
            </div>
          </div>
        </div>

        {/* Loading Message */}
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gt-gray-900 mb-2">
            GT 2.0
          </h2>
          <p className="text-gt-gray-600 text-sm animate-pulse-gentle">
            {message}
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="w-64 h-1 bg-gt-gray-200 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-gt-green to-gt-green/80 rounded-full animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ 
  size = 'md', 
  className 
}: LoadingSpinnerProps) {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className={cn('flex items-center justify-center', className)}>
      <div className={cn(
        'border-2 border-gt-gray-200 rounded-full animate-spin',
        'border-t-gt-green',
        sizes[size]
      )} />
    </div>
  );
}

interface TypingIndicatorProps {
  className?: string;
}

export function TypingIndicator({ className }: TypingIndicatorProps) {
  return (
    <div className={cn('flex items-center space-x-1 py-2', className)}>
      <span className="text-sm text-gt-gray-500">GT is thinking</span>
      <div className="flex space-x-1">
        <div className="w-1.5 h-1.5 bg-gt-green rounded-full animate-neural-pulse"></div>
        <div className="w-1.5 h-1.5 bg-gt-green rounded-full animate-neural-pulse" style={{ animationDelay: '0.2s' }}></div>
        <div className="w-1.5 h-1.5 bg-gt-green rounded-full animate-neural-pulse" style={{ animationDelay: '0.4s' }}></div>
      </div>
    </div>
  );
}

export default LoadingScreen;