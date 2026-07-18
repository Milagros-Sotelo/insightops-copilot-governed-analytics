CREATE OR REPLACE VIEW vw_control_center AS
SELECT r.run_id, r.source_file, r.status, r.started_at, r.completed_at, r.processing_time_ms,
       r.rows_received, r.rows_accepted, r.rows_rejected, r.quality_score, r.user_email
FROM ingestion_runs r;

CREATE OR REPLACE VIEW vw_quality_summary AS
SELECT r.run_id, r.source_file, r.started_at::date AS run_date, r.rows_received,
       r.rows_accepted, r.rows_rejected, r.quality_score, r.status,
       CASE WHEN r.rows_received = 0 THEN 0 ELSE r.rows_rejected::numeric / r.rows_received END AS rejection_rate
FROM ingestion_runs r;

CREATE OR REPLACE VIEW vw_metric_monitoring AS
SELECT mr.period, md.metric_id, md.name, md.definition, md.formula, md.owner,
       md.improvement_direction, mr.value, mr.budget, mr.budget_variance
FROM metric_results mr JOIN metric_definitions md USING(metric_id)
WHERE md.active;

CREATE OR REPLACE VIEW vw_anomaly_center AS
SELECT a.anomaly_id, a.period, a.metric_id, md.name AS metric_name, a.observed_value,
       a.expected_value, a.variation, a.method, a.severity, a.explanation,
       a.source_view, a.review_status, a.reviewed_by, a.reviewed_at
FROM anomaly_results a JOIN metric_definitions md USING(metric_id);

CREATE OR REPLACE VIEW vw_report_review AS
SELECT report_id, period, content, status, created_at, updated_at
FROM report_drafts;

GRANT SELECT ON vw_control_center, vw_quality_summary, vw_metric_monitoring,
  vw_anomaly_center, vw_report_review TO insightops_readonly;

