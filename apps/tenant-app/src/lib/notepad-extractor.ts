interface AINotePadContent {
  type: 'code' | 'mermaid' | 'text' | 'json' | 'html' | 'markdown';
  content: string;
  language?: string;
  title?: string;
}

// Cache for extraction results to avoid re-parsing on every render
const extractionCache = new Map<string, {
  segments: Array<{type: 'text' | 'notepad', content: string, notepadData?: AINotePadContent}>,
  hasNotepads: boolean
}>();

export function extractNotePadContent(text: string): {
  segments: Array<{type: 'text' | 'notepad', content: string, notepadData?: AINotePadContent}>,
  hasNotepads: boolean
} {
  // Check cache first
  if (extractionCache.has(text)) {
    return extractionCache.get(text)!;
  }
  const segments: Array<{type: 'text' | 'notepad', content: string, notepadData?: AINotePadContent}> = [];
  
  // Pattern to match code blocks with language
  const codeBlockPattern = /```(\w+)?\n([\s\S]*?)```/g;
  
  let lastIndex = 0;
  let match;
  let hasNotepads = false;

  while ((match = codeBlockPattern.exec(text)) !== null) {
    const [fullMatch, language = 'text', content] = match;
    
    // Add text before this code block
    if (match.index > lastIndex) {
      const textBefore = text.slice(lastIndex, match.index);
      if (textBefore.trim()) {
        segments.push({
          type: 'text',
          content: textBefore
        });
      }
    }
    
    // Determine if this should go in a notepad
    const shouldExtract = shouldExtractToNotepad(language, content);
    
    if (shouldExtract) {
      const type = getContentType(language);
      const title = generateTitle(type, language, content);
      
      segments.push({
        type: 'notepad',
        content: '', // Empty content for notepad segments
        notepadData: {
          type,
          content: content.trim(),
          language: language || undefined,
          title
        }
      });
      hasNotepads = true;
    } else {
      // Keep as regular text/code
      segments.push({
        type: 'text',
        content: fullMatch
      });
    }
    
    lastIndex = match.index + fullMatch.length;
  }
  
  // Add remaining text after last match
  if (lastIndex < text.length) {
    const remainingText = text.slice(lastIndex);
    if (remainingText.trim()) {
      segments.push({
        type: 'text',
        content: remainingText
      });
    }
  }
  
  // If no code blocks were found, return the original text as a single segment
  if (segments.length === 0) {
    segments.push({
      type: 'text',
      content: text
    });
  }

  // Cache the result before returning
  const result = { segments, hasNotepads };
  extractionCache.set(text, result);

  return result;
}

function shouldExtractToNotepad(language: string, content: string): boolean {
  // Extract if it's a Mermaid diagram
  if (language === 'mermaid' || language === 'mmd') {
    return true;
  }
  
  // Extract if it's a long code block (more than 10 lines)
  if (content.split('\n').length > 10) {
    return true;
  }
  
  // Extract if it's HTML content
  if (language === 'html' || content.includes('<html') || content.includes('<!DOCTYPE')) {
    return true;
  }
  
  // Extract if it's JSON and more than 5 lines
  if (language === 'json' && content.split('\n').length > 5) {
    return true;
  }
  
  // Extract if it contains complex structures
  if (content.includes('function') && content.includes('{') && content.split('\n').length > 8) {
    return true;
  }
  
  return false;
}

function getContentType(language: string): AINotePadContent['type'] {
  switch (language) {
    case 'mermaid':
    case 'mmd':
      return 'mermaid';
    case 'json':
      return 'json';
    case 'html':
      return 'html';
    case 'markdown':
    case 'md':
      return 'markdown';
    default:
      return 'code';
  }
}

function generateTitle(type: AINotePadContent['type'], language?: string, content?: string): string {
  switch (type) {
    case 'mermaid':
      // Try to detect mermaid diagram type
      if (content?.includes('graph')) return 'Flowchart';
      if (content?.includes('sequenceDiagram')) return 'Sequence Diagram';
      if (content?.includes('pie')) return 'Pie Chart';
      if (content?.includes('gantt')) return 'Gantt Chart';
      return 'Mermaid Diagram';
    
    case 'json':
      return 'JSON Data';
    
    case 'html':
      return 'HTML Document';
    
    case 'markdown':
      return 'Markdown Document';
    
    case 'code':
      if (language) {
        return `${language.charAt(0).toUpperCase() + language.slice(1)} Code`;
      }
      return 'Code Sample';
    
    default:
      return 'Text Content';
  }
}