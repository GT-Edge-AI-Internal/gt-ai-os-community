/**
 * Markdown Parser for Export Functionality
 *
 * Uses remark (already installed) for AST-based parsing.
 * Extracts links, formatting, headers, code blocks, and Mermaid diagrams
 * for use in PDF/DOCX exports.
 *
 * GT 2.0 Compliance:
 * - No mocks: Real parsing using remark AST
 * - Fail fast: Throws on critical errors
 * - Zero complexity: Reuses existing remark dependency
 */

import { remark } from 'remark';
import remarkGfm from 'remark-gfm';
import type { Root, Paragraph, Heading, Link, Text, Code, InlineCode, Emphasis, Strong, List, ListItem, Table, Blockquote } from 'mdast';

export interface ParsedLink {
  text: string;
  url: string;
  title?: string;
  position: number;
}

export interface ParsedFormatting {
  type: 'bold' | 'italic' | 'code' | 'strikethrough';
  text: string;
  range: [number, number];
}

export interface ParsedHeader {
  level: 1 | 2 | 3 | 4 | 5 | 6;
  text: string;
  position: number;
}

export interface ParsedCodeBlock {
  language: string | null;
  code: string;
  position: number;
}

export interface ParsedMermaidBlock {
  code: string;
  position: number;
}

export interface ParsedTable {
  headers: string[];
  rows: string[][];
  position: number;
}

export interface ParsedList {
  type: 'ordered' | 'unordered';
  items: string[];
  position: number;
}

export interface ParsedBlockquote {
  text: string;
  position: number;
}

export interface ParsedMarkdown {
  links: ParsedLink[];
  headers: ParsedHeader[];
  codeBlocks: ParsedCodeBlock[];
  mermaidBlocks: ParsedMermaidBlock[];
  tables: ParsedTable[];
  lists: ParsedList[];
  blockquotes: ParsedBlockquote[];
  hasEmoji: boolean;
  hasUnsupportedChars: boolean;
}

/**
 * Extract text content from AST node recursively
 */
function extractText(node: any): string {
  if (node.type === 'text') {
    return node.value;
  }
  if (node.children) {
    return node.children.map(extractText).join('');
  }
  return '';
}

/**
 * Detect emoji in text (common ranges)
 */
function hasEmojiChars(text: string): boolean {
  // Emoji ranges: emoticons, symbols, transport, etc.
  return /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u.test(text);
}

/**
 * Detect potentially unsupported characters (CJK, RTL, etc.)
 */
function hasUnsupportedChars(text: string): boolean {
  // CJK ranges (Chinese, Japanese, Korean)
  const hasCJK = /[\u{4E00}-\u{9FFF}\u{3400}-\u{4DBF}\u{20000}-\u{2A6DF}\u{3040}-\u{309F}\u{30A0}-\u{30FF}\u{AC00}-\u{D7AF}]/u.test(text);

  // RTL ranges (Arabic, Hebrew)
  const hasRTL = /[\u{0600}-\u{06FF}\u{0750}-\u{077F}\u{0590}-\u{05FF}]/u.test(text);

  return hasCJK || hasRTL;
}

/**
 * Parse markdown content into structured data for exports
 */
export function parseMarkdown(content: string): ParsedMarkdown {
  if (!content || typeof content !== 'string') {
    throw new Error('Invalid markdown content: must be a non-empty string');
  }

  const result: ParsedMarkdown = {
    links: [],
    headers: [],
    codeBlocks: [],
    mermaidBlocks: [],
    tables: [],
    lists: [],
    blockquotes: [],
    hasEmoji: hasEmojiChars(content),
    hasUnsupportedChars: hasUnsupportedChars(content),
  };

  try {
    // Parse markdown to AST
    const tree = remark().use(remarkGfm).parse(content);

    // Walk the AST and extract elements
    let position = 0;

    function visit(node: any, parent?: any) {
      position++;

      // Extract links
      if (node.type === 'link') {
        result.links.push({
          text: extractText(node),
          url: node.url,
          title: node.title,
          position,
        });
      }

      // Extract headers
      if (node.type === 'heading') {
        result.headers.push({
          level: node.depth as 1 | 2 | 3 | 4 | 5 | 6,
          text: extractText(node),
          position,
        });
      }

      // Extract code blocks
      if (node.type === 'code') {
        const lang = node.lang || null;

        // Separate Mermaid diagrams from regular code blocks
        if (lang === 'mermaid') {
          result.mermaidBlocks.push({
            code: node.value,
            position,
          });
        } else {
          result.codeBlocks.push({
            language: lang,
            code: node.value,
            position,
          });
        }
      }

      // Extract tables
      if (node.type === 'table') {
        const headers: string[] = [];
        const rows: string[][] = [];

        node.children.forEach((row: any, idx: number) => {
          const cells = row.children.map((cell: any) => extractText(cell));
          if (idx === 0) {
            headers.push(...cells);
          } else {
            rows.push(cells);
          }
        });

        result.tables.push({
          headers,
          rows,
          position,
        });
      }

      // Extract lists
      if (node.type === 'list') {
        const items = node.children.map((item: any) => extractText(item));
        result.lists.push({
          type: node.ordered ? 'ordered' : 'unordered',
          items,
          position,
        });
      }

      // Extract blockquotes
      if (node.type === 'blockquote') {
        result.blockquotes.push({
          text: extractText(node),
          position,
        });
      }

      // Recurse into children
      if (node.children) {
        node.children.forEach((child: any) => visit(child, node));
      }
    }

    visit(tree);

    return result;
  } catch (error) {
    // Fail fast on parsing errors
    throw new Error(`Markdown parsing failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Extract inline formatting from a text node
 * This is used for more granular formatting extraction within paragraphs
 */
export function extractInlineFormatting(node: any): Array<{ type: string; text: string }> {
  const results: Array<{ type: string; text: string }> = [];

  function visit(n: any, currentFormat?: string) {
    if (n.type === 'text') {
      results.push({
        type: currentFormat || 'normal',
        text: n.value,
      });
      return;
    }

    if (n.type === 'strong') {
      n.children.forEach((child: any) => visit(child, 'bold'));
      return;
    }

    if (n.type === 'emphasis') {
      n.children.forEach((child: any) => visit(child, 'italic'));
      return;
    }

    if (n.type === 'inlineCode') {
      results.push({
        type: 'code',
        text: n.value,
      });
      return;
    }

    if (n.type === 'delete') {
      n.children.forEach((child: any) => visit(child, 'strikethrough'));
      return;
    }

    if (n.children) {
      n.children.forEach((child: any) => visit(child, currentFormat));
    }
  }

  visit(node);
  return results;
}

/**
 * Parse markdown and return enriched AST for rendering
 * This provides access to the full remark AST for advanced use cases
 */
export function parseMarkdownToAST(content: string): Root {
  try {
    return remark().use(remarkGfm).parse(content);
  } catch (error) {
    throw new Error(`Failed to parse markdown to AST: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}
