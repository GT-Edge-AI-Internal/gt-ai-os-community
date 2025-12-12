/**
 * GT 2.0 Animation Library
 * Apple-inspired physics with AI-specific animations for premium UX
 */

import { Variants, Transition } from 'framer-motion';

// Animation timing functions (Apple-inspired)
export const easing = {
  // Standard Apple easing curve - used for most UI animations
  standard: [0.4, 0.0, 0.2, 1] as [number, number, number, number],
  // Spring physics for interactive elements
  spring: [0.34, 1.56, 0.64, 1] as [number, number, number, number],
  // Smooth deceleration for entering elements
  decelerate: [0.0, 0.0, 0.2, 1] as [number, number, number, number],
  // Quick acceleration for exiting elements
  accelerate: [0.4, 0.0, 1, 1] as [number, number, number, number],
  // Gentle bounce for success states
  bounce: [0.68, -0.55, 0.265, 1.55] as [number, number, number, number],
};

// Neural pulse animation for AI thinking states
export const neuralPulse: Variants = {
  initial: { 
    scale: 1, 
    opacity: 0.3,
  },
  animate: { 
    scale: [1, 1.2, 1],
    opacity: [0.3, 1, 0.3],
    transition: { 
      duration: 1.4,
      repeat: Infinity,
      ease: easing.spring,
    }
  }
};

// Synaptic flow for data connections and network animations
export const synapticFlow: Variants = {
  initial: { 
    pathLength: 0, 
    opacity: 0,
  },
  animate: { 
    pathLength: 1,
    opacity: [0, 1, 1, 0],
    transition: { 
      pathLength: {
        duration: 2,
        ease: "easeInOut",
      },
      opacity: {
        duration: 2,
        times: [0, 0.2, 0.8, 1],
      },
      repeat: Infinity,
    }
  }
};

// Glass morphism fade-in for modern UI elements
export const glassMorphism: Variants = {
  initial: {
    opacity: 0,
    backdropFilter: "blur(0px)",
    background: "rgba(255, 255, 255, 0)",
  },
  animate: {
    opacity: 1,
    backdropFilter: "blur(10px)",
    background: "rgba(255, 255, 255, 0.1)",
    transition: {
      duration: 0.3,
      ease: easing.standard,
    }
  }
};

// Message bubble appearance with bounce
export const messageBubble: Variants = {
  initial: {
    opacity: 0,
    scale: 0.8,
    y: 20,
  },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: easing.bounce,
    }
  },
  exit: {
    opacity: 0,
    scale: 0.9,
    y: -10,
    transition: {
      duration: 0.2,
      ease: easing.accelerate,
    }
  }
};

// Staggered list animation for sequential reveals
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    }
  }
};

export const staggerItem: Variants = {
  initial: {
    opacity: 0,
    x: -20,
  },
  animate: {
    opacity: 1,
    x: 0,
    transition: {
      duration: 0.3,
      ease: easing.decelerate,
    }
  }
};

// Confidence meter animation with color transitions
export const confidenceMeter: Variants = {
  low: {
    width: "25%",
    backgroundColor: "#ef4444",
    transition: { duration: 0.5, ease: easing.standard }
  },
  medium: {
    width: "50%",
    backgroundColor: "#fbbf24",
    transition: { duration: 0.5, ease: easing.standard }
  },
  high: {
    width: "75%",
    backgroundColor: "#4ade80",
    transition: { duration: 0.5, ease: easing.standard }
  },
  veryHigh: {
    width: "100%",
    backgroundColor: "#00d084",
    transition: { duration: 0.5, ease: easing.standard }
  }
};

