CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE ingestion_runs (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_file text NOT NULL,
  processing_time_ms integer NOT NULL DEFAULT 0 CHECK (processing_time_ms >= 0),
  rows_received integer NOT NULL DEFAULT 0, rows_accepted integer NOT NULL DEFAULT 0,
  rows_rejected integer NOT NULL DEFAULT 0, quality_score numeric(5,2) CHECK (quality_score BETWEEN 0 AND 100),
  user_email text NOT NULL, started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
  status text NOT NULL CHECK (status IN ('received','processing','completed','failed','duplicate_skipped'))
);

CREATE TABLE source_files (
  source_file_id bigserial PRIMARY KEY, run_id uuid REFERENCES ingestion_runs(run_id), file_name text NOT NULL,
  file_hash char(64) NOT NULL, size_bytes bigint NOT NULL CHECK (size_bytes > 0), encoding text,
  separator text, sheet_names jsonb NOT NULL DEFAULT '[]', uploaded_by text NOT NULL,
  uploaded_at timestamptz NOT NULL DEFAULT now(), status text NOT NULL,
  duplicate_of bigint REFERENCES source_files(source_file_id), UNIQUE(file_hash, file_name)
);

CREATE TABLE schema_templates (
  template_id bigserial PRIMARY KEY, source_name text NOT NULL, version integer NOT NULL DEFAULT 1,
  mapping jsonb NOT NULL, approved_by text NOT NULL, approved_at timestamptz NOT NULL DEFAULT now(),
  active boolean NOT NULL DEFAULT true, UNIQUE(source_name, version)
);
CREATE TABLE schema_mappings (
  mapping_id bigserial PRIMARY KEY, run_id uuid REFERENCES ingestion_runs(run_id), source_column text NOT NULL,
  canonical_column text NOT NULL, confidence numeric(5,4), review_status text NOT NULL,
  reviewed_by text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE quality_rules (
  rule_id text PRIMARY KEY, name text NOT NULL, dimension text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('warning','error')), expression text NOT NULL,
  effective_from date NOT NULL, active boolean NOT NULL DEFAULT true
);
CREATE TABLE quality_results (
  quality_result_id bigserial PRIMARY KEY, run_id uuid NOT NULL REFERENCES ingestion_runs(run_id),
  rule_id text NOT NULL REFERENCES quality_rules(rule_id), total_rows integer NOT NULL,
  failed_rows integer NOT NULL, pass_rate numeric(8,6) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE rejected_records (
  rejection_id bigserial PRIMARY KEY, run_id uuid NOT NULL REFERENCES ingestion_runs(run_id),
  source_row_number integer NOT NULL, record_payload jsonb NOT NULL, failed_rules text[] NOT NULL,
  rejection_reason text NOT NULL, rejected_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE accepted_records (
  accepted_record_id bigserial PRIMARY KEY, run_id uuid NOT NULL REFERENCES ingestion_runs(run_id),
  record_id text NOT NULL, transaction_date date NOT NULL, area text NOT NULL, metric_type text NOT NULL,
  entity_name text NOT NULL, amount numeric(18,2) NOT NULL, quantity numeric(18,4), budget numeric(18,2),
  status text, cycle_days numeric(10,2), source_system text NOT NULL, UNIQUE(run_id, record_id)
);
CREATE TABLE metric_definitions (
  metric_id text PRIMARY KEY, name text NOT NULL, definition text NOT NULL, formula text NOT NULL,
  granularity text NOT NULL, source_view text NOT NULL, owner text NOT NULL, frequency text NOT NULL,
  expected_min numeric, expected_max numeric, improvement_direction text NOT NULL,
  effective_date date NOT NULL, active boolean NOT NULL DEFAULT true
);
CREATE TABLE metric_results (
  metric_result_id bigserial PRIMARY KEY, metric_id text NOT NULL REFERENCES metric_definitions(metric_id),
  period date NOT NULL, value numeric NOT NULL, budget numeric, budget_variance numeric,
  calculated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(metric_id, period)
);
CREATE TABLE anomaly_results (
  anomaly_id bigserial PRIMARY KEY, metric_id text NOT NULL REFERENCES metric_definitions(metric_id),
  period date NOT NULL, observed_value numeric NOT NULL, expected_value numeric, variation numeric,
  method text NOT NULL, severity text NOT NULL, explanation text NOT NULL, source_view text NOT NULL,
  review_status text NOT NULL DEFAULT 'open', reviewed_by text, reviewed_at timestamptz
);
CREATE TABLE report_drafts (
  report_id text PRIMARY KEY, period date NOT NULL, content jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('Draft','Under Review','Approved','Rejected','Published')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE report_approvals (
  approval_id bigserial PRIMARY KEY, report_id text NOT NULL REFERENCES report_drafts(report_id),
  decision text NOT NULL CHECK (decision IN ('Approved','Rejected')), decided_by text NOT NULL,
  comment text, decided_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE audit_events (
  audit_event_id bigserial PRIMARY KEY, event_type text NOT NULL, actor text NOT NULL,
  object_type text NOT NULL, object_id text NOT NULL, details jsonb NOT NULL,
  event_hash char(64) NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE user_feedback (
  feedback_id bigserial PRIMARY KEY, interaction_id text NOT NULL, user_email text NOT NULL,
  rating smallint CHECK (rating BETWEEN 1 AND 5), comment text, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_ingestion_status_started ON ingestion_runs(status, started_at DESC);
CREATE INDEX idx_source_hash ON source_files(file_hash);
CREATE INDEX idx_quality_run_rule ON quality_results(run_id, rule_id);
CREATE INDEX idx_accepted_date_area ON accepted_records(transaction_date, area);
CREATE INDEX idx_metric_period ON metric_results(metric_id, period DESC);
CREATE INDEX idx_anomaly_open ON anomaly_results(review_status, severity, period DESC);
CREATE INDEX idx_audit_object ON audit_events(object_type, object_id, created_at DESC);

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
CREATE ROLE insightops_readonly NOLOGIN;
GRANT USAGE ON SCHEMA public TO insightops_readonly;

