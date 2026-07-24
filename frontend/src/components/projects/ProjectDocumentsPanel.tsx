import { useRef } from 'react';
import { Box, Button, Stack, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, getErrorMessage } from '../../api/client';
import {
  documentDownloadUrl,
  listDocuments,
  uploadDocument,
} from '../../api/documents';
import { useToast } from '../../context/ToastContext';
import { LoadingState } from '../common/LoadingState';
import { formatDateTime } from '../../utils/format';

type ProjectDocumentsPanelProps = {
  projectId: string;
};

export function ProjectDocumentsPanel({ projectId }: ProjectDocumentsPanelProps) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement | null>(null);

  const docsQuery = useQuery({
    queryKey: ['documents', 'project', projectId],
    queryFn: () => listDocuments({ entity_type: 'project', entity_id: projectId }),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      uploadDocument({
        entity_type: 'project',
        entity_id: projectId,
        file,
        title: file.name,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents', 'project', projectId] });
      showSuccess('Document uploaded');
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const docs = docsQuery.data ?? [];

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 1.5, alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          DMS metadata + local file storage for project documents (object-storage ready).
        </Typography>
        <Button
          size="small"
          variant="outlined"
          disabled={uploadMutation.isPending}
          onClick={() => inputRef.current?.click()}
        >
          Upload
        </Button>
        <input
          ref={inputRef}
          type="file"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (file) uploadMutation.mutate(file);
          }}
        />
      </Stack>

      {docsQuery.isLoading ? (
        <LoadingState message="Loading documents…" />
      ) : docs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No documents uploaded yet.
        </Typography>
      ) : (
        <Stack spacing={0.75}>
          {docs.map((doc) => (
            <Stack
              key={doc.id}
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {doc.title || doc.filename}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {doc.filename}
                  {doc.created_at ? ` · ${formatDateTime(doc.created_at)}` : ''}
                </Typography>
              </Box>
              <Button
                size="small"
                onClick={async () => {
                  try {
                    const { data } = await apiClient.get(documentDownloadUrl(doc.id), {
                      responseType: 'blob',
                    });
                    const url = URL.createObjectURL(data);
                    const anchor = document.createElement('a');
                    anchor.href = url;
                    anchor.download = doc.filename;
                    anchor.click();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    showError(getErrorMessage(err));
                  }
                }}
              >
                Download
              </Button>
            </Stack>
          ))}
        </Stack>
      )}
    </Box>
  );
}
