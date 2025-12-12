/**
 * Mermaid Diagram Renderer for Export Functionality
 *
 * Converts Mermaid diagram code to PNG images for embedding in PDF/DOCX exports.
 * Uses browser-native Canvas API with size validation and memory management.
 *
 * GT 2.0 Compliance:
 * - No mocks: Real Mermaid rendering
 * - Fail fast: Size validation before conversion
 * - Zero complexity: Client-side only, reuses existing Mermaid library
 */

import mermaid from 'mermaid';

// Browser canvas size limit (32,767px maximum dimension)
const MAX_CANVAS_SIZE = 32000; // Safe limit below browser maximum

export interface DiagramRenderResult {
  success: boolean;
  data?: string; // base64 PNG data URL
  error?: string;
  width?: number;
  height?: number;
}

/**
 * Initialize Mermaid with export-friendly settings
 * Only call this once at module load
 */
let mermaidInitialized = false;

function initializeMermaid() {
  if (mermaidInitialized) return;

  mermaid.initialize({
    startOnLoad: false,
    theme: 'default', // Use default theme for better PDF/print compatibility
    themeVariables: {
      primaryColor: '#3b82f6',
      primaryTextColor: '#1f2937',
      primaryBorderColor: '#1e40af',
      lineColor: '#6b7280',
      secondaryColor: '#e5e7eb',
      tertiaryColor: '#f3f4f6',
    },
    fontFamily: 'Arial, sans-serif', // Standard font for PDF compatibility
    flowchart: {
      useMaxWidth: false,
      htmlLabels: true,
      curve: 'basis',
    },
    sequence: {
      useMaxWidth: false,
      diagramMarginX: 50,
      diagramMarginY: 10,
    },
    suppressErrorRendering: true,
    errorLevel: 'fatal',
    logLevel: 'fatal',
  });

  mermaidInitialized = true;
}

/**
 * Parse SVG dimensions from SVG string
 */
function parseSVGDimensions(svgString: string): { width: number; height: number } {
  const parser = new DOMParser();
  const svgDoc = parser.parseFromString(svgString, 'image/svg+xml');
  const svgElement = svgDoc.documentElement;

  // Try to get width/height from attributes
  let width = parseInt(svgElement.getAttribute('width') || '800');
  let height = parseInt(svgElement.getAttribute('height') || '600');

  // If width/height are percentages or not set, try viewBox
  if (isNaN(width) || isNaN(height)) {
    const viewBox = svgElement.getAttribute('viewBox');
    if (viewBox) {
      const parts = viewBox.split(' ');
      if (parts.length === 4) {
        width = parseInt(parts[2]);
        height = parseInt(parts[3]);
      }
    }
  }

  // Fallback to reasonable defaults
  if (isNaN(width) || width <= 0) width = 800;
  if (isNaN(height) || height <= 0) height = 600;

  return { width, height };
}

/**
 * Convert SVG string to PNG data URL using Canvas API
 */
async function svgToPNG(svgString: string, width: number, height: number): Promise<string> {
  return new Promise((resolve, reject) => {
    // Create canvas
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      reject(new Error('Failed to get canvas context'));
      return;
    }

    // Create image from SVG
    const img = new Image();

    img.onload = () => {
      try {
        // Fill white background (for better PDF rendering)
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        // Draw SVG image
        ctx.drawImage(img, 0, 0, width, height);

        // Convert to PNG data URL
        const pngDataUrl = canvas.toDataURL('image/png');
        resolve(pngDataUrl);
      } catch (error) {
        reject(new Error(`Canvas conversion failed: ${error instanceof Error ? error.message : 'Unknown error'}`));
      }
    };

    img.onerror = () => {
      reject(new Error('Failed to load SVG image'));
    };

    // CRITICAL FIX: Use base64 data URL directly to avoid canvas tainting
    // Using createObjectURL causes CORS issues and taints the canvas
    try {
      // Encode SVG to base64
      const base64 = btoa(unescape(encodeURIComponent(svgString)));
      img.src = `data:image/svg+xml;base64,${base64}`;
    } catch (error) {
      reject(new Error(`Failed to encode SVG: ${error instanceof Error ? error.message : 'Unknown error'}`));
    };
  });
}

/**
 * Render a single Mermaid diagram to PNG
 *
 * @param code - Mermaid diagram code
 * @param id - Unique ID for this diagram (optional, auto-generated if not provided)
 * @returns DiagramRenderResult with PNG data or error
 */
export async function renderMermaidToPNG(code: string, id?: string): Promise<DiagramRenderResult> {
  // Initialize Mermaid if needed
  initializeMermaid();

  // Validate input
  if (!code || typeof code !== 'string' || code.trim().length === 0) {
    return {
      success: false,
      error: 'Invalid or empty Mermaid code',
    };
  }

  // Generate unique ID
  const diagramId = id || `mermaid-export-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  try {
    // Render Mermaid to SVG
    const { svg } = await mermaid.render(diagramId, code.trim());

    // Parse SVG dimensions
    const { width, height } = parseSVGDimensions(svg);

    // CRITICAL: Validate size before Canvas conversion
    if (width > MAX_CANVAS_SIZE || height > MAX_CANVAS_SIZE) {
      return {
        success: false,
        error: `Diagram too large: ${width}x${height}px exceeds ${MAX_CANVAS_SIZE}px limit`,
        width,
        height,
      };
    }

    // Convert SVG to PNG
    const pngDataUrl = await svgToPNG(svg, width, height);

    return {
      success: true,
      data: pngDataUrl,
      width,
      height,
    };
  } catch (error) {
    return {
      success: false,
      error: `Mermaid rendering failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
    };
  }
}

/**
 * Render multiple Mermaid diagrams sequentially (memory-efficient)
 *
 * @param diagrams - Array of Mermaid diagram code strings
 * @param onProgress - Optional callback for progress updates
 * @returns Array of DiagramRenderResults
 */
export async function renderMultipleDiagrams(
  diagrams: string[],
  onProgress?: (current: number, total: number) => void
): Promise<DiagramRenderResult[]> {
  const results: DiagramRenderResult[] = [];

  // Process diagrams sequentially to avoid memory issues
  for (let i = 0; i < diagrams.length; i++) {
    // Update progress
    if (onProgress) {
      onProgress(i + 1, diagrams.length);
    }

    // Render diagram
    const result = await renderMermaidToPNG(diagrams[i], `diagram-${i}`);
    results.push(result);

    // Allow garbage collection between renders
    // This prevents memory buildup when rendering many diagrams
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  return results;
}

/**
 * Create a text placeholder for failed diagrams
 */
export function createDiagramPlaceholder(error?: string): string {
  const message = error ? `[Diagram rendering failed: ${error}]` : '[Diagram rendering failed]';
  return message;
}
