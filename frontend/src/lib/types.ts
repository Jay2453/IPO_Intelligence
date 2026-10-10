export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface IPOEvent {
  id: string;
  ipo_id: string;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  headline: string;
  description?: string | null;
  event_timestamp: string;
  created_at: string;
}

export interface Document {
  id: string;
  ipo_id?: string | null;
  document_type: string;
  issuer_name?: string | null;
  version_number: number;
  file_name: string;
  file_url: string;
  source_url?: string | null;
  file_hash_sha256: string;
  file_size_bytes?: number | null;
  filing_date?: string | null;
  retrieval_timestamp?: string | null;
  is_current: boolean;
  extraction_status: string; // PENDING, EXTRACTED, FAILED, UNMATCHED, REVIEW_REQUIRED
  extraction_error?: string | null;
  extracted_metadata?: Record<string, any> | null;
  created_at: string;
}

export interface FinancialObservation {
  id: string;
  ipo_id: string;
  source_document_id?: string | null;
  fiscal_year: string;
  period_months: number;
  statement_type?: string | null;
  is_restated?: boolean;
  currency?: string;
  unit?: string;
  revenue_crores?: number | null;
  ebitda_crores?: number | null;
  pat_crores?: number | null;
  total_assets_crores?: number | null;
  net_worth_crores?: number | null;
  total_liabilities_crores?: number | null;
  total_debt_crores?: number | null;
  operating_cash_flow_crores?: number | null;
  roe_pct?: number | null;
  roce_pct?: number | null;
  eps_inr?: number | null;
  nav_per_share_inr?: number | null;
  source_page?: number | null;
  extraction_method?: string | null;
  verification_status?: string;
  raw_data_provenance?: Record<string, any> | null;
  created_at: string;
}

export interface SubscriptionSnapshot {
  id: string;
  ipo_id: string;
  snapshot_time: string;
  qib_subscription_times?: number | null;
  nii_subscription_times?: number | null;
  rii_subscription_times?: number | null;
  employee_subscription_times?: number | null;
  total_subscription_times?: number | null;
  total_shares_bid?: number | null;
  created_at: string;
}

export interface MarketObservation {
  id: string;
  ipo_id: string;
  observation_type: string;
  observation_time: string;
  gmp_inr?: number | null;
  gmp_percent?: number | null;
  final_issue_price_inr?: number | null;
  listing_open_price_inr?: number | null;
  listing_close_price_inr?: number | null;
  listing_gain_pct?: number | null;
  bhavcopy_verified: boolean;
  created_at: string;
}

export interface ModelVersion {
  id: string;
  model_name: string;
  version_tag: string;
  algorithm: string;
  training_cutoff_date?: string | null;
  validation_metrics?: Record<string, any> | null;
  feature_manifest?: string[] | null;
  is_active: boolean;
  created_at: string;
}

export interface Prediction {
  id: string;
  ipo_id: string;
  model_version_id: string;
  prediction_timestamp: string;
  forecast_horizon: string;
  positive_return_prob?: number | null;
  predicted_return_pct?: number | null;
  risk_decile?: number | null;
  feature_snapshot?: Record<string, any> | null;
  evidence_summary?: Record<string, any> | null;
  prediction_status: string;
  created_at: string;
  model_version?: ModelVersion | null;
}

export interface IPOSummary {
  id: string;
  symbol?: string | null;
  company_name: string;
  exchange: string;
  category: string;
  lifecycle_status: string;
  min_price?: number | null;
  max_price?: number | null;
  lot_size?: number | null;
  issue_size_crores?: number | null;
  fresh_issue_crores?: number | null;
  ofs_crores?: number | null;
  open_date?: string | null;
  close_date?: string | null;
  allotment_date?: string | null;
  refund_date?: string | null;
  credit_date?: string | null;
  listing_date?: string | null;
  face_value?: number | null;
  lead_managers?: string | null;
  registrar?: string | null;
  data_completeness_pct: number;
  analysis_status: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  latest_gmp_inr?: number | null;
  latest_gmp_percent?: number | null;
  total_subscription_times?: number | null;
  positive_return_prob?: number | null;
  risk_decile?: number | null;
}

export interface IPODetail extends IPOSummary {
  events: IPOEvent[];
  documents: Document[];
  financials: FinancialObservation[];
  subscriptions: SubscriptionSnapshot[];
  market_observations: MarketObservation[];
  predictions: Prediction[];
}

export interface IntegrationStatus {
  name: string;
  status: string;
  verified: boolean;
  last_check_timestamp?: string | null;
  last_successful_sync?: string | null;
  error_count_last_24h: number;
  message: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  environment: string;
  timestamp: string;
  version: string;
}

export interface SystemStatusResponse {
  database_connected: boolean;
  total_ipos_tracked: number;
  real_ipos_count: number;
  demo_ipos_count: number;
  last_successful_sync?: string | null;
  last_sync_status?: string | null;
  recent_errors: string[];
  integrations: IntegrationStatus[];
  timestamp: string;
}

export interface IngestionJob {
  id: string;
  job_type: string;
  source_system: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  records_processed: number;
  error_details?: string | null;
  created_at: string;
}
