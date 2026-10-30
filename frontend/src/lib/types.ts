/** Typed mirror of the backend OpenAPI schemas (app/schemas/*). */

export type NormalizedLabel = "positive" | "negative" | "neutral";

export interface Health {
  status: string;
  app: string;
  version: string;
  database: "ok" | "unreachable";
  registered_models: number;
}

export interface ModelCardOut {
  description: string;
  intended_domain: string;
  limitations: string[];
  calibration: string;
  training_provenance: string;
}

export interface ModelOut {
  key: string;
  display_name: string;
  family: string;
  version: string;
  labels: string[];
  supports_neutral: boolean;
  provenance: string;
  source: string;
  enabled: boolean;
  cached: boolean | null;
  download_required: boolean;
  card: ModelCardOut | null;
}

export interface PredictionOut {
  model_key: string;
  model_version: string;
  model_display_name: string;
  label: NormalizedLabel;
  probabilities: Record<string, number>;
  confidence: number;
  latency_ms: number;
  supports_neutral: boolean;
}

export interface SingleAnalyzeResponse {
  text_chars: number;
  predictions: PredictionOut[];
}

export interface BatchPredictionOut extends PredictionOut {
  text_index: number;
}

export interface BatchAnalyzeResponse {
  count: number;
  batch_latency_ms: number;
  predictions: BatchPredictionOut[];
}

export interface DatasetIngestStats {
  row_count: number;
  valid_rows: number;
  duplicate_rows: number;
  missing_text_rows: number;
  invalid_label_rows: number;
  unparseable_timestamp_rows: number;
}

export interface ReviewOut {
  id: number;
  external_id: string | null;
  text: string;
  label: NormalizedLabel | null;
  raw_label: string | null;
  review_timestamp: string | null;
}

export interface DatasetOut {
  id: string;
  name: string;
  original_filename: string;
  encoding: string;
  text_column: string;
  label_column: string | null;
  id_column: string | null;
  timestamp_column: string | null;
  stats: DatasetIngestStats;
  file_size_bytes: number;
  ingest_warnings: string[];
  created_at: string;
}

export interface DatasetCreatedResponse extends DatasetOut {
  preview: ReviewOut[];
}

export interface ReviewPage {
  items: ReviewOut[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface EvaluationMetrics {
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1_macro: number | null;
  f1_weighted: number | null;
  confusion_matrix: number[][] | null;
  per_class: Record<string, Record<string, number>> | null;
}

export interface EvaluationOut {
  artifact: string;
  model_key: string;
  evaluation_type: "reproduced" | "historical_reference";
  created_at: string | null;
  dataset: Record<string, unknown>;
  metrics: EvaluationMetrics;
  config: Record<string, unknown>;
  notes: string | null;
}

export interface ModelCompareResponse {
  evaluations: EvaluationOut[];
}

export interface ErrorEnvelope {
  error: { code: string; message: string; details?: Record<string, unknown> | null };
}
