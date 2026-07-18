# Data quality design

Rules are evaluated after canonical mapping and before persistence in analytical views. Errors reject a record; warnings retain the record and create review evidence.

| Rule | Control | Severity |
|---|---|---|
| DQ001 | required fields | error |
| DQ002 | valid transaction date | error |
| DQ003 | numeric amount | error |
| DQ004 | non-negative amount | error |
| DQ005 | no future transaction date | error |
| DQ006 | unique business key | error |
| DQ007 | valid business area | error |
| DQ008 | non-negative quantity and cycle | error |
| DQ009 | IQR amount outlier | warning |

The executed sample keeps record-level rejection reasons and aggregate pass rates. Source-to-source volume drift and distribution baselines can be calibrated once production history exists.

