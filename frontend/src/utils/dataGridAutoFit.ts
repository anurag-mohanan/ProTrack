/**
 * Content-aware column sizing for MUI DataGrid tables (Excel AutoFit-style).
 * Reusable across Projects, Workload, Reports, Timesheets, and admin grids.
 */

import type { GridColDef, GridValidRowModel } from '@mui/x-data-grid';

export type ColumnFitKind =
  | 'content'
  | 'flex'
  | 'compact'
  | 'badge'
  | 'hours'
  | 'progress'
  | 'date'
  | 'actions';

export interface ColumnAutoFitProfile {
  field: string;
  headerName: string;
  kind: ColumnFitKind;
  /** Flex weight when kind is `flex` (absorbs remaining horizontal space). */
  flex?: number;
  /** Minimum width floor in pixels. */
  minWidth?: number;
  /** Maximum width cap in pixels. */
  maxWidth?: number;
  /** Extra pixels added to measured content (avatars, icons). */
  extraPadding?: number;
  /** Badge label candidates for badge columns. */
  badgeLabels?: string[];
  /** Extract display text from a row for measurement. */
  getValue?: (row: unknown) => string;
}

export interface AutoFitOptions {
  /** Wider flex weights on large monitors (1920px+). */
  wide?: boolean;
  charWidth?: number;
  cellPadding?: number;
}

const DEFAULT_CHAR_WIDTH = 7.05;
const HEADER_CHAR_WIDTH = 6.6;
const DEFAULT_CELL_PADDING = 18;

function estimateTextWidth(
  text: string,
  charWidth = DEFAULT_CHAR_WIDTH,
  padding = DEFAULT_CELL_PADDING,
): number {
  const normalized = String(text ?? '').trim();
  if (!normalized || normalized === '—') return padding;
  return Math.ceil(normalized.length * charWidth) + padding;
}

function headerWidth(headerName: string, padding = 28): number {
  return estimateTextWidth(headerName, HEADER_CHAR_WIDTH, padding);
}

function longestContentWidth(values: string[], charWidth: number, padding: number): number {
  if (!values.length) return padding;
  return Math.max(...values.map((value) => estimateTextWidth(value, charWidth, padding)));
}

function hoursColumnWidth(rows: unknown[], getValue?: (row: unknown) => string): number {
  const samples = rows.map((row) => getValue?.(row) ?? '');
  const header = headerWidth('Hours');
  const content = Math.max(
    longestContentWidth(samples, 6.8, 12),
    estimateTextWidth('999 / 999', 6.8, 12) + 38,
  );
  return Math.min(120, Math.max(96, Math.max(header, content)));
}

function resolveProfileWidth(
  profile: ColumnAutoFitProfile,
  rows: unknown[],
  options: AutoFitOptions,
): Pick<GridColDef, 'width' | 'minWidth' | 'maxWidth' | 'flex'> {
  const charWidth = options.charWidth ?? DEFAULT_CHAR_WIDTH;
  const padding = options.cellPadding ?? DEFAULT_CELL_PADDING;
  const header = headerWidth(profile.headerName);
  const values = rows.map((row) => profile.getValue?.(row) ?? '');

  switch (profile.kind) {
    case 'actions':
      return {
        width: profile.minWidth ?? 72,
        minWidth: profile.minWidth ?? 72,
        maxWidth: profile.maxWidth ?? 88,
      };

    case 'hours':
      return {
        width: hoursColumnWidth(rows, profile.getValue),
        minWidth: 92,
        maxWidth: 120,
      };

    case 'progress':
      return {
        width: Math.max(72, header),
        minWidth: 68,
        maxWidth: 88,
      };

    case 'date':
      return {
        width: Math.max(92, header, longestContentWidth(values, 6.5, 12)),
        minWidth: 88,
        maxWidth: 112,
      };

    case 'compact':
      return {
        width: Math.max(profile.minWidth ?? 68, header, longestContentWidth(values, charWidth, 10)),
        minWidth: profile.minWidth ?? 68,
        maxWidth: profile.maxWidth ?? 96,
      };

    case 'badge': {
      const badgeTexts = profile.badgeLabels ?? values;
      const badgeWidth = Math.max(
        header,
        ...badgeTexts.map((label) => estimateTextWidth(label, 6.4, 34)),
      );
      return {
        width: Math.min(profile.maxWidth ?? 220, Math.max(profile.minWidth ?? 72, badgeWidth)),
        minWidth: profile.minWidth ?? 72,
        maxWidth: profile.maxWidth ?? 220,
      };
    }

    case 'flex': {
      const content = longestContentWidth(values, charWidth, padding) + (profile.extraPadding ?? 0);
      const minWidth = Math.max(profile.minWidth ?? 88, content, header);
      const flex = (profile.flex ?? 1) * (options.wide ? 1.15 : 1);
      return {
        minWidth,
        flex,
        maxWidth: profile.maxWidth,
      };
    }

    case 'content':
    default: {
      const content =
        longestContentWidth(values, charWidth, padding) + (profile.extraPadding ?? 0);
      const width = Math.min(
        profile.maxWidth ?? 360,
        Math.max(profile.minWidth ?? 64, content, header),
      );
      return {
        width,
        minWidth: Math.max(profile.minWidth ?? 64, Math.min(width, content)),
        maxWidth: profile.maxWidth,
      };
    }
  }
}

export function applyAutoFitToColumns<TRow extends GridValidRowModel>(
  columns: GridColDef<TRow>[],
  rows: TRow[],
  profiles: ColumnAutoFitProfile[],
  options: AutoFitOptions = {},
): GridColDef<TRow>[] {
  const profileByField = new Map(profiles.map((profile) => [profile.field, profile]));

  return columns.map((column) => {
    const profile = profileByField.get(column.field);
    if (!profile) return column;

    const sizing = resolveProfileWidth(profile, rows as unknown[], options);
    return {
      ...column,
      ...sizing,
      resizable: column.resizable ?? true,
    };
  });
}

/** Shared cell style — show full text when column is content-sized (no ellipsis). */
export const autoFitCellSx = {
  overflow: 'visible',
  textOverflow: 'clip',
  whiteSpace: 'nowrap' as const,
};

/** Shared cell style — allow flex columns to shrink gracefully on narrow viewports. */
export const autoFitFlexCellSx = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap' as const,
};
