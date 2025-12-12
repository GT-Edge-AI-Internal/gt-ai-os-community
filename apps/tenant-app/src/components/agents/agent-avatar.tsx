'use client';

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { avatarAnimations, neuralPulse, animationUtils } from '@/lib/animations/gt-animations';
import { cn } from '@/lib/utils';

export type PersonalityType = 'geometric' | 'organic' | 'minimal' | 'technical';
export type AvatarState = 'idle' | 'thinking' | 'speaking' | 'offline' | 'success' | 'error';

interface AgentAvatarProps {
  personality: PersonalityType;
  state: AvatarState;
  size?: 'small' | 'medium' | 'large';
  confidence?: number; // 0-1
  className?: string;
  showConfidence?: boolean;
  primaryColor?: string;
  secondaryColor?: string;
  customImageUrl?: string;
  onClick?: () => void;
}

const sizeMap = {
  small: 'w-12 h-12',
  medium: 'w-20 h-20',
  large: 'w-32 h-32',
};

const sizePx = {
  small: 48,
  medium: 80,
  large: 128,
};

export function AgentAvatar({
  personality = 'minimal',
  state = 'idle',
  size = 'medium',
  confidence = 1,
  className,
  showConfidence = false,
  primaryColor = '#00d084',
  secondaryColor = '#ffffff',
  customImageUrl,
  onClick,
}: AgentAvatarProps) {
  // Get animation based on personality and state
  const animation = useMemo(() => {
    if (state === 'offline') return {};
    // Map error state to idle animation as fallback
    const mappedState = state === 'error' ? 'idle' : state;
    return avatarAnimations[personality]?.[mappedState] || avatarAnimations.minimal.idle;
  }, [personality, state]);

  // Calculate opacity based on confidence
  const confidenceOpacity = 0.3 + (confidence * 0.7);

  // If custom image is provided, use that instead of personality shapes
  if (customImageUrl) {
    return (
      <div className={cn('relative inline-block', className)}>
        <motion.div
          className={cn(
            'relative flex items-center justify-center rounded-full overflow-hidden cursor-pointer',
            sizeMap[size],
            state === 'offline' && 'opacity-30',
            onClick && 'hover:shadow-lg transition-shadow'
          )}
          animate={animation}
          onClick={onClick}
          style={{
            filter: state === 'thinking' ? 'drop-shadow(0 0 10px rgba(0, 208, 132, 0.5))' : undefined,
          }}
        >
          <img 
            src={customImageUrl} 
            alt="Agent avatar"
            className="w-full h-full object-cover"
          />
          
          {/* Confidence indicator overlay */}
          {showConfidence && confidence < 1 && (
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/20">
              <motion.div
                className="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500"
                initial={{ width: 0 }}
                animate={{ width: `${confidence * 100}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          )}
        </motion.div>
        
        {/* State indicator for custom images */}
        <AnimatePresence>
          {state === 'thinking' && (
            <motion.div
              className="absolute -top-1 -right-1"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <motion.div
                className="w-3 h-3 bg-gt-green rounded-full"
                animate={neuralPulse.animate as any}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  // Render personality-based shape
  const renderShape = () => {
    const svgSize = sizePx[size];
    
    switch (personality) {
      case 'geometric':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <defs>
              <linearGradient id={`geometric-gradient-${personality}`} x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={primaryColor} stopOpacity={confidenceOpacity} />
                <stop offset="100%" stopColor={secondaryColor} stopOpacity={confidenceOpacity * 0.5} />
              </linearGradient>
              <filter id={`geometric-glow-${personality}`}>
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge> 
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            
            {/* Main hexagon shape */}
            <polygon
              points="50,10 90,30 90,70 50,90 10,70 10,30"
              fill={`url(#geometric-gradient-${personality})`}
              stroke={primaryColor}
              strokeWidth="2"
              strokeOpacity={confidence}
              filter={state === 'thinking' ? `url(#geometric-glow-${personality})` : undefined}
            />
            
            {/* Inner elements for different states */}
            {state === 'thinking' && (
              <>
                <circle
                  cx="50"
                  cy="50"
                  r="5"
                  fill={primaryColor}
                  opacity={confidence}
                >
                  <animate
                    attributeName="r"
                    values="5;15;5"
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="1;0.3;1"
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                </circle>
                
                {/* Neural network pattern */}
                <g opacity={confidence * 0.6}>
                  <line x1="30" y1="30" x2="70" y2="70" stroke={primaryColor} strokeWidth="1">
                    <animate
                      attributeName="stroke-dasharray"
                      values="0,40;20,20;40,0"
                      dur="2s"
                      repeatCount="indefinite"
                    />
                  </line>
                  <line x1="70" y1="30" x2="30" y2="70" stroke={primaryColor} strokeWidth="1">
                    <animate
                      attributeName="stroke-dasharray"
                      values="40,0;20,20;0,40"
                      dur="2s"
                      repeatCount="indefinite"
                    />
                  </line>
                </g>
              </>
            )}
            
            {state === 'speaking' && (
              <g opacity={confidence}>
                {[20, 35, 50].map((r, i) => (
                  <circle
                    key={r}
                    cx="50"
                    cy="50"
                    r={r}
                    fill="none"
                    stroke={primaryColor}
                    strokeWidth="1"
                    opacity="0.5"
                  >
                    <animate
                      attributeName="r"
                      values={`${r};${r + 10};${r}`}
                      dur="0.8s"
                      begin={`${i * 0.2}s`}
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="opacity"
                      values="0.5;0;0.5"
                      dur="0.8s"
                      begin={`${i * 0.2}s`}
                      repeatCount="indefinite"
                    />
                  </circle>
                ))}
              </g>
            )}
            
            {state === 'success' && (
              <g opacity={confidence}>
                <path
                  d="M35 50 L45 60 L65 40"
                  stroke={primaryColor}
                  strokeWidth="3"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <animate
                    attributeName="stroke-dasharray"
                    values="0 30;30 0"
                    dur="0.5s"
                  />
                </path>
              </g>
            )}
          </svg>
        );

      case 'organic':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <defs>
              <radialGradient id={`organic-gradient-${personality}`}>
                <stop offset="0%" stopColor={primaryColor} stopOpacity={confidenceOpacity} />
                <stop offset="100%" stopColor={secondaryColor} stopOpacity={confidenceOpacity * 0.3} />
              </radialGradient>
              <filter id={`organic-blur-${personality}`}>
                <feGaussianBlur stdDeviation="2" />
              </filter>
              <filter id={`organic-glow-${personality}`}>
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            
            {/* Main organic shape */}
            <path
              d="M50,20 Q80,30 70,50 T50,80 Q20,70 30,50 T50,20"
              fill={`url(#organic-gradient-${personality})`}
              stroke="none"
              filter={`url(#organic-blur-${personality})`}
            />
            
            {state === 'thinking' && (
              <g opacity={confidence}>
                {/* Ripple effects */}
                {[30, 40, 50].map((r, i) => (
                  <circle
                    key={r}
                    cx="50"
                    cy="50"
                    r={r}
                    fill="none"
                    stroke={primaryColor}
                    strokeWidth="0.5"
                    opacity="0.3"
                  >
                    <animate
                      attributeName="r"
                      values={`${r};${r + 15};${r}`}
                      dur="2s"
                      begin={`${i * 0.5}s`}
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="opacity"
                      values="0.3;0;0.3"
                      dur="2s"
                      begin={`${i * 0.5}s`}
                      repeatCount="indefinite"
                    />
                  </circle>
                ))}
              </g>
            )}
            
            {state === 'speaking' && (
              <g opacity={confidence}>
                {/* Flowing wave patterns */}
                <path
                  d="M25,45 Q35,40 45,45 T65,45 T85,45"
                  stroke={primaryColor}
                  strokeWidth="1"
                  fill="none"
                  opacity="0.6"
                >
                  <animate
                    attributeName="d"
                    values="M25,45 Q35,40 45,45 T65,45 T85,45;M25,45 Q35,50 45,45 T65,45 T85,45;M25,45 Q35,40 45,45 T65,45 T85,45"
                    dur="1.2s"
                    repeatCount="indefinite"
                  />
                </path>
                <path
                  d="M25,55 Q35,50 45,55 T65,55 T85,55"
                  stroke={primaryColor}
                  strokeWidth="1"
                  fill="none"
                  opacity="0.4"
                >
                  <animate
                    attributeName="d"
                    values="M25,55 Q35,50 45,55 T65,55 T85,55;M25,55 Q35,60 45,55 T65,55 T85,55;M25,55 Q35,50 45,55 T65,55 T85,55"
                    dur="1.2s"
                    begin="0.3s"
                    repeatCount="indefinite"
                  />
                </path>
              </g>
            )}
          </svg>
        );

      case 'minimal':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <defs>
              <filter id={`minimal-glow-${personality}`}>
                <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            
            {/* Simple circle */}
            <circle
              cx="50"
              cy="50"
              r="35"
              fill={primaryColor}
              fillOpacity={confidenceOpacity}
              stroke="none"
              filter={state === 'thinking' ? `url(#minimal-glow-${personality})` : undefined}
            />
            
            {state === 'thinking' && (
              <circle
                cx="50"
                cy="50"
                r="35"
                fill="none"
                stroke={primaryColor}
                strokeWidth="1"
                strokeDasharray="5 5"
                opacity={confidence}
              >
                <animateTransform
                  attributeName="transform"
                  type="rotate"
                  from="0 50 50"
                  to="360 50 50"
                  dur="3s"
                  repeatCount="indefinite"
                />
              </circle>
            )}
            
            {state === 'speaking' && (
              <g opacity={confidence}>
                <circle cx="40" cy="45" r="2" fill={secondaryColor}>
                  <animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite" />
                </circle>
                <circle cx="50" cy="45" r="2" fill={secondaryColor}>
                  <animate attributeName="opacity" values="1;0;1" dur="1s" begin="0.2s" repeatCount="indefinite" />
                </circle>
                <circle cx="60" cy="45" r="2" fill={secondaryColor}>
                  <animate attributeName="opacity" values="1;0;1" dur="1s" begin="0.4s" repeatCount="indefinite" />
                </circle>
              </g>
            )}
          </svg>
        );

      case 'technical':
        return (
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <defs>
              <pattern id={`tech-grid-${personality}`} x="0" y="0" width="10" height="10" patternUnits="userSpaceOnUse">
                <line x1="0" y1="0" x2="0" y2="10" stroke={primaryColor} strokeWidth="0.5" opacity="0.3" />
                <line x1="0" y1="0" x2="10" y2="0" stroke={primaryColor} strokeWidth="0.5" opacity="0.3" />
              </pattern>
              <filter id={`tech-glow-${personality}`}>
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            
            {/* Grid background */}
            <rect x="15" y="15" width="70" height="70" fill={`url(#tech-grid-${personality})`} />
            
            {/* Main frame */}
            <rect
              x="20"
              y="20"
              width="60"
              height="60"
              fill="none"
              stroke={primaryColor}
              strokeWidth="2"
              strokeOpacity={confidence}
              filter={state === 'thinking' ? `url(#tech-glow-${personality})` : undefined}
            />
            
            {/* Corner brackets */}
            <g stroke={primaryColor} strokeWidth="2" fill="none" opacity={confidence}>
              <path d="M25,25 L30,25 L30,30" />
              <path d="M75,25 L70,25 L70,30" />
              <path d="M75,75 L70,75 L70,70" />
              <path d="M25,75 L30,75 L30,70" />
            </g>
            
            {state === 'thinking' && (
              <g opacity={confidence}>
                {/* Scanning lines */}
                <line x1="20" y1="50" x2="80" y2="50" stroke={primaryColor} strokeWidth="1">
                  <animate
                    attributeName="x1"
                    values="20;50;20"
                    dur="1s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="x2"
                    values="80;50;80"
                    dur="1s"
                    repeatCount="indefinite"
                  />
                </line>
                <line x1="50" y1="20" x2="50" y2="80" stroke={primaryColor} strokeWidth="1">
                  <animate
                    attributeName="y1"
                    values="20;50;20"
                    dur="1s"
                    begin="0.5s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="y2"
                    values="80;50;80"
                    dur="1s"
                    begin="0.5s"
                    repeatCount="indefinite"
                  />
                </line>
              </g>
            )}
            
            {state === 'speaking' && (
              <g opacity={confidence}>
                <text x="50" y="55" textAnchor="middle" fill={primaryColor} fontSize="8" fontFamily="monospace">
                  <tspan>&gt;_</tspan>
                  <animate attributeName="opacity" values="1;0;1" dur="0.5s" repeatCount="indefinite" />
                </text>
                
                {/* Data flow indicators */}
                {[35, 42, 49, 56, 63].map((y, i) => (
                  <rect
                    key={y}
                    x="30"
                    y={y}
                    width="40"
                    height="2"
                    fill={primaryColor}
                    opacity="0.3"
                  >
                    <animate
                      attributeName="opacity"
                      values="0.3;1;0.3"
                      dur="0.8s"
                      begin={`${i * 0.1}s`}
                      repeatCount="indefinite"
                    />
                  </rect>
                ))}
              </g>
            )}
          </svg>
        );

      default:
        return null;
    }
  };

  return (
    <div className={cn('relative inline-block', className)}>
      <motion.div
        className={cn(
          'relative flex items-center justify-center cursor-pointer',
          sizeMap[size],
          state === 'offline' && 'opacity-30',
          onClick && 'hover:shadow-lg transition-shadow'
        )}
        animate={animation}
        onClick={onClick}
        style={{
          filter: state === 'thinking' ? 'drop-shadow(0 0 10px rgba(0, 208, 132, 0.5))' : undefined,
        }}
      >
        {renderShape()}
      </motion.div>

      {/* Confidence indicator */}
      {showConfidence && confidence < 1 && (
        <div className="absolute -bottom-2 left-0 right-0 h-1 bg-gray-200 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500"
            initial={{ width: 0 }}
            animate={{ width: `${confidence * 100}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      )}

      {/* State indicator */}
      <AnimatePresence>
        {state === 'thinking' && (
          <motion.div
            className="absolute -top-1 -right-1"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="relative">
              <motion.div
                className="w-2 h-2 bg-gt-green rounded-full"
                animate={neuralPulse.animate as any}
              />
            </div>
          </motion.div>
        )}
        
        {state === 'success' && (
          <motion.div
            className="absolute -top-1 -right-1"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="w-3 h-3 bg-green-500 rounded-full flex items-center justify-center">
              <svg className="w-2 h-2 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </div>
          </motion.div>
        )}
        
        {state === 'error' && (
          <motion.div
            className="absolute -top-1 -right-1"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="w-3 h-3 bg-red-500 rounded-full flex items-center justify-center">
              <svg className="w-2 h-2 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}