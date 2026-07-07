import type { ReactNode } from 'react';
import { Box, Stack } from '@mui/material';
import FileDownloadRoundedIcon from '@mui/icons-material/FileDownloadRounded';
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { ProsohmButton } from '../ui/ProsohmButton';
import { exportToCsv, exportToPdfPlaceholder, type ExportColumn } from '../../utils/exportData';

interface ReportAnalyticsShellProps<T extends Record<string, unknown>> {
  title: string;
  subtitle?: string;
  chart?: ReactNode;
  kpis?: ReactNode;
  children: ReactNode;
  exportFilename?: string;
  exportRows?: T[];
  exportColumns?: ExportColumn<T>[];
  canExport?: boolean;
}

export function ReportAnalyticsShell<T extends Record<string, unknown>>({
  title,
  subtitle,
  chart,
  kpis,
  children,
  exportFilename,
  exportRows,
  exportColumns,
  canExport = false,
}: ReportAnalyticsShellProps<T>) {
  const showExport = canExport && exportRows && exportColumns && exportFilename;

  return (
    <Stack spacing={2.5}>
      {kpis ? <Box>{kpis}</Box> : null}
      {chart ? (
        <DashboardPanel title={`${title} — Visual`} subtitle={subtitle}>
          {chart}
        </DashboardPanel>
      ) : null}
      <DashboardPanel
        title={`${title} — Data`}
        subtitle={subtitle}
        action={
          showExport ? (
            <Stack direction="row" spacing={1}>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                startIcon={<FileDownloadRoundedIcon />}
                onClick={() => exportToCsv(exportFilename!, exportRows!, exportColumns!)}
              >
                CSV
              </ProsohmButton>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                startIcon={<PictureAsPdfRoundedIcon />}
                onClick={() => exportToPdfPlaceholder(exportFilename!)}
              >
                PDF
              </ProsohmButton>
            </Stack>
          ) : undefined
        }
        noPadding
      >
        {children}
      </DashboardPanel>
    </Stack>
  );
}
