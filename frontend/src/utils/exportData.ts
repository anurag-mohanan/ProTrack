export interface ExportColumn<T> {
  key: keyof T | string;
  header: string;
  format?: (row: T) => string | number;
}

function resolveValue<T extends Record<string, unknown>>(
  row: T,
  col: ExportColumn<T>,
): string | number {
  const raw =
    col.format?.(row) ??
    (typeof col.key === 'string'
      ? (row[col.key] as string | number | null)
      : (row[col.key as keyof T] as string | number | null));
  return raw ?? '';
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
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
    .map((row) => columns.map((col) => escapeCsvValue(resolveValue(row, col))).join(','))
    .join('\n');

  const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`);
}

function escapeXml(value: string | number): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Export to a genuine Excel workbook using the SpreadsheetML 2003 format.
 * Dependency-free and opens natively in Excel with numbers typed as numbers.
 */
export function exportToExcel<T extends Record<string, unknown>>(
  filename: string,
  rows: T[],
  columns: ExportColumn<T>[],
  sheetName = 'Report',
): void {
  const headerCells = columns
    .map(
      (col) =>
        `<Cell ss:StyleID="hdr"><Data ss:Type="String">${escapeXml(col.header)}</Data></Cell>`,
    )
    .join('');

  const bodyRows = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const value = resolveValue(row, col);
          const isNumber = typeof value === 'number' && Number.isFinite(value);
          const type = isNumber ? 'Number' : 'String';
          return `<Cell><Data ss:Type="${type}">${escapeXml(value)}</Data></Cell>`;
        })
        .join('');
      return `<Row>${cells}</Row>`;
    })
    .join('');

  const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="hdr"><Font ss:Bold="1"/><Interior ss:Color="#E3E8EF" ss:Pattern="Solid"/></Style>
 </Styles>
 <Worksheet ss:Name="${escapeXml(sheetName)}">
  <Table>
   <Row>${headerCells}</Row>
   ${bodyRows}
  </Table>
 </Worksheet>
</Workbook>`;

  const blob = new Blob([xml], { type: 'application/vnd.ms-excel;charset=utf-8;' });
  triggerDownload(blob, filename.endsWith('.xls') ? filename : `${filename}.xls`);
}

/**
 * Export to PDF by rendering a clean, print-ready report in a new window and
 * invoking the browser print dialog (Save as PDF). Dependency-free and prints
 * only the report table rather than the whole application.
 */
export function exportToPdf<T extends Record<string, unknown>>(
  filename: string,
  rows: T[],
  columns: ExportColumn<T>[],
  title?: string,
): void {
  const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=1024,height=768');
  if (!printWindow) {
    // Popup blocked — fall back to printing the current page.
    window.print();
    return;
  }

  const heading = title ?? filename;
  const headerCells = columns.map((col) => `<th>${escapeXml(col.header)}</th>`).join('');
  const bodyRows = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((col) => `<td>${escapeXml(resolveValue(row, col))}</td>`)
          .join('')}</tr>`,
    )
    .join('');

  const generated = new Date().toLocaleString();
  printWindow.document.write(`<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>${escapeXml(heading)}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Arial, Helvetica, sans-serif; color: #1a2432; margin: 24px; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .meta { color: #64748b; font-size: 12px; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
  thead th { background: #e3e8ef; font-weight: 700; }
  tbody tr:nth-child(even) { background: #f8fafc; }
  @media print { .no-print { display: none; } }
</style>
</head>
<body>
  <h1>${escapeXml(heading)}</h1>
  <div class="meta">Generated ${escapeXml(generated)} • ${rows.length} rows</div>
  <table>
    <thead><tr>${headerCells}</tr></thead>
    <tbody>${bodyRows}</tbody>
  </table>
  <script>
    window.onload = function () { window.focus(); window.print(); };
  </script>
</body>
</html>`);
  printWindow.document.close();
}
