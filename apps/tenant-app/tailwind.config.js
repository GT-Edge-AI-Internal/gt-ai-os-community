/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          css: {
            'code::before': {
              content: '""',
            },
            'code::after': {
              content: '""',
            },
          },
        },
      },
      colors: {
        gt: {
          white: 'var(--gt-white)',
          black: 'var(--gt-black)',
          green: 'var(--gt-green)',
          gray: {
            50: 'var(--gt-gray-50)',
            100: 'var(--gt-gray-100)',
            200: 'var(--gt-gray-200)',
            300: 'var(--gt-gray-300)',
            400: 'var(--gt-gray-400)',
            500: 'var(--gt-gray-500)',
            600: 'var(--gt-gray-600)',
            700: 'var(--gt-gray-700)',
            800: 'var(--gt-gray-800)',
            900: 'var(--gt-gray-900)',
          },
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'SF Pro Display',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'SF Mono',
          'Monaco',
          'Cascadia Code',
          'Roboto Mono',
          'Consolas',
          'monospace',
        ],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-gentle': 'pulseGentle 2s infinite',
        'neural-pulse': 'neuralPulse 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseGentle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        neuralPulse: {
          '0%, 100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
};