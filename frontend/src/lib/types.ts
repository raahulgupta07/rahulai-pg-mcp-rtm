export interface Job {
  job_id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  total_outlets: number;
  class_a_count: number;
  class_b_count: number;
  class_c_count: number;
  wholesaler_count: number;
  total_revenue: number;
  threshold_a: number;
  threshold_b: number;
  date_from?: string;
  date_to?: string;
}

export interface OutletResult {
  BranchName: string;
  'Cus.Code': string;
  'Cus.Name': string;
  Classification: string;
  TotalSales_2Yr: number;
  TotalSales_12M: number;
  TotalSales_6M: number;
  TotalSales_3M: number;
  TotalPcs: number;
  TransactionCount: number;
  Overall_Contribution_Pct: number;
  CumulativePct: number;
  Is_Wholesaler: boolean;
  Frequency_2Yr: number;
  OutletChannel: string;
  AI_Growth_Signal?: string;
  AI_Risk_Level?: string;
  AI_Visit_Priority?: number;
  AI_Action?: string;
  AI_Insight?: string;
  [key: string]: any;
}

export interface ClassifyResponse {
  job_id: string;
  total_outlets: number;
  branches: string[];
  class_a: number;
  class_b: number;
  class_c: number;
  wholesalers: number;
  revenue: number;
  results: OutletResult[];
  branch_summary: BranchSummary[];
  insights: Record<string, string>;
  log: string[];
}

export interface BranchSummary {
  BranchName: string;
  Total_Outlets: number;
  Total_Revenue: number;
  Class_A_Count: number;
  Class_B_Count: number;
  Class_C_Count: number;
  Class_A_Pct: number;
}

export interface HealthResponse {
  status: string;
  pipeline: string;
  model: string;
}
