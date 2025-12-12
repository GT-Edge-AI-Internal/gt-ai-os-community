'use client';

import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { ZoomIn, ZoomOut, Maximize, Move, RotateCcw } from 'lucide-react';

interface MermaidChartProps {
  children: string;
  className?: string;
}

export function MermaidChart({ children, className = '' }: MermaidChartProps) {
  const elementRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  const [renderState, setRenderState] = useState<'loading' | 'success' | 'error'>('loading');
  const [svgContent, setSvgContent] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  
  // Zoom and pan state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [showControls, setShowControls] = useState(false);

  useEffect(() => {
    if (!initialized.current) {
      // Initialize mermaid with dark theme and better sizing
      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          primaryColor: '#3b82f6',
          primaryTextColor: '#ffffff',
          primaryBorderColor: '#1e40af',
          lineColor: '#6b7280',
          secondaryColor: '#1f2937',
          tertiaryColor: '#374151',
          background: '#111827',
          mainBkg: '#1f2937',
          secondBkg: '#374151',
        },
        darkMode: true,
        fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        // Improve sizing and containment
        flowchart: {
          useMaxWidth: false,
          htmlLabels: true,
          curve: 'basis'
        },
        sequence: {
          useMaxWidth: false,
          diagramMarginX: 50,
          diagramMarginY: 10,
          boxTextMargin: 5,
          noteMargin: 10,
          messageMargin: 35
        },
        pie: {
          useMaxWidth: false
        },
        gantt: {
          useMaxWidth: false,
          leftPadding: 75,
          gridLineStartPadding: 35
        },
        // Completely suppress error rendering to DOM
        suppressErrorRendering: true,
        errorLevel: 'fatal',
        logLevel: 'fatal'
      });
      initialized.current = true;
    }

    // Reset state
    setRenderState('loading');
    setSvgContent('');
    setErrorMessage('');
      
    // Generate unique ID for this chart - use isolated approach
    const chartId = `isolated-mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Create a completely isolated temporary container for rendering
    const tempContainer = document.createElement('div');
    tempContainer.style.position = 'absolute';
    tempContainer.style.top = '-9999px';
    tempContainer.style.left = '-9999px';
    tempContainer.style.width = '1px';
    tempContainer.style.height = '1px';
    tempContainer.style.overflow = 'hidden';
    tempContainer.style.visibility = 'hidden';
    tempContainer.style.pointerEvents = 'none';
    document.body.appendChild(tempContainer);
    
    try {
      // Pre-validate the Mermaid syntax before attempting to render
      const trimmedContent = children.trim();
      
      // Basic syntax validation
      if (!trimmedContent || trimmedContent.length < 5) {
        throw new Error('Invalid or empty Mermaid content');
      }
      
      // Render the mermaid diagram in isolated container
      mermaid.render(chartId, trimmedContent).then(({ svg }) => {
        // Clean up temp container immediately
        document.body.removeChild(tempContainer);
        
        // Modify SVG for zoom and pan compatibility
        const modifiedSvg = svg
          .replace(/width="[^"]*"/, 'width="100%"')
          .replace(/height="[^"]*"/, 'height="100%"')
          .replace('<svg', '<svg style="display: block; cursor: grab;"');
        
        setSvgContent(modifiedSvg);
        setRenderState('success');
      }).catch((error) => {
        // Clean up temp container on error
        if (document.body.contains(tempContainer)) {
          document.body.removeChild(tempContainer);
        }
        
        // Completely suppress error display - just show a generic message
        console.warn('Mermaid diagram could not be rendered');
        setErrorMessage('Invalid diagram syntax');
        setRenderState('error');
      });
    } catch (error) {
      // Clean up temp container on syntax error
      if (document.body.contains(tempContainer)) {
        document.body.removeChild(tempContainer);
      }
      
      // Completely suppress error display - just show a generic message
      console.warn('Mermaid diagram syntax error');
      setErrorMessage('Invalid diagram syntax');
      setRenderState('error');
    }
  }, [children]);

  // Zoom and pan handlers
  const handleZoomIn = () => {
    setZoom(prevZoom => Math.min(prevZoom * 1.2, 5));
  };

  const handleZoomOut = () => {
    setZoom(prevZoom => Math.max(prevZoom / 1.2, 0.1));
  };

  const handleFitToWindow = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (renderState === 'success') {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      if (containerRef.current) {
        containerRef.current.style.cursor = 'grabbing';
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    if (containerRef.current) {
      containerRef.current.style.cursor = 'grab';
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prevZoom => Math.min(Math.max(prevZoom * delta, 0.1), 5));
  };

  return (
    <div 
      className={`mermaid-container relative bg-gray-900 rounded-lg border border-gray-700 ${className}`}
      style={{ 
        minHeight: '300px',
        maxWidth: '100%',
        backgroundColor: '#111827',
      }}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
    >
      {/* Zoom Controls */}
      {showControls && renderState === 'success' && (
        <div className="absolute top-2 right-2 z-10 flex flex-col gap-1 bg-gray-800 border border-gray-600 rounded p-1">
          <button
            onClick={handleZoomIn}
            className="p-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleFitToWindow}
            className="p-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="Fit to Window"
          >
            <Maximize className="w-4 h-4" />
          </button>
          <div className="text-xs text-gray-400 px-2 py-1 text-center">
            {Math.round(zoom * 100)}%
          </div>
        </div>
      )}

      {/* Pan Hint */}
      {showControls && renderState === 'success' && (
        <div className="absolute bottom-2 left-2 z-10 flex items-center gap-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-gray-400">
          <Move className="w-3 h-3" />
          Drag to pan • Scroll to zoom
        </div>
      )}

      {renderState === 'loading' && (
        <div className="flex items-center justify-center h-full">
          <div className="text-gray-400 text-sm">Rendering diagram...</div>
        </div>
      )}
      
      {renderState === 'success' && (
        <div 
          ref={containerRef}
          className="w-full h-full overflow-hidden cursor-grab"
          style={{ minHeight: '300px' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          <div 
            ref={elementRef}
            style={{ 
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: '0 0',
              transition: isDragging ? 'none' : 'transform 0.1s ease-out',
              cursor: isDragging ? 'grabbing' : 'grab'
            }}
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </div>
      )}
      
      {renderState === 'error' && (
        <div className="p-4 bg-red-900/20 border border-red-500 rounded text-red-200 max-w-full overflow-hidden">
          <strong className="block mb-2">Mermaid Diagram Error:</strong>
          <pre className="text-xs font-mono whitespace-pre-wrap break-words overflow-wrap-anywhere">
            {errorMessage}
          </pre>
        </div>
      )}
    </div>
  );
}