import { createContext, useCallback, useContext, type ReactNode } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { UserPreferences } from '../types/Preferences';
import { updateMyPreferences } from '../api/preferences';

interface PreferencesContextValue {
  preferences: UserPreferences | null;
  updatePreferences: (patch: Partial<UserPreferences>) => Promise<void>;
  isLoading: boolean;
}

const PreferencesContext = createContext<PreferencesContextValue>({
  preferences: null,
  updatePreferences: async () => undefined,
  isLoading: true,
});

export function PreferencesProvider({
  value,
  children,
}: {
  value: PreferencesContextValue;
  children: ReactNode;
}) {
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  return useContext(PreferencesContext);
}

export function usePreferencesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateMyPreferences,
    onSuccess: (data) => {
      queryClient.setQueryData(['preferences', 'me'], data);
      void queryClient.invalidateQueries({ queryKey: ['auth', 'profile'] });
    },
  });
}

export function useUpdatePreferences() {
  const mutation = usePreferencesMutation();
  const updatePreferences = useCallback(
    async (patch: Partial<UserPreferences>) => {
      await mutation.mutateAsync(patch);
    },
    [mutation],
  );
  return { updatePreferences, isSaving: mutation.isPending };
}
