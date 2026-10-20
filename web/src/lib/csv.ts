/**
 * CSV export, client-side only. No API call and no dependency: a treasury
 * export is a snapshot of what the reader is looking at right now, not a
 * server resource, so there is nothing here for the backend to own.
 */

export type CsvColumn<T> = {
  header: string;
  value: (row: T) => string | number | null | undefined;
};

/** RFC 4180: a field is quoted whenever it could otherwise be misread. */
function csvCell(value: string | number | null | undefined): string {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv<T>(rows: T[], columns: CsvColumn<T>[]): string {
  const lines = [columns.map((c) => csvCell(c.header)).join(',')];
  for (const row of rows) {
    lines.push(columns.map((c) => csvCell(c.value(row))).join(','));
  }
  // CRLF is the RFC 4180 line ending and what Excel expects without a
  // "text looks like one long line" repair prompt on open.
  return lines.join('\r\n');
}

/**
 * Blob + object URL, revoked once the click has been dispatched. No part of
 * this touches the network: the file never leaves the browser's own memory.
 */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
