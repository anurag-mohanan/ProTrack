import type { QuoteToDeliveryParams, QuoteToDeliveryReport } from '../types/QuoteToDelivery';
import { apiClient, buildQuery } from './client';
import { downloadReportExcel } from './engineeringPerformance';

export async function fetchQuoteToDelivery(params: QuoteToDeliveryParams): Promise<QuoteToDeliveryReport> {
  const { data } = await apiClient.get<QuoteToDeliveryReport>(
    `/reports/quote-to-delivery${buildQuery({ ...params })}`,
  );
  return data;
}

/** Exports every row matching the filters, search and drill-down (pagination is ignored). */
export async function downloadQuoteToDeliveryExcel(params: QuoteToDeliveryParams): Promise<void> {
  await downloadReportExcel(
    `/reports/quote-to-delivery/export.xlsx${buildQuery({ ...params, page: undefined, page_size: undefined })}`,
    'Quote_to_Delivery.xlsx',
  );
}

export const quoteToDeliveryQueryKeys = {
  report: (params: QuoteToDeliveryParams) => ['reports', 'quote-to-delivery', params] as const,
};
