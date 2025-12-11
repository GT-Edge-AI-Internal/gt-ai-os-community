import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/lib/providers';

const inter = Inter({ subsets: ['latin'] });

// Viewport must be exported separately in Next.js 14+
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export const metadata: Metadata = {
  title: {
    template: 'GT AI OS | %s',
    default: 'GT AI OS'
  },
  description: 'Your intelligent AI agent for enterprise workflows and decision-making',
  keywords: ['AI', 'agent', 'enterprise', 'chat', 'documents', 'productivity'],
  authors: [{ name: 'GT Edge AI' }],
  robots: 'noindex, nofollow', // Tenant apps should not be indexed
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.png',
    shortcut: '/favicon.png',
    apple: '/gt-logo.png'
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'GT AI OS'
  }
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className="h-full">
      <head>
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="format-detection" content="telephone=no" />
        <link rel="icon" href="/gt-small-logo.png" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        {/* Console log suppression - controlled by NEXT_PUBLIC_DISABLE_CONSOLE_LOGS */}
        {process.env.NEXT_PUBLIC_DISABLE_CONSOLE_LOGS === 'true' && (
          <script
            dangerouslySetInnerHTML={{
              __html: `
                (function() {
                  // Override console methods to suppress logs
                  // Keep error and warn for critical issues
                  console.log = function() {};
                  console.debug = function() {};
                  console.info = function() {};
                })();
              `,
            }}
          />
        )}
      </head>
      <body className={`${inter.className} h-full antialiased`}>
        <Providers>
          <div className="flex flex-col h-full bg-gt-white text-gt-gray-900">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}