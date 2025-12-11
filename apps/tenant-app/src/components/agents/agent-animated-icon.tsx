'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { avatarAnimations } from '@/lib/animations/gt-animations';

interface AgentAnimatedIconProps {
  iconUrl?: string;
  animationStyle: 'none' | 'subtle' | 'interactive';
  state: 'idle' | 'thinking' | 'speaking' | 'success';
  size?: 'small' | 'medium' | 'large';
  className?: string;
}

const sizeClasses = {
  small: 'w-8 h-8',
  medium: 'w-16 h-16', 
  large: 'w-24 h-24'
};

export function AgentAnimatedIcon({
  iconUrl,
  animationStyle = 'subtle',
  state = 'idle',
  size = 'medium',
  className
}: AgentAnimatedIconProps) {
  const getAnimation = () => {
    if (animationStyle === 'none') {
      return {};
    }
    
    if (animationStyle === 'subtle') {
      // Gentle breathing effect
      return {
        animate: { 
          scale: [1, 1.02, 1],
          opacity: [0.9, 1, 0.9]
        },
        transition: { 
          duration: 3, 
          repeat: Infinity,
          ease: "easeInOut"
        }
      };
    }
    
    if (animationStyle === 'interactive') {
      // Use the technical animation style from gt-animations
      const animation = avatarAnimations.technical[state] || avatarAnimations.technical.idle;
      // Ensure animation properties are properly formatted for motion.div
      return {
        animate: animation,
        transition: animation.transition
      };
    }
    
    return {};
  };

  return (
    <motion.div
      className={cn(
        sizeClasses[size],
        "rounded-xl overflow-hidden border-2 border-gray-200",
        className
      )}
      {...getAnimation()}
    >
      {iconUrl ? (
        <img 
          src={iconUrl} 
          alt="Agent icon"
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <Bot className={cn(
            "text-white",
            size === 'small' && "w-4 h-4",
            size === 'medium' && "w-8 h-8",
            size === 'large' && "w-12 h-12"
          )} />
        </div>
      )}
    </motion.div>
  );
}