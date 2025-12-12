'use client';

import { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

interface ReportChatIssueSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentName: string;
  timestamp: string;
  conversationName: string;
  userPrompt: string;
  agentResponse: string;
  // Agent configuration
  model?: string;
  temperature?: number;
  maxTokens?: number;
  // Tenant information
  tenantUrl?: string;
  tenantName?: string;
  // User information
  userEmail?: string;
}

const issueTypes = [
  { value: '1', label: 'Harmful or biased content' },
  { value: '2', label: 'Hallucinations observed' },
  { value: '3', label: 'Error message' },
  { value: '4', label: 'Other - please explain' },
];

export function ReportChatIssueSheet({
  open,
  onOpenChange,
  agentName,
  timestamp,
  conversationName,
  userPrompt,
  agentResponse,
  model,
  temperature,
  maxTokens,
  tenantUrl,
  tenantName,
  userEmail,
}: ReportChatIssueSheetProps) {
  const [selectedIssueType, setSelectedIssueType] = useState<string>('');
  const [comments, setComments] = useState<string>('');
  const [validationError, setValidationError] = useState<string>('');

  const handleSendReport = () => {
    // Validation
    if (!selectedIssueType) {
      setValidationError('Please select an issue type');
      return;
    }

    if (selectedIssueType === '4' && !comments.trim()) {
      setValidationError('Comments are required when selecting "Other"');
      return;
    }

    // Clear validation error
    setValidationError('');

    // Find the selected issue type label
    const issueTypeLabel = issueTypes.find((type) => type.value === selectedIssueType)?.label || 'Unknown';

    // Build report content
    const reportTimestamp = new Date().toISOString();
    const reportContent = `====================================
GT Chat Issue Report
Generated: ${reportTimestamp}
====================================

PLEASE SEND THIS FILE TO: support@gtedge.ai

ISSUE DETAILS:
- Issue Type: ${issueTypeLabel}
- User Comments: ${comments.trim() || 'None provided'}

USER INFORMATION:
- Email: ${userEmail || 'Not available'}
- Tenant Name: ${tenantName || 'Not available'}
- Tenant URL: ${tenantUrl || 'Not available'}

AGENT CONFIGURATION:
- Agent Name: ${agentName}
- Model: ${model || 'Not specified'}
- Temperature: ${temperature !== undefined ? temperature : 'Not specified'}
- Max Tokens: ${maxTokens !== undefined ? maxTokens : 'Not specified'}

CONVERSATION CONTEXT:
- Conversation Name: ${conversationName}
- Timestamp: ${timestamp}

USER PROMPT:
${userPrompt}

AGENT RESPONSE:
${agentResponse}
====================================`;

    // Create blob and download
    const blob = new Blob([reportContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);

    // Create filename with timestamp
    const filename = `chat-issue-report-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)}.txt`;

    // Create temporary link and trigger download
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();

    // Cleanup
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    // Reset form and close sheet
    setSelectedIssueType('');
    setComments('');
    setValidationError('');
    onOpenChange(false);
  };

  const handleCancel = () => {
    // Reset form and close sheet
    setSelectedIssueType('');
    setComments('');
    setValidationError('');
    onOpenChange(false);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col w-full sm:max-w-xl">
        <SheetHeader onClose={() => onOpenChange(false)}>
          <div>
            <SheetTitle>Report Chat Issue</SheetTitle>
            <SheetDescription>
              Enter the number of the type of concern that you have with the AI chat response.
            </SheetDescription>
          </div>
        </SheetHeader>

        <SheetBody className="flex-1 overflow-y-auto">
          <div className="space-y-4">
            <div className="space-y-3">
              <Label>Your issue type number:</Label>
              <RadioGroup value={selectedIssueType} onValueChange={setSelectedIssueType}>
                {issueTypes.map((type) => (
                  <div key={type.value} className="flex items-center space-x-2">
                    <RadioGroupItem value={type.value} id={`issue-${type.value}`} />
                    <Label htmlFor={`issue-${type.value}`} className="font-normal cursor-pointer">
                      {type.value}. {type.label}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>

            <div className="space-y-2">
              <Label htmlFor="comments">
                Comments:
                {selectedIssueType === '4' && <span className="text-red-500 ml-1">*</span>}
              </Label>
              <Textarea
                id="comments"
                placeholder={
                  selectedIssueType === '4'
                    ? 'Please explain your concern (required)'
                    : 'Add any additional comments (optional)'
                }
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                rows={6}
                className="resize-none"
              />
            </div>

            {validationError && <p className="text-sm text-red-500">{validationError}</p>}
          </div>
        </SheetBody>

        <SheetFooter>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSendReport}>Download Report</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
