import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { UploadCloud } from 'lucide-react';
import { knowledgeService } from '@/services/knowledgeService';
import { queryKeys } from '@/api/queryKeys';
import { toast } from '@/stores/useNotificationStore';
import { parseApiError } from '@/lib/error';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select } from '@/components/ui/Select';
import { FormField } from '@/components/forms/FormField';
import { FileDropzone } from '@/components/forms/FileDropzone';
import type { DocumentCategory } from '@/types/knowledge';

const uploadSchema = z.object({
  title: z.string().optional(),
  description: z.string().optional(),
  category: z.enum([
    'RUNBOOK',
    'INCIDENT_REPORT',
    'MANUAL',
    'CONFIGURATION',
    'POLICY',
    'OTHER',
  ]),
  language: z.string().min(2, 'Language code required'),
  tags: z.string().optional(),
});

type UploadFormValues = z.infer<typeof uploadSchema>;

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UploadFormValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      title: '',
      description: '',
      category: 'RUNBOOK',
      language: 'en',
      tags: '',
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (values: UploadFormValues) => {
      if (!selectedFile) {
        throw new Error('Please select a file to upload');
      }

      const tagsArray = values.tags
        ? values.tags
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
        : [];

      return knowledgeService.uploadDocument(
        {
          file: selectedFile,
          title: values.title || '',
          description: values.description,
          category: values.category as DocumentCategory,
          language: values.language,
          tags: tagsArray,
        },
        (progress) => setUploadProgress(progress)
      );
    },
    onSuccess: (data) => {
      toast.success('Document Ingested', `Successfully uploaded "${data.title}"`);
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.lists() });
      handleClose();
    },
    onError: (err) => {
      const parsed = parseApiError(err);
      toast.error('Upload Failed', parsed.message);
    },
  });

  const handleClose = () => {
    reset();
    setSelectedFile(null);
    setFileError(null);
    setUploadProgress(0);
    onClose();
  };

  const onSubmit = (values: UploadFormValues) => {
    if (!selectedFile) {
      setFileError('File attachment is required');
      return;
    }
    setFileError(null);
    uploadMutation.mutate(values);
  };

  const categoryOptions = [
    { value: 'RUNBOOK', label: 'Operational Runbook' },
    { value: 'INCIDENT_REPORT', label: 'Post-Mortem / Incident Report' },
    { value: 'MANUAL', label: 'Technical Manual' },
    { value: 'CONFIGURATION', label: 'System Configuration' },
    { value: 'POLICY', label: 'Security Policy' },
    { value: 'OTHER', label: 'Other Document' },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Upload Knowledge Document"
      description="Ingest operational documentation, runbooks, and post-mortems into the retrieval pipeline."
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* File Dropzone */}
        <div>
          <label className="block text-xs font-medium text-foreground mb-1.5">
            File Attachment <span className="text-destructive">*</span>
          </label>
          <FileDropzone
            selectedFile={selectedFile}
            onFileSelect={(file) => {
              setSelectedFile(file);
              setFileError(null);
            }}
            onClear={() => setSelectedFile(null)}
            error={fileError || undefined}
          />
        </div>

        {/* Title */}
        <FormField
          label="Document Title"
          error={errors.title?.message}
          helperText="Leave empty to use original filename"
          htmlFor="doc-title"
        >
          <Input
            id="doc-title"
            placeholder="e.g. Kubernetes Cluster Evacuation Runbook"
            disabled={uploadMutation.isPending}
            {...register('title')}
          />
        </FormField>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Category */}
          <FormField
            label="Document Category"
            error={errors.category?.message}
            required
            htmlFor="doc-category"
          >
            <Select
              id="doc-category"
              options={categoryOptions}
              disabled={uploadMutation.isPending}
              {...register('category')}
            />
          </FormField>

          {/* Language */}
          <FormField
            label="ISO Language Code"
            error={errors.language?.message}
            required
            htmlFor="doc-lang"
          >
            <Input
              id="doc-lang"
              placeholder="en"
              disabled={uploadMutation.isPending}
              {...register('language')}
            />
          </FormField>
        </div>

        {/* Tags */}
        <FormField
          label="Tags"
          error={errors.tags?.message}
          helperText="Comma-separated operational keywords (e.g. k8s, ingress, p1)"
          htmlFor="doc-tags"
        >
          <Input
            id="doc-tags"
            placeholder="kubernetes, ingress-controller, failover"
            disabled={uploadMutation.isPending}
            {...register('tags')}
          />
        </FormField>

        {/* Description */}
        <FormField
          label="Document Summary / Scope"
          error={errors.description?.message}
          htmlFor="doc-desc"
        >
          <Textarea
            id="doc-desc"
            placeholder="Brief overview of procedures covered in this document..."
            disabled={uploadMutation.isPending}
            {...register('description')}
          />
        </FormField>

        {/* Upload Progress Bar */}
        {uploadMutation.isPending && (
          <div className="space-y-1.5 pt-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Ingesting payload into storage...</span>
              <span className="font-mono">{uploadProgress}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-cyan-400 transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-border/40">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleClose}
            disabled={uploadMutation.isPending}
          >
            Cancel
          </Button>

          <Button
            type="submit"
            variant="primary"
            size="sm"
            isLoading={uploadMutation.isPending}
            leftIcon={<UploadCloud className="h-3.5 w-3.5" />}
          >
            Upload Document
          </Button>
        </div>
      </form>
    </Modal>
  );
};
