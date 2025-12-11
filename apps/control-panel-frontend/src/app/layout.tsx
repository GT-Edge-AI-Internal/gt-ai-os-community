import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/lib/providers';
import { Toaster } from 'react-hot-toast';
import Script from 'next/script';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'GT 2.0 Control Panel',
  description: 'Enterprise AI as a Service Platform - Control Panel',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <Script id="disable-console" strategy="beforeInteractive">
          {`
            // Disable console logs in production
            if (typeof window !== 'undefined' && '${process.env.NEXT_PUBLIC_ENVIRONMENT}' === 'production') {
              const noop = function() {};
              ['log', 'debug', 'info', 'warn'].forEach(function(method) {
                console[method] = noop;
              });
            }
          `}
        </Script>
      </head>
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: 'hsl(var(--card))',
                color: 'hsl(var(--card-foreground))',
                border: '1px solid hsl(var(--border))',
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}