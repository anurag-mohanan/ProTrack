import { useCallback, useState } from 'react';
import { getErrorMessage } from '../api/client';
import {
  fetchDeleteCheck,
  fetchUserDeleteCheck,
  permanentDeleteResource,
  permanentDeleteUser,
} from '../api/deleteCheck';
import type { DeleteCheckResult } from '../components/ui/design-system/DeleteRecordDialog';
import { useToast } from '../context/ToastContext';

interface DeleteTarget {
  id: string;
  name: string;
}

export function useAdminPermanentDelete(
  resource: string,
  onSuccess: () => void,
  options?: { useUserDeleteCheck?: boolean },
) {
  const { showSuccess, showError } = useToast();
  const [target, setTarget] = useState<DeleteTarget | null>(null);
  const [check, setCheck] = useState<DeleteCheckResult | null>(null);
  const [loading, setLoading] = useState(false);

  const closeDelete = useCallback(() => {
    if (loading) return;
    setTarget(null);
    setCheck(null);
  }, [loading]);

  const openDelete = useCallback(
    async (id: string, name: string) => {
      setTarget({ id, name });
      setCheck(null);
      try {
        const result = options?.useUserDeleteCheck
          ? await fetchUserDeleteCheck(id)
          : await fetchDeleteCheck(resource, id);
        setCheck({
          ...result,
          record_name: result.record_name ?? name,
        });
      } catch (error) {
        showError(getErrorMessage(error));
        setTarget(null);
      }
    },
    [options?.useUserDeleteCheck, resource, showError],
  );

  const confirmDelete = useCallback(async () => {
    if (!target || !check?.can_delete) return;
    setLoading(true);
    try {
      if (options?.useUserDeleteCheck) {
        await permanentDeleteUser(target.id);
      } else {
        await permanentDeleteResource(resource, target.id);
      }
      showSuccess(`${check.record_type ?? 'Record'} permanently deleted.`);
      closeDelete();
      onSuccess();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [check, closeDelete, onSuccess, options?.useUserDeleteCheck, resource, showError, showSuccess, target]);

  return {
    target,
    isOpen: Boolean(target),
    check,
    loading,
    openDelete,
    closeDelete,
    confirmDelete,
  };
}
