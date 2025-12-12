'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { 
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle,
  Upload,
  X,
  Plus,
  ChevronLeft,
  ChevronRight,
  Play,
  Eye,
  EyeOff,
  Calendar,
  Clock,
  Mail,
  Phone,
  Globe,
  Hash,
  Type,
  List,
  CheckSquare,
  Circle,
  Image,
  Workflow
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { 
  Workflow,
  WorkflowExecution,
  WorkflowInterfaceProps,
  FormField,
  FormData,
  FormErrors,
  FieldValidation
} from '@/types/workflow';

interface WorkflowFormInterfaceProps extends WorkflowInterfaceProps {
  fields?: FormField[];
  multiStep?: boolean;
  showPreview?: boolean;
  autoSave?: boolean;
  onFieldChange?: (fieldName: string, value: any) => void;
  onValidationChange?: (errors: FormErrors) => void;
}

interface FormFieldComponentProps {
  field: FormField;
  value: any;
  onChange: (value: any) => void;
  error?: string[];
  disabled?: boolean;
}

function FormFieldComponent({ field, value, onChange, error, disabled }: FormFieldComponentProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setSelectedFiles(files);
    
    if (field.multiple) {
      onChange(files);
    } else {
      onChange(files[0] || null);
    }
  };

  const removeFile = (index: number) => {
    const newFiles = selectedFiles.filter((_, i) => i !== index);
    setSelectedFiles(newFiles);
    
    if (field.multiple) {
      onChange(newFiles);
    } else {
      onChange(null);
    }
  };

  const getFieldIcon = () => {
    switch (field.type) {
      case 'email': return <Mail className="w-4 h-4" />;
      case 'tel': return <Phone className="w-4 h-4" />;
      case 'url': return <Globe className="w-4 h-4" />;
      case 'number': return <Hash className="w-4 h-4" />;
      case 'textarea': return <Type className="w-4 h-4" />;
      case 'select': return <List className="w-4 h-4" />;
      case 'checkbox': return <CheckSquare className="w-4 h-4" />;
      case 'radio': return <Circle className="w-4 h-4" />;
      case 'file': return <Upload className="w-4 h-4" />;
      case 'date': return <Calendar className="w-4 h-4" />;
      case 'time': return <Clock className="w-4 h-4" />;
      case 'datetime-local': return <Calendar className="w-4 h-4" />;
      default: return <Type className="w-4 h-4" />;
    }
  };

  const baseInputProps = {
    id: field.name,
    disabled,
    placeholder: field.placeholder,
    required: field.required,
    className: cn(error && "border-red-500 focus:border-red-500")
  };

  return (
    <div className="space-y-2">
      <Label htmlFor={field.name} className="flex items-center gap-2">
        {getFieldIcon()}
        {field.label}
        {field.required && <span className="text-red-500">*</span>}
      </Label>
      
      {field.description && (
        <p className="text-sm text-gray-500">{field.description}</p>
      )}

      {/* Text inputs */}
      {(['text', 'email', 'url', 'tel', 'number', 'date', 'time', 'datetime-local'].includes(field.type)) && (
        <Input
          {...baseInputProps}
          type={field.type === 'password' && showPassword ? 'text' : field.type}
          value={value || ''}
          onChange={(e) => onChange(field.type === 'number' ? Number(e.target.value) : (e as React.ChangeEvent<HTMLSelectElement>).target.value)}
          min={field.min}
          max={field.max}
          step={field.step}
          pattern={field.pattern}
        />
      )}

      {/* Password input with show/hide toggle */}
      {field.type === 'password' && (
        <div className="relative">
          <Input
            {...baseInputProps}
            type={showPassword ? 'text' : 'password'}
            value={value || ''}
            onChange={(e) => onChange((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-1 top-1 h-8 w-8 p-0"
            onClick={() => setShowPassword(!showPassword)}
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </Button>
        </div>
      )}

      {/* Textarea */}
      {field.type === 'textarea' && (
        <Textarea
          {...baseInputProps}
          value={value || ''}
          onChange={(e) => onChange((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
          rows={4}
        />
      )}

      {/* Select dropdown */}
      {field.type === 'select' && (
        <Select
          disabled={disabled}
          value={value || ''}
          onValueChange={onChange}
        >
          <SelectTrigger className={cn(error && "border-red-500")}>
            <SelectValue placeholder={field.placeholder || `Select ${field.label.toLowerCase()}...`} />
          </SelectTrigger>
          <SelectContent>
            {field.options?.map((option) => (
              <SelectItem 
                key={option.value.toString()} 
                value={option.value.toString()}
                disabled={option.disabled}
              >
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Checkbox */}
      {field.type === 'checkbox' && (
        <div className="flex items-center space-x-2">
          <Switch
            id={field.name}
            checked={Boolean(value)}
            onCheckedChange={onChange}
            disabled={disabled}
          />
          <Label htmlFor={field.name} className="text-sm cursor-pointer">
            {field.label}
          </Label>
        </div>
      )}

      {/* Radio buttons */}
      {field.type === 'radio' && (
        <div className="space-y-2">
          {field.options?.map((option) => (
            <div key={option.value.toString()} className="flex items-center space-x-2">
              <input
                type="radio"
                id={`${field.name}-${option.value}`}
                name={field.name}
                value={option.value.toString()}
                checked={value === option.value.toString()}
                onChange={(e) => onChange((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
                disabled={disabled || option.disabled}
                className="w-4 h-4 text-blue-600"
              />
              <Label 
                htmlFor={`${field.name}-${option.value}`}
                className="text-sm cursor-pointer"
              >
                {option.label}
              </Label>
            </div>
          ))}
        </div>
      )}

      {/* File upload */}
      {field.type === 'file' && (
        <div className="space-y-2">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
            <input
              type="file"
              id={field.name}
              multiple={field.multiple}
              accept={field.accept}
              onChange={handleFileChange}
              disabled={disabled}
              className="hidden"
            />
            <Label htmlFor={field.name} className="cursor-pointer">
              <div className="flex flex-col items-center gap-2">
                <Upload className="w-8 h-8 text-gray-400" />
                <div>
                  <span className="text-sm font-medium text-blue-600 hover:text-blue-500">
                    Click to upload
                  </span>
                  <span className="text-sm text-gray-500"> or drag and drop</span>
                </div>
                {field.accept && (
                  <p className="text-xs text-gray-400">
                    Accepted: {field.accept}
                  </p>
                )}
              </div>
            </Label>
          </div>

          {/* Selected files */}
          {selectedFiles.length > 0 && (
            <div className="space-y-1">
              {selectedFiles.map((file, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded border">
                  <div className="flex items-center gap-2">
                    <Image className="w-4 h-4 text-gray-500" />
                    <span className="text-sm text-gray-700">{file.name}</span>
                    <span className="text-xs text-gray-500">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeFile(index)}
                    className="h-6 w-6 p-0"
                  >
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Field errors */}
      {error && error.length > 0 && (
        <div className="space-y-1">
          {error.map((errorMsg, index) => (
            <div key={index} className="flex items-center gap-1 text-sm text-red-600">
              <AlertCircle className="w-3 h-3" />
              {errorMsg}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function validateField(field: FormField, value: any): string[] {
  const errors: string[] = [];
  const validation = field.validation || {};

  // Required validation
  if (field.required && (!value || (Array.isArray(value) && value.length === 0) || value === '')) {
    errors.push(`${field.label} is required`);
    return errors; // Don't check other validations if required field is empty
  }

  // Skip other validations if field is empty and not required
  if (!value || value === '') {
    return errors;
  }

  // String length validations
  if (typeof value === 'string') {
    if (validation.min_length && value.length < validation.min_length) {
      errors.push(`${field.label} must be at least ${validation.min_length} characters`);
    }
    if (validation.max_length && value.length > validation.max_length) {
      errors.push(`${field.label} must be no more than ${validation.max_length} characters`);
    }
  }

  // Number validations
  if (field.type === 'number' && typeof value === 'number') {
    if (validation.min_value !== undefined && value < validation.min_value) {
      errors.push(`${field.label} must be at least ${validation.min_value}`);
    }
    if (validation.max_value !== undefined && value > validation.max_value) {
      errors.push(`${field.label} must be no more than ${validation.max_value}`);
    }
  }

  // Pattern validation
  if (validation.pattern && typeof value === 'string') {
    const regex = new RegExp(validation.pattern);
    if (!regex.test(value)) {
      errors.push(validation.custom_message || `${field.label} format is invalid`);
    }
  }

  // Email validation
  if (field.type === 'email' && typeof value === 'string') {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value)) {
      errors.push(`${field.label} must be a valid email address`);
    }
  }

  // URL validation
  if (field.type === 'url' && typeof value === 'string') {
    try {
      new URL(value);
    } catch {
      errors.push(`${field.label} must be a valid URL`);
    }
  }

  return errors;
}

export function WorkflowFormInterface({
  workflow,
  onExecute,
  onExecutionUpdate,
  fields = [],
  multiStep = false,
  showPreview = false,
  autoSave = false,
  onFieldChange,
  onValidationChange,
  className
}: WorkflowFormInterfaceProps) {
  const [formData, setFormData] = useState<FormData>({});
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [lastExecution, setLastExecution] = useState<WorkflowExecution | null>(null);
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  // Generate form fields from workflow definition if not provided
  const formFields = fields.length > 0 ? fields : generateFieldsFromWorkflow(workflow);
  
  // Group fields by step for multi-step forms
  const fieldSteps = multiStep ? groupFieldsByStep(formFields) : [formFields];
  const currentStepFields = fieldSteps[currentStep] || [];
  const totalSteps = fieldSteps.length;

  // Initialize form data with default values
  useEffect(() => {
    const initialData: FormData = {};
    formFields.forEach(field => {
      if (field.default_value !== undefined) {
        initialData[field.name] = field.default_value;
      }
    });
    setFormData(initialData);
  }, [formFields]);

  // Auto-save functionality
  useEffect(() => {
    if (autoSave && Object.keys(formData).length > 0) {
      const timer = setTimeout(() => {
        // Save to localStorage or send to backend
        localStorage.setItem(`workflow-form-${workflow.id}`, JSON.stringify(formData));
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [formData, autoSave, workflow.id]);

  // Validate all fields
  const validateForm = (fieldsToValidate: FormField[] = formFields): FormErrors => {
    const errors: FormErrors = {};
    
    fieldsToValidate.forEach(field => {
      const fieldErrors = validateField(field, formData[field.name]);
      if (fieldErrors.length > 0) {
        errors[field.name] = fieldErrors;
      }
    });

    return errors;
  };

  // Handle field value change
  const handleFieldChange = (fieldName: string, value: any) => {
    const newFormData = { ...formData, [fieldName]: value };
    setFormData(newFormData);

    // Validate the changed field
    const field = formFields.find(f => f.name === fieldName);
    if (field) {
      const fieldErrors = validateField(field, value);
      const newErrors = { ...formErrors };
      
      if (fieldErrors.length > 0) {
        newErrors[fieldName] = fieldErrors;
      } else {
        delete newErrors[fieldName];
      }
      
      setFormErrors(newErrors);
      
      if (onValidationChange) {
        onValidationChange(newErrors);
      }
    }

    if (onFieldChange) {
      onFieldChange(fieldName, value);
    }
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (isExecuting) return;

    // Validate all fields
    const errors = validateForm();
    setFormErrors(errors);

    if (Object.keys(errors).length > 0) {
      // Scroll to first error
      const firstErrorField = Object.keys(errors)[0];
      const errorElement = document.getElementById(firstErrorField);
      errorElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    setIsExecuting(true);

    try {
      const execution = await onExecute({
        ...formData,
        interaction_mode: 'form',
        trigger_type: 'manual'
      });

      setLastExecution(execution);

      if (execution.status === 'running') {
        // Poll for execution updates
        pollExecutionStatus(execution.id);
      } else {
        setIsExecuting(false);
      }

      if (onExecutionUpdate) {
        onExecutionUpdate(execution);
      }

    } catch (error) {
      console.error('Failed to execute workflow:', error);
      setIsExecuting(false);
    }
  };

  const pollExecutionStatus = async (executionId: string) => {
    setTimeout(() => {
      const updatedExecution: WorkflowExecution = {
        ...lastExecution!,
        status: 'completed',
        progress_percentage: 100,
        completed_at: new Date().toISOString(),
        duration_ms: 2200,
        output_data: {
          result: 'Form workflow executed successfully',
          processed_data: formData
        },
        tokens_used: 120,
        cost_cents: 4
      };

      setLastExecution(updatedExecution);
      setIsExecuting(false);

      if (onExecutionUpdate) {
        onExecutionUpdate(updatedExecution);
      }
    }, 2200);
  };

  // Navigation for multi-step forms
  const canGoNext = () => {
    if (!multiStep) return false;
    const stepErrors = validateForm(currentStepFields);
    return currentStep < totalSteps - 1 && Object.keys(stepErrors).length === 0;
  };

  const canGoPrevious = () => {
    return multiStep && currentStep > 0;
  };

  const handleNext = () => {
    if (canGoNext()) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (canGoPrevious()) {
      setCurrentStep(currentStep - 1);
    }
  };

  const isFormValid = Object.keys(validateForm()).length === 0;
  const canSubmit = !multiStep || currentStep === totalSteps - 1;

  return (
    <Card className={cn("w-full max-w-2xl", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="w-5 h-5" />
          {workflow.name}
          {multiStep && (
            <Badge variant="secondary" className="ml-auto">
              Step {currentStep + 1} of {totalSteps}
            </Badge>
          )}
        </CardTitle>
        {workflow.description && (
          <p className="text-sm text-gray-600 mt-1">
            {workflow.description}
          </p>
        )}
      </CardHeader>

      <CardContent>
        {/* Form Preview Toggle */}
        {showPreview && (
          <div className="flex justify-end mb-4">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsPreviewMode(!isPreviewMode)}
            >
              {isPreviewMode ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              {isPreviewMode ? 'Edit Form' : 'Preview Data'}
            </Button>
          </div>
        )}

        {/* Form Preview */}
        {isPreviewMode ? (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Form Data Preview</h3>
            <pre className="p-4 bg-gray-50 rounded-lg border text-sm overflow-x-auto">
              {JSON.stringify(formData, null, 2)}
            </pre>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Multi-step progress */}
            {multiStep && totalSteps > 1 && (
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Progress</span>
                  <span className="text-sm text-gray-500">
                    {Math.round(((currentStep + 1) / totalSteps) * 100)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Form Fields */}
            <div className="space-y-4">
              {currentStepFields.map((field) => (
                <FormFieldComponent
                  key={field.name}
                  field={field}
                  value={formData[field.name]}
                  onChange={(value) => handleFieldChange(field.name, value)}
                  error={formErrors[field.name]}
                  disabled={isExecuting}
                />
              ))}
            </div>

            {/* Form Actions */}
            <div className="flex items-center justify-between pt-4 border-t">
              {/* Previous Button */}
              <Button
                type="button"
                variant="secondary"
                onClick={handlePrevious}
                disabled={!canGoPrevious() || isExecuting}
                className={cn(!canGoPrevious() && "invisible")}
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </Button>

              <div className="flex gap-2">
                {/* Next Button */}
                {!canSubmit && (
                  <Button
                    type="button"
                    onClick={handleNext}
                    disabled={!canGoNext() || isExecuting}
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                )}

                {/* Submit Button */}
                {canSubmit && (
                  <Button
                    type="submit"
                    disabled={!isFormValid || isExecuting}
                  >
                    {isExecuting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Executing...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        Execute Workflow
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </form>
        )}

        {/* Execution Result */}
        {lastExecution && (
          <div className="mt-6 p-4 border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              {lastExecution.status === 'completed' && (
                <CheckCircle className="w-5 h-5 text-green-600" />
              )}
              {lastExecution.status === 'running' && (
                <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
              )}
              <span className="font-medium">
                Execution {lastExecution.status}
              </span>
            </div>
            
            {lastExecution.output_data && (
              <div className="text-sm text-gray-600">
                <strong>Result:</strong> {JSON.stringify(lastExecution.output_data)}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Helper functions
function generateFieldsFromWorkflow(workflow: Workflow): FormField[] {
  // Extract fields from trigger nodes that have input schemas
  const triggerNodes = workflow.definition.nodes.filter(node => node.type === 'trigger');
  const fields: FormField[] = [];

  triggerNodes.forEach(node => {
    if (node.data.input_schema) {
      fields.push(...node.data.input_schema);
    }
  });

  // If no fields found, create a basic message field
  if (fields.length === 0) {
    fields.push({
      name: 'message',
      label: 'Message',
      type: 'textarea',
      required: true,
      placeholder: 'Enter your message for the workflow...',
      description: 'This message will be used as input for the workflow execution'
    });
  }

  return fields;
}

function groupFieldsByStep(fields: FormField[]): FormField[][] {
  // Simple grouping: every 3-4 fields per step
  const steps: FormField[][] = [];
  const fieldsPerStep = 4;

  for (let i = 0; i < fields.length; i += fieldsPerStep) {
    steps.push(fields.slice(i, i + fieldsPerStep));
  }

  return steps.length > 0 ? steps : [fields];
}