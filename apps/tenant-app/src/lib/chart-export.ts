import html2canvas from 'html2canvas';

interface ExportOptions {
  element: HTMLElement;
  filename: string;
  backgroundColor?: string;
}

/**
 * Exports a chart component as a PNG image
 * @param options - Export configuration options
 * @returns Promise that resolves when export is complete
 */
export async function exportChartAsPNG(options: ExportOptions): Promise<void> {
  const { element, filename, backgroundColor = '#ffffff' } = options;

  try {
    // Create canvas from the DOM element
    const canvas = await html2canvas(element, {
      backgroundColor,
      scale: 2, // Higher resolution for better quality
      logging: false,
      useCORS: true,
      allowTaint: true,
      onclone: (clonedDoc) => {
        // Ensure the cloned element is visible
        const clonedElement = clonedDoc.querySelector('[data-export-target]');
        if (clonedElement) {
          (clonedElement as HTMLElement).style.display = 'block';
        }
      },
    });

    // Convert canvas to blob
    canvas.toBlob((blob) => {
      if (!blob) {
        throw new Error('Failed to create image blob');
      }

      // Create download link
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;

      // Trigger download
      document.body.appendChild(link);
      link.click();

      // Cleanup
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 'image/png');
  } catch (error) {
    console.error('Error exporting chart:', error);
    throw new Error('Failed to export chart as PNG');
  }
}

/**
 * Generates a filename for chart export
 * @param metric - Current metric being displayed (conversations, messages, tokens)
 * @param dateRange - Date range string (e.g., "30d", "7d")
 * @returns Formatted filename with timestamp
 */
export function generateExportFilename(metric: string, dateRange: string): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0] + '_' +
                    new Date().toTimeString().split(' ')[0].replace(/:/g, '');
  return `usage_overview_${metric}_${dateRange}_${timestamp}.png`;
}
