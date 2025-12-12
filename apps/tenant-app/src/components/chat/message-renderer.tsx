'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AINotepad } from '@/components/ui/ai-notepad';
import { extractNotePadContent } from '@/lib/notepad-extractor';

interface MessageRendererProps {
  content: string;
  messageId: number;
}

export const MessageRenderer = React.memo(({ content, messageId }: MessageRendererProps) => {
  // Extract segmented content from the message
  const { segments, hasNotepads } = extractNotePadContent(content);

  // Shared markdown components configuration
  const markdownComponents = {
    p: ({ children, ...props }: any) => <div className="mb-4 last:mb-0 break-words" {...props}>{children}</div>,
    dl: ({ children }: any) => <div className="my-4 break-words">{children}</div>,
    dt: ({ children }: any) => <strong className="block mt-2 break-words">{children}</strong>,
    dd: ({ children }: any) => <div className="ml-4 mb-2 break-words">{children}</div>,
    h1: ({ children, ...props }: any) => <h1 className="break-words" {...props}>{children}</h1>,
    h2: ({ children, ...props }: any) => <h2 className="break-words" {...props}>{children}</h2>,
    h3: ({ children, ...props }: any) => <h3 className="break-words" {...props}>{children}</h3>,
    h4: ({ children, ...props }: any) => <h4 className="break-words" {...props}>{children}</h4>,
    h5: ({ children, ...props }: any) => <h5 className="break-words" {...props}>{children}</h5>,
    h6: ({ children, ...props }: any) => <h6 className="break-words" {...props}>{children}</h6>,
    code: ({ children, className, ...props }: any) => {
      // Get actual text content - children can be string or array
      const content = Array.isArray(children) ? children[0] : children;
      const textContent = typeof content === 'string' ? content : String(content || '');

      // Inline code: no className (language) and no newlines in content
      const isInline = !className && !textContent.includes('\n');

      if (isInline) {
        return <code className="break-all px-1 py-0.5 bg-gray-100 rounded text-sm font-mono" {...props}>{children}</code>;
      }
      return <code className="break-all px-1 py-0.5 bg-gray-100 rounded text-sm block my-2 p-2 font-mono" {...props}>{children}</code>;
    },
    pre: ({ children }: any) => <>{children}</>,
    img: ({ src, alt, ...props }: any) => <img src={src} alt={alt} className="max-w-full h-auto" {...props} />,
    table: ({ children, ...props }: any) => (
      <div className="overflow-x-auto max-w-full">
        <table className="min-w-full table-auto break-words" {...props}>{children}</table>
      </div>
    ),
    li: ({ children, ...props }: any) => <li className="break-words" {...props}>{children}</li>,
    blockquote: ({ children, ...props }: any) => <blockquote className="break-words border-l-4 border-blue-500 pl-4 italic my-4" {...props}>{children}</blockquote>,
    sup: ({ children, ...props }: any) => <sup className="break-words" {...props}>{children}</sup>,
    sub: ({ children, ...props }: any) => <sub className="break-words" {...props}>{children}</sub>,
    a: ({ href, children, ...props }: any) => (
      <a
        href={href}
        className="break-words text-blue-600 hover:text-blue-800 underline"
        target={href?.startsWith('http') ? '_blank' : undefined}
        rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
        {...props}
      >
        {children}
      </a>
    ),
    div: ({ children, ...props }: any) => <div className="break-words overflow-hidden" {...props}>{children}</div>,
  };

  // If no notepads needed, render normally
  if (!hasNotepads) {
    return (
      <div className="prose prose-sm max-w-none prose-gray break-words overflow-hidden">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          className="text-gt-gray-900 leading-relaxed"
          skipHtml={true}
          disallowedElements={['script', 'style', 'iframe', 'object', 'embed', 'html']}
          unwrapDisallowed={true}
          urlTransform={(href) => href}
          components={markdownComponents}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  // Render segments inline
  return (
    <div className="prose prose-sm max-w-none prose-gray break-words overflow-hidden">
      {segments.map((segment, index) => {
        if (segment.type === 'notepad' && segment.notepadData) {
          return (
            <div key={`${messageId}-segment-${index}`} className="my-4">
              <AINotepad
                contents={[segment.notepadData]}
                title={segment.notepadData.title}
                className="w-full"
              />
            </div>
          );
        } else {
          return (
            <div key={`${messageId}-segment-${index}`}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                className="text-gt-gray-900 leading-relaxed"
                skipHtml={true}
                disallowedElements={['script', 'style', 'iframe', 'object', 'embed', 'html']}
                unwrapDisallowed={true}
                urlTransform={(href) => href}
                components={markdownComponents}
              >
                {segment.content}
              </ReactMarkdown>
            </div>
          );
        }
      })}
    </div>
  );
});