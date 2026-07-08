import { useCallback, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { ProsohmButton } from '../ui/ProsohmButton';
import { resolveLogoUrl } from '../../config/env';

interface LogoUploadProps {
  logoUrl?: string | null;
  onUpload: (file: File) => Promise<void>;
  uploading?: boolean;
}

const ACCEPT = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'];

export function LogoUpload({ logoUrl, onUpload, uploading = false }: LogoUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const resolved = preview ?? resolveLogoUrl(logoUrl, logoUrl ?? '');

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file || !ACCEPT.includes(file.type)) return;
      setPreview(URL.createObjectURL(file));
      await onUpload(file);
    },
    [onUpload],
  );

  return (
    <Box>
      <Box
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          void handleFile(event.dataTransfer.files[0]);
        }}
        onClick={() => inputRef.current?.click()}
        sx={{
          border: '2px dashed',
          borderColor: dragActive ? 'primary.main' : 'divider',
          borderRadius: 3,
          p: 3,
          textAlign: 'center',
          cursor: uploading ? 'wait' : 'pointer',
          bgcolor: dragActive ? 'action.hover' : 'background.paper',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          hidden
          accept=".png,.jpg,.jpeg,.svg"
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
        {resolved ? (
          <Box
            component="img"
            src={resolved}
            alt="Company logo preview"
            sx={{ maxHeight: 96, maxWidth: '100%', objectFit: 'contain', mb: 2 }}
          />
        ) : (
          <CloudUploadIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
        )}
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {dragActive ? 'Drop logo here' : 'Drag & drop company logo'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          PNG, JPG, or SVG · max 2 MB
        </Typography>
      </Box>
      <Box sx={{ mt: 1.5 }}>
        <ProsohmButton
          buttonVariant="outlined"
          size="small"
          startIcon={<CloudUploadIcon />}
          loading={uploading}
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
        >
          Browse files
        </ProsohmButton>
      </Box>
    </Box>
  );
}
