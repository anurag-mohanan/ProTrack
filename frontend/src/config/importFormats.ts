/** Shared accept attributes and labels for data-import file pickers. */

export const IMPORT_ACCEPT_DEFAULT =
  '.xlsx,.xlsm,.pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12,application/pdf';

export const IMPORT_ACCEPT_WITH_CSV = `${IMPORT_ACCEPT_DEFAULT},.csv,text/csv`;

export const IMPORT_FORMAT_LABEL_DEFAULT =
  'Excel (.xlsx / .xlsm) or PDF (table layout with a header row)';

export const IMPORT_FORMAT_LABEL_WITH_CSV =
  'Excel (.xlsx / .xlsm), PDF (table layout), or CSV';
