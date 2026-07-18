let
    Source = PostgreSQL.Database(ParameterServer, ParameterDatabase),
    MetricMonitoring = Source{[Schema="public", Item="vw_metric_monitoring"]}[Data],
    Typed = Table.TransformColumnTypes(
        MetricMonitoring,
        {{"period", type date}, {"value", type number}, {"budget", type number}, {"budget_variance", Percentage.Type}}
    ),
    CleanMetricId = Table.TransformColumns(Typed, {{"metric_id", each Text.Upper(Text.Trim(_)), type text}}),
    ValidRows = Table.SelectRows(CleanMetricId, each [period] <> null and [metric_id] <> null)
in
    ValidRows
