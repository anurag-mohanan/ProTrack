import type { ReactNode } from 'react';
import type { SvgIconComponent } from '@mui/icons-material';
import { ProsohmButton } from '../ProsohmButton';
import { ModernDrawer } from './ModernDrawer';
import { UnsavedChangesBar } from '../../common/UnsavedChangesBar';

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
  submitDisabled?: boolean;
  destructiveAction?: ReactNode;
  width?: number | string;
  dirty?: boolean;
  onDiscard?: () => void;
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
  submitDisabled = false,
  destructiveAction,
  width,
  dirty = false,
  onDiscard,
}: FormDrawerProps) {
  const floatingBar = dirty ? (
    <UnsavedChangesBar
      visible
      inset
      onSave={() => {
        const form = document.getElementById(formId) as HTMLFormElement | null;
        form?.requestSubmit();
      }}
      onDiscard={() => onDiscard?.()}
      saving={loading}
      saveDisabled={submitDisabled}
      saveLabel={submitLabel}
    />
  ) : null;

  return (
    <ModernDrawer
      open={open}
      onClose={onClose}
      title={title}
      subtitle={subtitle}
      icon={icon}
      width={width}
      widthPreset="form"
      floatingBar={floatingBar}
      footer={
        <>
          {destructiveAction}
          <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={loading}>
            {cancelLabel}
          </ProsohmButton>
          {!dirty ? (
            <ProsohmButton
              type="submit"
              form={formId}
              buttonVariant="primary"
              loading={loading}
              disabled={submitDisabled || loading}
              onClick={onSubmit}
            >
              {submitLabel}
            </ProsohmButton>
          ) : null}
        </>
      }
    >
      {children}
    </ModernDrawer>
  );
}