// Avatar personality animations - each type has unique characteristics
export const avatarAnimations = {
  geometric: {
    idle: {
      rotate: [0, 90, 180, 270, 360],
      transition: {
        duration: 20,
        repeat: Infinity,
        ease: "linear",
      }
    },
    thinking: {
      rotate: [0, -10, 10, -10, 0],
      scale: [1, 1.1, 0.9, 1.1, 1],
      transition: {
        duration: 0.5,
        repeat: Infinity,
        ease: easing.spring,
      }
    },
    speaking: {
      scale: [1, 1.05, 1],
      transition: {
        duration: 0.3,
        repeat: Infinity,
        ease: easing.standard,
      }
    },
    success: {
      scale: [1, 1.2, 1],
      rotate: [0, 360],
      transition: {
        duration: 0.6,
        ease: easing.bounce,
      }
    }
  },
  organic: {
    idle: {
      scale: [1, 1.02, 1],
      transition: {
        duration: 4,
        repeat: Infinity,
        ease: "easeInOut",
      }
    },
    thinking: {
      scale: [1, 1.2, 1.1, 1.2, 1],
      opacity: [1, 0.8, 1, 0.8, 1],
      transition: {
        duration: 2,
        repeat: Infinity,
        ease: easing.decelerate,
      }
    },
    speaking: {
      scale: [1, 1.1, 1.05, 1.1, 1],
      transition: {
        duration: 0.8,
        repeat: Infinity,
        ease: "easeInOut",
      }
    },
    success: {
      scale: [1, 1.3, 1],
      opacity: [1, 0.7, 1],
      transition: {
        duration: 0.8,
        ease: easing.bounce,
      }
    }
  },
  minimal: {
    idle: {
      opacity: [0.7, 1, 0.7],
      transition: {
        duration: 3,
        repeat: Infinity,
        ease: "easeInOut",
      }
    },
    thinking: {
      opacity: [1, 0.3, 1],
      transition: {
        duration: 1,
        repeat: Infinity,
        ease: easing.standard,
      }
    },
    speaking: {
      opacity: [1, 0.9, 1],
      transition: {
        duration: 0.5,
        repeat: Infinity,
        ease: easing.standard,
      }
    },
    success: {
      opacity: [0.7, 1, 0.7],
      scale: [1, 1.1, 1],
      transition: {
        duration: 0.4,
        ease: easing.standard,
      }
    }
  },
  technical: {
    idle: {
      rotateY: [0, 360],
      transition: {
        duration: 10,
        repeat: Infinity,
        ease: "linear",
      }
    },
    thinking: {
      rotateX: [-5, 5, -5],
      rotateY: [-5, 5, -5],
      transition: {
        duration: 0.3,
        repeat: Infinity,
        ease: easing.spring,
      }
    },
    speaking: {
      rotateZ: [-2, 2, -2],
      scale: [1, 1.02, 1],
      transition: {
        duration: 0.2,
        repeat: Infinity,
        ease: easing.standard,
      }
    },
    success: {
      rotateY: [0, 720],
      scale: [1, 1.15, 1],
      transition: {
        duration: 1,
        ease: easing.bounce,
      }
    }
  }
};

// Typing animation for character-by-character text reveal
export const typingReveal = {
  hidden: { 
    opacity: 0,
    display: "none",
  },
  visible: (i: number) => ({
    opacity: 1,
    display: "inline",
    transition: {
      delay: i * 0.03,
      duration: 0.1,
    }
  })
};

// Network graph animations for RAG visualization
export const networkNode: Variants = {
  initial: {
    scale: 0,
    opacity: 0,
  },
  animate: {
    scale: 1,
    opacity: 1,
    transition: {
      duration: 0.5,
      ease: easing.spring,
    }
  },
  hover: {
    scale: 1.2,
    transition: {
      duration: 0.2,
      ease: easing.standard,
    }
  },
  selected: {
    scale: 1.3,
    boxShadow: "0 0 20px rgba(0, 208, 132, 0.5)",
    transition: {
      duration: 0.3,
      ease: easing.spring,
    }
  },
  exit: {
    scale: 0,
    opacity: 0,
    transition: {
      duration: 0.3,
      ease: easing.accelerate,
    }
  }
};

// Citation and reference card animations
export const citationCard: Variants = {
  initial: {
    opacity: 0,
    y: 10,
    scale: 0.95,
  },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.3,
      ease: easing.decelerate,
    }
  },
  hover: {
    y: -2,
    boxShadow: "0 10px 30px rgba(0, 208, 132, 0.15)",
    transition: {
      duration: 0.2,
      ease: easing.standard,
    }
  },
  tap: {
    scale: 0.98,
    transition: {
      duration: 0.1,
    }
  }
};

// Loading skeleton shimmer animation
export const skeleton: Variants = {
  initial: {
    backgroundPosition: "-200% 0",
  },
  animate: {
    backgroundPosition: "200% 0",
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: "linear",
    }
  }
};

// Neural border animation for active/focused elements
export const neuralBorder = {
  initial: {
    borderColor: "rgba(0, 208, 132, 0)",
  },
  animate: {
    borderColor: [
      "rgba(0, 208, 132, 0)",
      "rgba(0, 208, 132, 0.5)",
      "rgba(0, 208, 132, 1)",
      "rgba(0, 208, 132, 0.5)",
      "rgba(0, 208, 132, 0)",
    ],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut",
    }
  }
};

// Slide transitions for panel and modal animations
export const slideUp: Variants = {
  initial: {
    y: "100%",
    opacity: 0,
  },
  animate: {
    y: 0,
    opacity: 1,
    transition: {
      duration: 0.4,
      ease: easing.decelerate,
    }
  },
  exit: {
    y: "100%",
    opacity: 0,
    transition: {
      duration: 0.3,
      ease: easing.accelerate,
    }
  }
};

