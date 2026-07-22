'use client';

import React, { useState, useCallback } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Upload, AlertCircle, CheckCircle2, XCircle, Download } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { bulkImportAgents, type BulkImportResult } from '@/services/agents';

interface AgentBulkImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

export function AgentBulkImportModal({ isOpen, onClose, onImportComplete }: AgentBulkImportModalProps) {
  const [csvFiles, setCsvFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<BulkImportResult | null>(null);

  const handleClose = () => {
    if (!isProcessing) {
      // Reset state
      setCsvFiles([]);
      setResult(null);
      onClose();
    }
  };

  const handleFileSelect = (files: File[]) => {
    const validFiles: File[] = [];

    for (const file of files) {
      // Validate file type
      if (!file.name.endsWith('.csv')) {
        alert(`Skipping ${file.name}: Not a CSV file`);
        continue;
      }

      // Validate file size (1MB)
      if (file.size > 1024 * 1024) {
        alert(`Skipping ${file.name}: File size must be less than 1MB`);
        continue;
      }

      validFiles.push(file);
    }

    if (validFiles.length > 0) {
      setCsvFiles(prev => [...prev, ...validFiles]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setCsvFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files);
    }
  }, []);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(Array.from(files));
    }
  };

  const handleImport = async () => {
    setIsProcessing(true);
    setResult(null);

    try {
      if (csvFiles.length === 0) {
        alert('Please select at least one CSV file to import');
        setIsProcessing(false);
        return;
      }

      // Import all files sequentially and aggregate results
      let totalSuccess = 0;
      let totalErrors = 0;
      let totalRows = 0;
      const allCreatedAgents: any[] = [];
      const allErrors: any[] = [];

      for (let i = 0; i < csvFiles.length; i++) {
        const file = csvFiles[i];
        try {
          const importResult = await bulkImportAgents({ file });
          totalSuccess += importResult.success_count;
          totalErrors += importResult.error_count;
          totalRows += importResult.total_rows;
          allCreatedAgents.push(...importResult.created_agents);

          // Prefix errors with filename
          const fileErrors = importResult.errors.map(err => ({
            ...err,
            message: `[${file.name}] ${err.message}`
          }));
          allErrors.push(...fileErrors);
        } catch (error) {
          console.error(`Failed to import ${file.name}:`, error);
          allErrors.push({
            row_number: 0,
            field: 'file',
            message: `[${file.name}] Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`
          });
        }
      }

      const aggregatedResult = {
        success_count: totalSuccess,
        error_count: totalErrors,
        total_rows: totalRows,
        created_agents: allCreatedAgents,
        errors: allErrors
      };

      setResult(aggregatedResult);

      // If successful, notify parent and refresh immediately
      // Backend invalidates cache, so fresh data will be fetched
      if (aggregatedResult.success_count > 0) {
        onImportComplete();
        onClose();  // Auto-close modal after successful import
      }
    } catch (error) {
      console.error('Import failed:', error);
      alert(`Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const downloadTemplate = () => {
    const template = `name,description,category,model,temperature,max_tokens,prompt_template,dataset_connection,selected_dataset_ids,disclaimer,easy_prompts,visibility,tags
"Research Agent","Agent for research tasks","research","llama-3.1-70b-versatile",0.7,4096,"You are a helpful research agent","all","","","","individual","research"\n`;

    const blob = new Blob([template], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'agent_import_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import Agent</DialogTitle>
          <DialogDescription>
            Import agent configurations from CSV files
          </DialogDescription>
        </DialogHeader>

        {!result ? (
          <>
            <div className="flex justify-end mb-4">
              <Button variant="outline" size="sm" onClick={downloadTemplate}>
                <Download className="w-4 h-4 mr-2" />
                Download Template
              </Button>
            </div>

            <div className="space-y-4">
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    isDragging
                      ? 'border-gt-green bg-gt-green/5'
                      : 'border-gray-300 hover:border-gt-green/50'
                  }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  {csvFiles.length > 0 ? (
                    <div className="space-y-3">
                      <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto" />
                      <p className="text-sm font-medium">{csvFiles.length} file{csvFiles.length > 1 ? 's' : ''} selected</p>
                      <div className="max-h-40 overflow-y-auto space-y-2">
                        {csvFiles.map((file, index) => (
                          <div key={index} className="flex items-center justify-between bg-gray-50 rounded px-3 py-2">
                            <div className="text-left flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{file.name}</p>
                              <p className="text-xs text-gray-500">
                                {(file.size / 1024).toFixed(2)} KB
                              </p>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveFile(index)}
                              className="ml-2 h-auto p-1 text-gray-400 hover:text-red-600"
                            >
                              <XCircle className="w-4 h-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                      <label className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-gt-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 cursor-pointer transition-colors">
                        Add More Files
                        <input
                          type="file"
                          accept=".csv"
                          multiple
                          className="hidden"
                          onChange={handleFileInputChange}
                        />
                      </label>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                      <p className="text-sm text-gray-600 mb-2">
                        Drag and drop your CSV files here
                      </p>
                      <p className="text-xs text-gray-500 mb-4">or</p>
                      <label className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-gt-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 cursor-pointer transition-colors">
                        Choose Files
                        <input
                          type="file"
                          accept=".csv"
                          multiple
                          className="hidden"
                          onChange={handleFileInputChange}
                        />
                      </label>
                      <p className="text-xs text-gray-500 mt-4">
                        Maximum file size: 1MB per file
                      </p>
                    </>
                  )}
                </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex gap-3">
              <AlertCircle className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-blue-800">
                <strong>CSV Format:</strong> Comma-delimited, header row required. Arrays use pipe separator (|),
                objects use JSON format. Duplicate agent names will be auto-renamed with (1), (2), etc.
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={handleClose} disabled={isProcessing}>
                Cancel
              </Button>
              <Button
                onClick={handleImport}
                disabled={isProcessing || csvFiles.length === 0}
                className="bg-gt-green hover:bg-gt-green/90"
              >
                {isProcessing ? 'Importing...' : 'Import Agent'}
              </Button>
            </div>

            {isProcessing && (
              <div className="mt-4">
                <Progress value={undefined} className="w-full" />
                <p className="text-sm text-center text-gray-600 mt-2">
                  Processing agents...
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-4">
            {/* Results Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-blue-700">{result.total_rows}</p>
                <p className="text-sm text-blue-600">Total Rows</p>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-green-700">{result.success_count}</p>
                <p className="text-sm text-green-600">Imported</p>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-red-700">{result.error_count}</p>
                <p className="text-sm text-red-600">Errors</p>
              </div>
            </div>

            {/* Created Agents */}
            {result.created_agents && result.created_agents.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                  Successfully Imported Agents
                </h3>
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 max-h-40 overflow-y-auto">
                  <ul className="text-sm space-y-1">
                    {result.created_agents.map((agent, idx) => (
                      <li key={idx} className="text-green-800">
                        ✓ {agent.name}
                        {agent.original_name && (
                          <span className="text-xs text-green-600 ml-2">
                            (renamed from "{agent.original_name}")
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Errors */}
            {result.errors && result.errors.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-red-600" />
                  Import Errors
                </h3>
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 max-h-40 overflow-y-auto">
                  <ul className="text-sm space-y-2">
                    {result.errors.map((error, idx) => (
                      <li key={idx} className="text-red-800">
                        <strong>Row {error.row_number}</strong>
                        {error.field && ` (${error.field})`}: {error.message}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 mt-4">
              <Button onClick={handleClose} className="bg-gt-green hover:bg-gt-green/90">
                Done
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
