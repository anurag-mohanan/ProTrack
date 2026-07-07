export interface ExportColumn<T> {
  key: keyof T | string;
  header: string;
  format?: (row: T) => string | number;
}

function escapeCsvValue(value: string | number): string {
  const text = String(value ?? '');
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function exportToCsv<T extends Record<string, unknown>>(
  filename: string,
  rows: T[],
  columns: ExportColumn<T>[],
): void {
  const header = columns.map((col) => escapeCsvValue(col.header)).join(',');
  const body = rows
    .map((row) =>
      columns
        .map((col) => {
          const raw =
            col.format?.(row) ??
            (typeof col.key === 'string' ? (row[col.key] as string | number | null) : (row[col.key as keyof T] as string | number | null));
          return escapeCsvValue(raw ?? '');
        })
        .join(','),
    )
    .join('\n');

  const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function exportToPdfPlaceholder(title: string): void {
  window.print();
  void title;
}
