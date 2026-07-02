import { createContext, useContext, type ReactNode } from 'react';
import type { BrandingSettings, PublicSettings } from '../types/Settings';

interface CompanyContextValue {
  company: PublicSettings['company'] | null;
  branding: BrandingSettings | null;
  appName: string;
  isLoading: boolean;
}

const CompanyContext = createContext<CompanyContextValue>({
  company: null,
  branding: null,
  appName: 'ProTrack',
  isLoading: true,
});

export function CompanyProvider({
  value,
  children,
}: {
  value: CompanyContextValue;
  children: ReactNode;
}) {
  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompany() {
  return useContext(CompanyContext);
}
