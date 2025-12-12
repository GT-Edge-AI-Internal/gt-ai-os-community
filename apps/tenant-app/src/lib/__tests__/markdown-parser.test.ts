/**
 * Unit Tests for Markdown Parser
 *
 * Tests AST-based parsing for export functionality
 */

import { parseMarkdown, extractInlineFormatting, parseMarkdownToAST } from '../markdown-parser';

describe('parseMarkdown', () => {
  describe('Links', () => {
    it('should extract simple links', () => {
      const content = 'This is a [test link](https://example.com) in text.';
      const result = parseMarkdown(content);

      expect(result.links).toHaveLength(1);
      expect(result.links[0]).toMatchObject({
        text: 'test link',
        url: 'https://example.com',
      });
    });

    it('should extract multiple links', () => {
      const content = '[Link 1](https://example.com) and [Link 2](https://google.com)';
      const result = parseMarkdown(content);

      expect(result.links).toHaveLength(2);
      expect(result.links[0].url).toBe('https://example.com');
      expect(result.links[1].url).toBe('https://google.com');
    });

    it('should extract links with titles', () => {
      const content = '[Link](https://example.com "Title text")';
      const result = parseMarkdown(content);

      expect(result.links[0].title).toBe('Title text');
    });

    it('should handle relative links', () => {
      const content = '[Docs](/docs/guide)';
      const result = parseMarkdown(content);

      expect(result.links[0].url).toBe('/docs/guide');
    });
  });

  describe('Headers', () => {
    it('should extract headers of all levels', () => {
      const content = `
# H1
## H2
### H3
#### H4
##### H5
###### H6
      `;
      const result = parseMarkdown(content);

      expect(result.headers).toHaveLength(6);
      expect(result.headers[0]).toMatchObject({ level: 1, text: 'H1' });
      expect(result.headers[1]).toMatchObject({ level: 2, text: 'H2' });
      expect(result.headers[5]).toMatchObject({ level: 6, text: 'H6' });
    });

    it('should extract header text with inline formatting', () => {
      const content = '## Header with **bold** text';
      const result = parseMarkdown(content);

      expect(result.headers[0].text).toBe('Header with bold text');
    });
  });

  describe('Code Blocks', () => {
    it('should extract code blocks with language', () => {
      const content = '```python\nprint("Hello")\n```';
      const result = parseMarkdown(content);

      expect(result.codeBlocks).toHaveLength(1);
      expect(result.codeBlocks[0]).toMatchObject({
        language: 'python',
        code: 'print("Hello")',
      });
    });

    it('should extract code blocks without language', () => {
      const content = '```\nplain code\n```';
      const result = parseMarkdown(content);

      expect(result.codeBlocks[0].language).toBeNull();
      expect(result.codeBlocks[0].code).toBe('plain code');
    });

    it('should separate Mermaid diagrams from regular code', () => {
      const content = `
\`\`\`python
print("code")
\`\`\`

\`\`\`mermaid
graph TD
  A --> B
\`\`\`
      `;
      const result = parseMarkdown(content);

      expect(result.codeBlocks).toHaveLength(1);
      expect(result.mermaidBlocks).toHaveLength(1);
      expect(result.codeBlocks[0].language).toBe('python');
      expect(result.mermaidBlocks[0].code).toContain('graph TD');
    });
  });

  describe('Mermaid Diagrams', () => {
    it('should extract Mermaid diagram code', () => {
      const content = `
\`\`\`mermaid
graph TD
    A[Start] --> B[End]
\`\`\`
      `;
      const result = parseMarkdown(content);

      expect(result.mermaidBlocks).toHaveLength(1);
      expect(result.mermaidBlocks[0].code).toContain('graph TD');
      expect(result.mermaidBlocks[0].code).toContain('A[Start]');
    });

    it('should extract multiple Mermaid diagrams', () => {
      const content = `
\`\`\`mermaid
graph TD
  A --> B
\`\`\`

\`\`\`mermaid
sequenceDiagram
  User->>System: Request
\`\`\`
      `;
      const result = parseMarkdown(content);

      expect(result.mermaidBlocks).toHaveLength(2);
      expect(result.mermaidBlocks[0].code).toContain('graph TD');
      expect(result.mermaidBlocks[1].code).toContain('sequenceDiagram');
    });
  });

  describe('Tables', () => {
    it('should extract table headers and rows', () => {
      const content = `
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
      `;
      const result = parseMarkdown(content);

      expect(result.tables).toHaveLength(1);
      expect(result.tables[0].headers).toEqual(['Header 1', 'Header 2']);
      expect(result.tables[0].rows).toHaveLength(2);
      expect(result.tables[0].rows[0]).toEqual(['Cell 1', 'Cell 2']);
    });
  });

  describe('Lists', () => {
    it('should extract unordered lists', () => {
      const content = `
- Item 1
- Item 2
- Item 3
      `;
      const result = parseMarkdown(content);

      expect(result.lists).toHaveLength(1);
      expect(result.lists[0].type).toBe('unordered');
      expect(result.lists[0].items).toHaveLength(3);
    });

    it('should extract ordered lists', () => {
      const content = `
1. First
2. Second
3. Third
      `;
      const result = parseMarkdown(content);

      expect(result.lists).toHaveLength(1);
      expect(result.lists[0].type).toBe('ordered');
      expect(result.lists[0].items).toHaveLength(3);
    });
  });

  describe('Blockquotes', () => {
    it('should extract blockquote text', () => {
      const content = '> This is a quote';
      const result = parseMarkdown(content);

      expect(result.blockquotes).toHaveLength(1);
      expect(result.blockquotes[0].text).toBe('This is a quote');
    });
  });

  describe('Character Detection', () => {
    it('should detect emoji', () => {
      const content = 'Hello 😀 world 🚀';
      const result = parseMarkdown(content);

      expect(result.hasEmoji).toBe(true);
    });

    it('should not detect emoji in regular text', () => {
      const content = 'Hello world';
      const result = parseMarkdown(content);

      expect(result.hasEmoji).toBe(false);
    });

    it('should detect CJK characters', () => {
      const content = 'Hello 你好 world';
      const result = parseMarkdown(content);

      expect(result.hasUnsupportedChars).toBe(true);
    });

    it('should detect RTL characters', () => {
      const content = 'Hello مرحبا world';
      const result = parseMarkdown(content);

      expect(result.hasUnsupportedChars).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('should throw on invalid input', () => {
      expect(() => parseMarkdown('')).toThrow('Invalid markdown content');
      expect(() => parseMarkdown(null as any)).toThrow('Invalid markdown content');
      expect(() => parseMarkdown(undefined as any)).toThrow('Invalid markdown content');
    });
  });

  describe('Edge Cases', () => {
    it('should handle nested formatting', () => {
      const content = '**bold with *italic* inside**';
      const result = parseMarkdown(content);

      // Parser should extract text even with nested formatting
      expect(result).toBeDefined();
    });

    it('should handle empty code blocks', () => {
      const content = '```\n\n```';
      const result = parseMarkdown(content);

      expect(result.codeBlocks).toHaveLength(1);
      expect(result.codeBlocks[0].code).toBe('');
    });

    it('should handle malformed markdown gracefully', () => {
      const content = '[Unclosed link(https://example.com';

      // Should not throw, remark is forgiving
      const result = parseMarkdown(content);
      expect(result).toBeDefined();
    });
  });
});

describe('parseMarkdownToAST', () => {
  it('should return valid AST', () => {
    const content = '# Header\n\nParagraph';
    const ast = parseMarkdownToAST(content);

    expect(ast.type).toBe('root');
    expect(ast.children).toBeDefined();
    expect(ast.children.length).toBeGreaterThan(0);
  });

  it('should throw on parsing errors', () => {
    // remark is very forgiving, so this is hard to trigger
    // but we test the error handling path exists
    expect(() => parseMarkdownToAST(null as any)).toThrow();
  });
});
