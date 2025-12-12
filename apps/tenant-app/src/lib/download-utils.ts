import { saveAs } from 'file-saver';
import { Document, Packer, Paragraph, TextRun, HeadingLevel, ExternalHyperlink, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType, LevelFormat, convertInchesToTwip, ShadingType } from 'docx';
import { parseMarkdown } from './markdown-parser';
import { renderMultipleDiagrams, createDiagramPlaceholder } from './mermaid-renderer';

export interface DownloadOptions {
  filename?: string;
  format: 'txt' | 'docx' | 'md';
  content: string;
  title?: string;
}

// Convert markdown to clean text
function markdownToText(content: string): string {
  return content
    // Remove code blocks
    .replace(/```[\s\S]*?```/g, '[Code Block]')
    // Remove inline code
    .replace(/`([^`]+)`/g, '$1')
    // Remove links but keep text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Remove images
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '[Image: $1]')
    // Remove headers
    .replace(/^#{1,6}\s+/gm, '')
    // Remove bold/italic
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    // Remove blockquotes
    .replace(/^>\s*/gm, '')
    // Clean up extra whitespace
    .replace(/\n\s*\n/g, '\n\n')
    .trim();
}

// Helper interface for inline formatting segments
interface TextSegment {
  text: string;
  bold?: boolean;
  italic?: boolean;
  link?: string;
  code?: boolean;
}

// Parse inline markdown formatting (bold, italic, links) - Used by DOCX export
function parseInlineFormatting(line: string): TextSegment[] {
  // Handle empty or whitespace-only lines
  if (!line || !line.trim()) {
    return [{ text: line }];
  }

  const segments: TextSegment[] = [];
  let currentPos = 0;

  // Combined regex for inline code (`text`), bold (**text**), italic (*text*), and links ([text](url))
  // Order matters: match ` first, then ** before * to avoid conflicts
  // Groups: 1-2: inline code, 3-4: bold, 5-6: italic, 7-8: links
  const regex = /(`([^`\n]+?)`)|(\*\*([^*\n]+?)\*\*)|(?<!\*)(\*([^*\n]+?)\*)(?!\*)|\[([^\]\n]+)\]\(([^)\n]+)\)/g;
  let match;
  let iterations = 0;
  const MAX_ITERATIONS = 1000; // Prevent infinite loops

  try {
    while ((match = regex.exec(line)) !== null && iterations < MAX_ITERATIONS) {
      iterations++;

      // Add text before this match
      if (match.index > currentPos) {
        const beforeText = line.substring(currentPos, match.index);
        if (beforeText) {
          segments.push({ text: beforeText });
        }
      }

      if (match[1]) {
        // Inline code: `text`
        segments.push({ text: match[2], code: true });
      } else if (match[3]) {
        // Bold: **text**
        segments.push({ text: match[4], bold: true });
      } else if (match[5]) {
        // Italic: *text* (but not part of **)
        segments.push({ text: match[6], italic: true });
      } else if (match[7]) {
        // Link: [text](url)
        segments.push({ text: match[7], link: match[8] });
      }

      currentPos = regex.lastIndex;
    }

    // Add remaining text after last match
    if (currentPos < line.length) {
      const remainingText = line.substring(currentPos);
      if (remainingText) {
        segments.push({ text: remainingText });
      }
    }

    // If no formatting found, return original line as single segment
    return segments.length > 0 ? segments : [{ text: line }];
  } catch (error) {
    // If regex fails, return original line as plain text
    console.warn('parseInlineFormatting failed:', error);
    return [{ text: line }];
  }
}

export async function downloadContent(options: DownloadOptions): Promise<void> {
  const { content, format, filename, title } = options;
  const timestamp = new Date().toISOString().split('T')[0];
  const defaultFilename = filename || `gt-chat-response-${timestamp}`;
  
  try {
    switch (format) {
      case 'txt': {
        const textContent = markdownToText(content);
        const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
        saveAs(blob, `${defaultFilename}.txt`);
        break;
      }

      case 'md': {
        const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
        saveAs(blob, `${defaultFilename}.md`);
        break;
      }

      case 'docx': {
        // Parse markdown for enhanced rendering
        const parsed = parseMarkdown(content);

        // Render Mermaid diagrams to PNG (if any)
        const diagramResults = parsed.mermaidBlocks.length > 0
          ? await renderMultipleDiagrams(parsed.mermaidBlocks.map(b => b.code))
          : [];

        let diagramIndex = 0;

        const children: (Paragraph | Table)[] = [];

        // Add title if provided
        if (title) {
          children.push(
            new Paragraph({
              children: [new TextRun({ text: title, bold: true, size: 32 })],
              heading: HeadingLevel.HEADING_1,
              spacing: { after: 400 },
            })
          );
        }

        // Process content line by line with formatting
        const lines = content.split('\n');
        let currentParagraphRuns: Array<TextRun | ExternalHyperlink> = [];
        let inCodeBlock = false;
        let codeBlockLang = '';
        let codeBlockContent: string[] = [];
        let inTable = false;
        let tableRows: TableRow[] = [];
        let tableColumnCount = 0;

        const headingLevels = [
          HeadingLevel.HEADING_1,
          HeadingLevel.HEADING_2,
          HeadingLevel.HEADING_3,
          HeadingLevel.HEADING_4,
          HeadingLevel.HEADING_5,
          HeadingLevel.HEADING_6,
        ];

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];

          // Empty line - flush current paragraph
          if (!line.trim()) {
            if (currentParagraphRuns.length > 0) {
              children.push(
                new Paragraph({
                  children: currentParagraphRuns,
                  spacing: { after: 200 },
                })
              );
              currentParagraphRuns = [];
            }
            continue;
          }

          // Detect code block start/end
          if (line.startsWith('```')) {
            // Flush current paragraph
            if (currentParagraphRuns.length > 0) {
              children.push(new Paragraph({ children: currentParagraphRuns }));
              currentParagraphRuns = [];
            }

            if (!inCodeBlock) {
              // Start of code block
              inCodeBlock = true;
              codeBlockLang = line.substring(3).trim();
              continue;
            } else {
              // End of code block
              if (codeBlockLang === 'mermaid' && diagramIndex < diagramResults.length) {
                // Render Mermaid diagram as image
                const result = diagramResults[diagramIndex];
                diagramIndex++;

                if (result.success && result.data) {
                  // Convert base64 PNG to Uint8Array (browser-compatible, not Buffer)
                  const base64Data = result.data.split(',')[1];
                  const binaryString = atob(base64Data);
                  const bytes = new Uint8Array(binaryString.length);
                  for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                  }

                  // Calculate dimensions (max 6.5 inches width for Letter size with 1" margins)
                  const PAGE_WIDTH_INCHES = 6.5;
                  const DPI = 96;
                  const maxWidthPixels = PAGE_WIDTH_INCHES * DPI;

                  const imgWidth = result.width || 800;
                  const imgHeight = result.height || 600;
                  const aspectRatio = imgHeight / imgWidth;

                  let renderWidth = Math.min(imgWidth, maxWidthPixels);
                  let renderHeight = renderWidth * aspectRatio;

                  // Add image to document
                  children.push(
                    new Paragraph({
                      children: [
                        new ImageRun({
                          data: bytes,
                          transformation: {
                            width: renderWidth,
                            height: renderHeight,
                          },
                        }),
                      ],
                      spacing: { before: 200, after: 200 },
                    })
                  );
                } else {
                  // Diagram failed - show placeholder
                  const placeholder = createDiagramPlaceholder(result.error);
                  children.push(
                    new Paragraph({
                      children: [new TextRun({ text: placeholder, color: 'FF0000' })],
                      spacing: { after: 200 },
                    })
                  );
                  console.warn(`DOCX export: ${placeholder}`);
                }
              } else if (codeBlockContent.length > 0) {
                // Render non-mermaid code block content
                children.push(
                  new Paragraph({
                    children: [
                      new TextRun({
                        text: codeBlockContent.join('\n'),
                        font: 'Courier New',
                        size: 20, // 10pt
                        color: '000000', // Black text - required for visibility on gray background
                      }),
                    ],
                    shading: { fill: 'E5E7EB', type: ShadingType.SOLID },
                    spacing: { before: 200, after: 200 },
                  })
                );
              }
              inCodeBlock = false;
              codeBlockLang = '';
              codeBlockContent = [];
              continue;
            }
          }

          // Accumulate content inside code blocks (mermaid is handled separately via diagramResults)
          if (inCodeBlock) {
            if (codeBlockLang !== 'mermaid') {
              codeBlockContent.push(line);
            }
            continue;
          }

          // Check for headers
          const headerMatch = line.match(/^(#{1,6})\s+(.+)/);
          if (headerMatch) {
            // Flush current paragraph
            if (currentParagraphRuns.length > 0) {
              children.push(new Paragraph({ children: currentParagraphRuns }));
              currentParagraphRuns = [];
            }

            // Flush any open table before starting header
            if (inTable && tableRows.length > 0) {
              const totalWidth = 9360;
              const columnWidth = Math.floor(totalWidth / tableColumnCount);
              const columnWidths = Array(tableColumnCount).fill(columnWidth);

              children.push(new Table({
                rows: tableRows,
                width: { size: totalWidth, type: WidthType.DXA },
                columnWidths: columnWidths,
              }));
              tableRows = [];
              tableColumnCount = 0;
              inTable = false;
            }

            const level = headerMatch[1].length;
            const headerText = headerMatch[2];

            children.push(
              new Paragraph({
                text: headerText,
                heading: headingLevels[level - 1],
                spacing: { before: 200, after: 100 },
              })
            );
            continue;
          }

          // Check for numbered list items
          const numberedListMatch = line.match(/^(\s*)(\d+)[\.)]\s+(.+)/);
          if (numberedListMatch) {
            // Flush current paragraph
            if (currentParagraphRuns.length > 0) {
              children.push(new Paragraph({ children: currentParagraphRuns }));
              currentParagraphRuns = [];
            }

            // Flush any open table before starting numbered list
            if (inTable && tableRows.length > 0) {
              const totalWidth = 9360;
              const columnWidth = Math.floor(totalWidth / tableColumnCount);
              const columnWidths = Array(tableColumnCount).fill(columnWidth);

              children.push(new Table({
                rows: tableRows,
                width: { size: totalWidth, type: WidthType.DXA },
                columnWidths: columnWidths,
              }));
              tableRows = [];
              tableColumnCount = 0;
              inTable = false;
            }

            const indentLevel = Math.floor(numberedListMatch[1].length / 2);
            const listText = numberedListMatch[3];

            // Parse inline formatting in list item text
            const segments = parseInlineFormatting(listText);
            const listItemRuns: Array<TextRun | ExternalHyperlink> = [];

            segments.forEach(segment => {
              if (segment.link) {
                listItemRuns.push(
                  new ExternalHyperlink({
                    children: [new TextRun({
                      text: segment.text,
                      color: '0000FF',
                      underline: {}
                    })],
                    link: segment.link,
                  })
                );
              } else {
                listItemRuns.push(
                  new TextRun({
                    text: segment.text,
                    bold: segment.bold,
                    italics: segment.italic,
                    font: segment.code ? 'Courier New' : undefined,
                  })
                );
              }
            });

            children.push(
              new Paragraph({
                children: listItemRuns,
                numbering: { reference: 'default-numbering', level: indentLevel },
                spacing: { after: 100 },
              })
            );
            continue;
          }

          // Check for bullet list items
          const bulletListMatch = line.match(/^(\s*)[-*]\s+(.+)/);
          if (bulletListMatch) {
            // Flush current paragraph
            if (currentParagraphRuns.length > 0) {
              children.push(new Paragraph({ children: currentParagraphRuns }));
              currentParagraphRuns = [];
            }

            // Flush any open table before starting bullet list
            if (inTable && tableRows.length > 0) {
              const totalWidth = 9360;
              const columnWidth = Math.floor(totalWidth / tableColumnCount);
              const columnWidths = Array(tableColumnCount).fill(columnWidth);

              children.push(new Table({
                rows: tableRows,
                width: { size: totalWidth, type: WidthType.DXA },
                columnWidths: columnWidths,
              }));
              tableRows = [];
              tableColumnCount = 0;
              inTable = false;
            }

            const indentLevel = Math.floor(bulletListMatch[1].length / 2);
            const listText = bulletListMatch[2];

            // Parse inline formatting in list item text
            const segments = parseInlineFormatting(listText);
            const listItemRuns: Array<TextRun | ExternalHyperlink> = [];

            segments.forEach(segment => {
              if (segment.link) {
                listItemRuns.push(
                  new ExternalHyperlink({
                    children: [new TextRun({
                      text: segment.text,
                      color: '0000FF',
                      underline: {}
                    })],
                    link: segment.link,
                  })
                );
              } else {
                listItemRuns.push(
                  new TextRun({
                    text: segment.text,
                    bold: segment.bold,
                    italics: segment.italic,
                    font: segment.code ? 'Courier New' : undefined,
                  })
                );
              }
            });

            children.push(
              new Paragraph({
                children: listItemRuns,
                bullet: { level: indentLevel },
                spacing: { after: 100 },
              })
            );
            continue;
          }

          // Check for table rows
          if (line.includes('|') && line.split('|').length > 2) {
            // Skip separator lines (|---|---|)
            if (line.match(/^\|[\s\-\|:]+\|$/)) {
              continue;
            }

            // Flush current paragraph
            if (currentParagraphRuns.length > 0) {
              children.push(new Paragraph({ children: currentParagraphRuns }));
              currentParagraphRuns = [];
            }

            // Parse table cells
            const cells = line
              .split('|')
              .map(cell => cell.trim())
              .filter(cell => cell !== '');

            if (cells.length > 0) {
              // Check if this is a new table (different column count)
              if (inTable && tableColumnCount > 0 && cells.length !== tableColumnCount) {
                // Flush the previous table
                if (tableRows.length > 0) {
                  const totalWidth = 9360;
                  const columnWidth = Math.floor(totalWidth / tableColumnCount);
                  const columnWidths = Array(tableColumnCount).fill(columnWidth);

                  children.push(new Table({
                    rows: tableRows,
                    width: { size: totalWidth, type: WidthType.DXA },
                    columnWidths: columnWidths,
                  }));
                  tableRows = [];
                }
                // Reset for new table
                tableColumnCount = cells.length;
              } else if (!inTable) {
                // Starting a new table
                inTable = true;
                tableColumnCount = cells.length;
              }

              // Create table cells with inline formatting
              const tableCells = cells.map(cell => {
                const cellSegments = parseInlineFormatting(cell);
                const cellRuns: Array<TextRun | ExternalHyperlink> = [];

                cellSegments.forEach(segment => {
                  if (segment.link) {
                    cellRuns.push(
                      new ExternalHyperlink({
                        children: [new TextRun({
                          text: segment.text,
                          color: '0000FF',
                          underline: {}
                        })],
                        link: segment.link,
                      })
                    );
                  } else {
                    cellRuns.push(
                      new TextRun({
                        text: segment.text,
                        bold: segment.bold,
                        italics: segment.italic,
                        font: segment.code ? 'Courier New' : undefined,
                      })
                    );
                  }
                });

                return new TableCell({
                  children: [new Paragraph({
                    children: cellRuns,
                    spacing: { before: 100, after: 100 },
                  })],
                  margins: {
                    top: 100,
                    bottom: 100,
                    left: 100,
                    right: 100,
                  },
                });
              });

              // Add row to table
              tableRows.push(new TableRow({ children: tableCells }));
            }
            continue;
          } else if (inTable) {
            // End of table - flush accumulated rows
            if (tableRows.length > 0) {
              // Calculate equal column widths in DXA (9360 total = 6.5")
              const totalWidth = 9360;
              const columnWidth = Math.floor(totalWidth / tableColumnCount);
              const columnWidths = Array(tableColumnCount).fill(columnWidth);

              children.push(new Table({
                rows: tableRows,
                width: { size: totalWidth, type: WidthType.DXA },
                columnWidths: columnWidths,
              }));
              tableRows = [];
              tableColumnCount = 0;
              inTable = false;
            }
          }

          // Regular text - parse inline formatting
          const segments = parseInlineFormatting(line);

          segments.forEach(segment => {
            if (segment.link) {
              currentParagraphRuns.push(
                new ExternalHyperlink({
                  children: [new TextRun({
                    text: segment.text,
                    color: '0000FF',
                    underline: {}
                  })],
                  link: segment.link,
                })
              );
            } else {
              currentParagraphRuns.push(
                new TextRun({
                  text: segment.text,
                  bold: segment.bold,
                  italics: segment.italic,
                  font: segment.code ? 'Courier New' : undefined,
                })
              );
            }
          });

          // Flush at end of line if next line is empty or last line
          if (i === lines.length - 1 || !lines[i + 1].trim()) {
            children.push(
              new Paragraph({
                children: currentParagraphRuns,
                spacing: { after: 200 },
              })
            );
            currentParagraphRuns = [];
          }
        }

        // Flush any remaining table at end of content
        if (inTable && tableRows.length > 0) {
          // Calculate equal column widths in DXA (9360 total = 6.5")
          const totalWidth = 9360;
          const columnWidth = Math.floor(totalWidth / tableColumnCount);
          const columnWidths = Array(tableColumnCount).fill(columnWidth);

          children.push(new Table({
            rows: tableRows,
            width: { size: totalWidth, type: WidthType.DXA },
            columnWidths: columnWidths,
          }));
        }

        // Create document with numbering configuration
        const doc = new Document({
          numbering: {
            config: [
              {
                reference: 'default-numbering',
                levels: [
                  {
                    level: 0,
                    format: LevelFormat.DECIMAL,
                    text: '%1.',
                    alignment: AlignmentType.START,
                    style: {
                      paragraph: {
                        indent: {
                          left: convertInchesToTwip(0.5),
                          hanging: convertInchesToTwip(0.18)
                        },
                      },
                    },
                  },
                  {
                    level: 1,
                    format: LevelFormat.DECIMAL,
                    text: '%2.',
                    alignment: AlignmentType.START,
                    style: {
                      paragraph: {
                        indent: {
                          left: convertInchesToTwip(1.0),
                          hanging: convertInchesToTwip(0.18)
                        },
                      },
                    },
                  },
                  {
                    level: 2,
                    format: LevelFormat.DECIMAL,
                    text: '%3.',
                    alignment: AlignmentType.START,
                    style: {
                      paragraph: {
                        indent: {
                          left: convertInchesToTwip(1.5),
                          hanging: convertInchesToTwip(0.18)
                        },
                      },
                    },
                  },
                ],
              },
            ],
          },
          sections: [
            {
              properties: {},
              children,
            },
          ],
        });

        // Generate and save DOCX file
        Packer.toBlob(doc).then((blob) => {
          saveAs(blob, `${defaultFilename}.docx`);
        });
        break;
      }

      default:
        throw new Error(`Unsupported format: ${format}`);
    }
  } catch (error) {
    console.error('Download failed:', error);
    throw error;
  }
}

// Detect the best format based on content
export function suggestFormat(content: string): string[] {
  return ['txt', 'md', 'docx'];
}

// Get format description
export function getFormatDescription(format: string): string {
  switch (format) {
    case 'txt': return 'Plain text file';
    case 'md': return 'Markdown file';
    case 'docx': return 'Word document';
    default: return 'Unknown format';
  }
}