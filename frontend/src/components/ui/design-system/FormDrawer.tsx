import type { ReactNode } from 'react';
import type { SvgIconComponent } from '@mui/icons-material';
import { ProsohmButton } from '../ProsohmButton';
import { ModernDrawer } from './ModernDrawer';

interface FormDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  formId: string;
  onSubmit?: () => void;
  children: ReactNode;
  submitLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  destructiveAction?: ReactNode;
  width?: number | string;
}

export function FormDrawer({
  open,
  onClose,
  title,
  subtitle,
  icon,
  formId,
  onSubmit,
  children,
  submitLabel = 'Save Changes',
  cancelLabel = 'Cancel',
  loading = false,
  destructiveAction,
  width,
}: FormDrawerProps) {
  return (
    <ModernDrawer
      open={open}
      onClose={onClose}
      title={title}
      subtitle={subtitle}
      icon={icon}
      width={width}
      widthPreset="form"
      footer={
        <>
          {destructiveAction}
          <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={loading}>
            {cancelLabel}
          </ProsohmButton>
          <ProsohmButton
            type="submit"
            form={formId}
            buttonVariant="primary"
            loading={loading}
            onClick={onSubmit}
          >
            {submitLabel}
          </ProsohmButton>
        </>
      }
    >
      {children}
    </ModernDrawer>
  );
}
