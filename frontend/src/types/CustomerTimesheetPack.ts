export interface CustomerTimesheetAssociateRow {
  serial_no: number;
  user_id: string;
  associate_name: string;
  designation?: string | null;
  productive_hours: number;
  non_productive_hours: number;
  total_hours: number;
  utilization_percent: number;
  remarks?: string | null;
}

export interface CustomerTimesheetToolRow {
  tool_number: string;
  hours: number;
  comments?: string | null;
}

export interface CustomerTimesheetPackPayload {
  report_id: string;
  title: string;
  company_name: string;
  customer_id: string;
  customer_name: string;
  period: {
    period_type: string;
    label: string;
    start_date: string;
    end_date: string;
    working_days: number;
  };
  week_number?: number | null;
  working_hours_target: number;
  associates: CustomerTimesheetAssociateRow[];
  tools: CustomerTimesheetToolRow[];
  total_productive_hours: number;
  total_non_productive_hours: number;
  total_hours: number;
  overall_utilization_percent: number;
}