export const slideRight: Variants = {
  initial: {
    x: "-100%",
    opacity: 0,
  },
  animate: {
    x: 0,
    opacity: 1,
    transition: {
      duration: 0.4,
      ease: easing.decelerate,
    }
  },
  exit: {
    x: "-100%",
    opacity: 0,
    transition: {
      duration: 0.3,
      ease: easing.accelerate,
    }
  }
};

export const slideLeft: Variants = {
  initial: {
    x: "100%",
    opacity: 0,
  },
  animate: {
    x: 0,
    opacity: 1,
    transition: {
      duration: 0.4,
      ease: easing.decelerate,
    }
  },
  exit: {
    x: "100%",
    opacity: 0,
    transition: {
      duration: 0.3,
      ease: easing.accelerate,
    }
  }
};

// Scale animations for buttons and interactive elements
export const scaleOnHover: Variants = {
  initial: { scale: 1 },
  hover: { 
    scale: 1.05,
    transition: {
      duration: 0.2,
      ease: easing.standard,
    }
  },
  tap: { 
    scale: 0.95,
    transition: {
      duration: 0.1,
    }
  }
};

// Fade and blur effects for overlays
export const fadeBlur: Variants = {
  initial: {
    opacity: 0,
    backdropFilter: "blur(0px)",
  },
  animate: {
    opacity: 1,
    backdropFilter: "blur(8px)",
    transition: {
      duration: 0.2,
      ease: easing.standard,
    }
  },
  exit: {
    opacity: 0,
    backdropFilter: "blur(0px)",
    transition: {
      duration: 0.2,
      ease: easing.accelerate,
    }
  }
};

// Export animation utilities
export const animationUtils = {
  // Check if user prefers reduced motion
  shouldReduceMotion: (): boolean => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  },
  
  // Get appropriate animation based on reduced motion preference
  getAnimation: (animation: Variants): Variants => {
    if (animationUtils.shouldReduceMotion()) {
      return {
        initial: animation.initial,
        animate: {
          ...animation.animate,
          transition: { duration: 0 }
        }
      };
    }
    return animation;
  },
  
  // Create custom spring animation with physics
  createSpring: (stiffness = 300, damping = 30, mass = 1): Transition => ({
    type: "spring",
    stiffness,
    damping,
    mass,
  }),
  
  // Create custom tween animation
  createTween: (duration = 0.3, ease = easing.standard): Transition => ({
    type: "tween",
    duration,
    ease,
  }),
  
  // Create staggered animation for lists
  createStagger: (staggerDelay = 0.1, delayChildren = 0): Transition => ({
    staggerChildren: staggerDelay,
    delayChildren,
  }),
  
  // Get confidence animation based on score
  getConfidenceAnimation: (score: number): string => {
    if (score > 0.9) return 'veryHigh';
    if (score > 0.7) return 'high';
    if (score > 0.5) return 'medium';
    return 'low';
  },
  
  // Get personality animation set
  getPersonalityAnimations: (personality: 'geometric' | 'organic' | 'minimal' | 'technical') => {
    return avatarAnimations[personality] || avatarAnimations.minimal;
  },
  
  // Create dynamic color animation
  createColorTransition: (fromColor: string, toColor: string, duration = 0.3): Transition => ({
    duration,
    ease: easing.standard,
  }),
};

// Preset animation combinations for common use cases
export const presets = {
  // Card hover effect
  cardHover: {
    ...scaleOnHover,
    hover: {
      ...scaleOnHover.hover,
      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.1)",
    }
  },
  
  // Modal enter/exit
  modal: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { 
      opacity: 1, 
      scale: 1,
      transition: {
        duration: 0.2,
        ease: easing.decelerate,
      }
    },
    exit: { 
      opacity: 0, 
      scale: 0.95,
      transition: {
        duration: 0.15,
        ease: easing.accelerate,
      }
    }
  },
  
  // Success notification
  successNotification: {
    initial: { opacity: 0, x: 100, scale: 0.3 },
    animate: { 
      opacity: 1, 
      x: 0,
      scale: 1,
      transition: {
        type: "spring",
        stiffness: 500,
        damping: 30,
      }
    },
    exit: { 
      opacity: 0, 
      x: 100,
      transition: {
        duration: 0.2,
        ease: easing.accelerate,
      }
    }
  },
};

// Export everything for easy importing
export default {
  easing,
  neuralPulse,
  synapticFlow,
  glassMorphism,
  messageBubble,
  staggerContainer,
  staggerItem,
  confidenceMeter,
  avatarAnimations,
  typingReveal,
  networkNode,
  citationCard,
  skeleton,
  neuralBorder,
  slideUp,
  slideRight,
  slideLeft,
  scaleOnHover,
  fadeBlur,
  animationUtils,
  presets,
};