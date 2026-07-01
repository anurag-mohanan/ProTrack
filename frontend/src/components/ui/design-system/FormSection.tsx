import type { ReactNode } from 'react';
import { Grid } from '@mui/material';
import { AppCard } from './AppCard';
import type { SvgIconComponent } from '@mui/icons-material';

interface FormSectionProps {
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  children: ReactNode;
}

export function FormSection({ title, subtitle, icon, children }: FormSectionProps) {
  return (
    <AppCard title={title} subtitle={subtitle} icon={icon}>
      <Grid container spacing={2.5}>
        {children}
      </Grid>
    </AppCard>
  );
}
