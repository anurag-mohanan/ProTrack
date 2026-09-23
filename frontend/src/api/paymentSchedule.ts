import { apiClient } from './client';
import type { CustomerPaymentMilestone } from '../types';

export type QuotePaymentScheduleSummary = {
  quote_id: string;
  payment_model?: string | null;
  payment_terms?: string | null;
  payment_terms_days?: number | null;
  payment_schedule_source?: string | null;
  awarded_amount: number;
  scheduled_invoice_percent: number;
  scheduled_invoice_amount: number;
  amount_already_invoiced: number;
  remaining_to_invoice: number;
  amount_collected: number;
  outstanding_amount: number;
  future_milestone_amount: number;
  ready_to_invoice_amount: number;
  not_yet_due_amount: number;
  overdue_amount: number;
  milestones: Array<{
    id: string;
    sequence: number;
    name: string;
    percentage?: number | null;
    scheduled_amount: number;
    trigger_type: string;
    trigger_status: string;
    invoice_status: string;
    payment_status: string;
    invoice_date?: string | null;
    invoice_number?: string | null;
    due_date?: string | null;
    paid_amount: number;
    outstanding_amount: number;
    payment_timing?: string;
    payment_terms_days?: number | null;
  }>;
  warnings?: string[];
};

export async function fetchCustomerPaymentMilestones(customerId: string) {
  const { data } = await apiClient.get<CustomerPaymentMilestone[]>(
    `/finance/customers/${customerId}/payment-milestones`,
  );
  return data;
}

export async function replaceCustomerPaymentMilestones(
  customerId: string,
  milestones: CustomerPaymentMilestone[],
  reason?: string,
) {
  const { data } = await apiClient.put<CustomerPaymentMilestone[]>(
    `/finance/customers/${customerId}/payment-milestones`,
    { milestones, reason },
  );
  return data;
}

export async function fetchQuotePaymentSchedule(quoteId: string) {
  const { data } = await apiClient.get<QuotePaymentScheduleSummary>(
    `/finance/quotes/${quoteId}/payment-schedule`,
  );
  return data;
}

export async function replaceQuotePaymentSchedule(
  quoteId: string,
  body: {
    payment_model?: string | null;
    payment_terms?: string | null;
    payment_terms_days?: number | null;
    milestones: CustomerPaymentMilestone[];
    reason?: string;
  },
) {
  const { data } = await apiClient.put<QuotePaymentScheduleSummary>(
    `/finance/quotes/${quoteId}/payment-schedule`,
    body,
  );
  return data;
}

export async function triggerQuotePaymentMilestone(quoteId: string, milestoneId: string) {
  const { data } = await apiClient.post<QuotePaymentScheduleSummary>(
    `/finance/quotes/${quoteId}/payment-milestones/${milestoneId}/trigger`,
  );
  return data;
}
