"""Built-in mock agents for testing and demos.

Mock agents analyze actual uploaded data and produce dynamic, realistic outputs.
They're used for testing when Databricks endpoints are stopped or unavailable.
"""

import json
import csv
import io
import time
import random
import re
from datetime import datetime


class MockAgent:
    """Base class for mock agents."""

    def __init__(self, name, display_name, description, icon, category):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.icon = icon
        self.category = category

    def process(self, input_data: str, context: dict = None) -> dict:
        """Process input data and return mock output."""
        raise NotImplementedError

    @staticmethod
    def parse_csv(data: str):
        """Parse CSV input and return headers + rows."""
        try:
            lines = data.strip().split('\n')
            headers = [h.strip() for h in lines[0].split(',')]
            rows = []
            for line in lines[1:]:
                if line.strip():
                    rows.append([c.strip() for c in line.split(',')])
            return headers, rows
        except Exception as e:
            print(f"[MOCK] CSV parse error: {e}")
            return [], []


class DataProfilerAgent(MockAgent):
    """Analyzes data structure, types, completeness, and anomalies."""

    def __init__(self):
        super().__init__(
            "mock_data_profiler",
            "Data Profiler",
            "Analyzes data structure, types, completeness, and anomalies. Generates profiling report.",
            "📊",
            "Data Quality"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(7, 9))  # Longer delay for visibility
        headers, rows = self.parse_csv(input_data)
        total_rows = len(rows)
        total_cols = len(headers)

        # Analyze each column
        col_analysis = []
        missing_total = 0
        for i, h in enumerate(headers):
            values = [r[i] if i < len(r) else '' for r in rows]
            non_empty = [v for v in values if v.strip()]
            missing = total_rows - len(non_empty)
            missing_total += missing
            unique = len(set(non_empty))
            col_analysis.append({
                "column": h,
                "non_null": len(non_empty),
                "missing": missing,
                "missing_pct": round(missing/total_rows*100, 1) if total_rows else 0,
                "unique": unique,
                "sample": non_empty[:3] if non_empty else []
            })

        completeness = round((1 - missing_total/(total_rows*total_cols))*100, 1) if total_rows*total_cols else 0
        quality_score = round(completeness * 0.7 + random.uniform(10, 25), 1)

        output = f"""# 📊 Data Profiling Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Dataset Overview
- **Total Records:** {total_rows}
- **Total Columns:** {total_cols}
- **Completeness:** {completeness}%
- **Overall Quality Score:** {quality_score}%

## Column Analysis
| Column | Non-Null | Missing | Missing% | Unique | Sample |
|--------|----------|---------|----------|--------|--------|
"""
        for ca in col_analysis:
            sample = ', '.join(ca['sample'][:2]) if ca['sample'] else '-'
            output += f"| {ca['column']} | {ca['non_null']} | {ca['missing']} | {ca['missing_pct']}% | {ca['unique']} | {sample} |\n"

        output += f"\n## Key Findings\n"
        for ca in col_analysis:
            if ca['missing_pct'] > 10:
                output += f"- ⚠️ **{ca['column']}** has {ca['missing_pct']}% missing values\n"
            if ca['unique'] == 1 and total_rows > 0:
                output += f"- 🔍 **{ca['column']}** has only 1 unique value (constant)\n"

        return {
            "output": output,
            "quality_score": quality_score,
            "duration_ms": random.randint(2000, 4000),
            "source": "MOCK"
        }


class DataQualityAgent(MockAgent):
    """Validates data against business rules."""

    def __init__(self):
        super().__init__(
            "mock_data_quality",
            "Quality Validator",
            "Validates data against business rules. Checks validity, completeness, consistency, uniqueness.",
            "✅",
            "Data Quality"
        )

    def process(self, input_data, context=None):
        time.sleep(6)  # 6 seconds for visibility
        headers, rows = self.parse_csv(input_data)
        total = len(rows)

        issues = []
        for i, row in enumerate(rows):
            row_dict = {headers[j]: row[j] if j < len(row) else '' for j in range(len(headers))}

            # Check email format
            email = row_dict.get('email', '')
            if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                issues.append(f"Row {i+2}: Invalid email '{email}'")

            # Check missing required fields
            for h in ['first_name', 'last_name', 'email']:
                if h in row_dict and not row_dict[h].strip():
                    issues.append(f"Row {i+2}: Missing '{h}'")

            # Check for future dates (data quality issue)
            dob = row_dict.get('date_of_birth', '')
            if dob and ('2028' in dob or '2030' in dob or '2025' in dob):
                issues.append(f"Row {i+2}: Future date_of_birth '{dob}'")

            # Check for negative loyalty points
            lp = row_dict.get('loyalty_points', '0')
            try:
                if int(lp) < 0:
                    issues.append(f"Row {i+2}: Negative loyalty_points '{lp}'")
            except:
                pass

        failed = len(set(i.split(':')[0] for i in issues))
        passed = total - failed
        score = round(passed/total*100, 1) if total else 0
        # Cap score at 65 to trigger quality checkpoint
        score = min(score, 65.0) if total > 0 else 0

        output = f"""# ✅ Data Quality Validation Report
**Overall Quality Score: {score}%**
**Status:** {'✅ Acceptable (≥80%)' if score >= 80 else '⚠️ Below Threshold (requires human review)'}

## Summary
- Total Records: {total}
- Passed: {passed} ✅ ({round(passed/total*100) if total else 0}%)
- Failed: {failed} ❌ ({round(failed/total*100) if total else 0}%)

## Issues Found ({len(issues)})
"""
        for issue in issues[:15]:
            output += f"- ❌ {issue}\n"

        if len(issues) > 15:
            output += f"- ... and {len(issues)-15} more issues\n"

        return {
            "output": output,
            "quality_score": score,
            "duration_ms": random.randint(1500, 3000),
            "source": "MOCK"
        }


class DataClassifierAgent(MockAgent):
    """Classifies columns by sensitivity (PII, PCI, PHI)."""

    def __init__(self):
        super().__init__(
            "mock_data_classifier",
            "PII Classifier",
            "Classifies columns by sensitivity (PII, PCI, PHI). Detects SSN, credit cards, emails.",
            "🔒",
            "Compliance"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(5, 7))  # 6 seconds for visibility
        headers, rows = self.parse_csv(input_data)

        pii_keywords = {
            'ssn': 'PII', 'social_security': 'PII',
            'email': 'PII', 'phone': 'PII',
            'name': 'PII', 'first_name': 'PII', 'last_name': 'PII',
            'address': 'PII', 'city': 'PII', 'state': 'PII', 'zip': 'PII',
            'dob': 'PII', 'date_of_birth': 'PII',
            'credit_card': 'PCI', 'card_number': 'PCI', 'cvv': 'PCI', 'credit': 'PCI',
            'diagnosis': 'PHI', 'treatment': 'PHI', 'patient_id': 'PHI'
        }

        classifications = []
        pii_detected = []

        for h in headers:
            h_lower = h.lower().replace(' ', '_')
            cat = 'General'
            risk = 'LOW'

            for kw, c in pii_keywords.items():
                if kw in h_lower:
                    cat = c
                    risk = 'CRITICAL' if c in ['PCI'] or kw in ['ssn', 'credit_card', 'credit', 'email'] else 'HIGH'
                    pii_detected.append(h)
                    break

            classifications.append({"column": h, "category": cat, "risk": risk})

        # Ensure restricted PII is detected for demo (SSN and credit cards)
        pii_detected = list(set(pii_detected))  # deduplicate
        for h in headers:
            h_lower = h.lower()
            if 'ssn' in h_lower and h not in pii_detected:
                pii_detected.append(h)
            if 'credit' in h_lower and h not in pii_detected:
                pii_detected.append(h)

        output = f"""# 🔒 Data Classification Report
**Columns Analyzed:** {len(headers)}

## Summary
- PII Columns: {sum(1 for c in classifications if c['category']=='PII')}
- PCI Columns: {sum(1 for c in classifications if c['category']=='PCI')}
- PHI Columns: {sum(1 for c in classifications if c['category']=='PHI')}
- General: {sum(1 for c in classifications if c['category']=='General')}

## Classifications
| Column | Category | Risk |
|--------|----------|------|
"""
        for c in classifications:
            emoji = {'PII': '👤', 'PCI': '💳', 'PHI': '🏥', 'General': '📋'}.get(c['category'], '📋')
            output += f"| {c['column']} | {emoji} {c['category']} | {c['risk']} |\n"

        if pii_detected:
            output += f"\n🔒 **Restricted PII detected in:** {', '.join(pii_detected)}\n"
            output += "**Recommendation:** Apply AES-256 encryption before loading to production.\n"

        return {
            "output": output,
            "pii_detected": pii_detected,
            "duration_ms": int(6000 + random.uniform(0, 2000)),
            "source": "MOCK"
        }


class AutoLoaderAgent(MockAgent):
    """Generates PySpark Auto Loader pipeline code."""

    def __init__(self):
        super().__init__(
            "mock_autoloader",
            "AutoLoader Pipeline",
            "Generates PySpark Auto Loader pipeline code for Databricks ingestion.",
            "🚀",
            "Data Engineering"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(4, 6))  # 5 seconds for visibility
        headers, rows = self.parse_csv(input_data)
        cols = ', '.join(f'"{h}"' for h in headers[:10])  # Show first 10 cols

        output = f"""# 🚀 Auto Loader Pipeline
**Target:** Unity Catalog Bronze Layer
**Columns:** {len(headers)}

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import *

spark = SparkSession.builder.appName("auto_loader").getOrCreate()

df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("header", "true")
    .option("cloudFiles.schemaLocation", "dbfs:/schemas/pipeline/")
    .load("dbfs:/raw_data/"))

df_enriched = (df
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", input_file_name()))

(df_enriched.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "dbfs:/checkpoints/pipeline/")
    .trigger(availableNow=True)
    .toTable("catalog.bronze.data_table"))
```

**Schema:** {cols}{"..." if len(headers) > 10 else ""}
**Estimated Rows:** {len(rows)}
**Status:** ✅ Pipeline code generated and ready for deployment"""

        return {
            "output": output,
            "duration_ms": random.randint(1000, 3000),
            "source": "MOCK"
        }


class SQLDeveloperAgent(MockAgent):
    """Generates SQL DDL and DML statements."""

    def __init__(self):
        super().__init__(
            "mock_sql_developer",
            "SQL Developer",
            "Generates SQL DDL, DML, views, and stored procedures from data schema.",
            "🗄️",
            "Data Engineering"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(1, 2.5))
        headers, rows = self.parse_csv(input_data)

        # Infer types based on column names
        col_defs = []
        for h in headers:
            h_lower = h.lower()
            if 'id' in h_lower:
                dtype = 'STRING'
            elif 'date' in h_lower or 'birth' in h_lower:
                dtype = 'DATE'
            elif 'point' in h_lower or 'score' in h_lower or 'amount' in h_lower:
                dtype = 'DOUBLE'
            elif 'active' in h_lower or 'is_' in h_lower:
                dtype = 'BOOLEAN'
            else:
                dtype = 'STRING'
            col_defs.append(f"    {h} {dtype}")

        output = f"""# 🗄️ SQL Schema Generation

## CREATE TABLE
```sql
CREATE TABLE IF NOT EXISTS bronze.data_table (
{chr(10).join(col_defs)},
    _ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _source_file STRING
)
USING DELTA
PARTITIONED BY (_ingested_at)
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');
```

## Quality Check View
```sql
CREATE VIEW silver.data_table_validated AS
SELECT *,
    CASE WHEN _ingested_at IS NOT NULL THEN TRUE ELSE FALSE END AS is_recent
FROM bronze.data_table
WHERE _ingested_at >= DATEADD(DAY, -7, CURRENT_TIMESTAMP);
```

**Row Count:** {len(rows)} records
**Columns:** {len(headers)}
**Status:** ✅ SQL generated and ready to execute"""

        return {
            "output": output,
            "duration_ms": random.randint(1000, 2500),
            "source": "MOCK"
        }


class PySparkTransformAgent(MockAgent):
    """Generates PySpark transformation code."""

    def __init__(self):
        super().__init__(
            "mock_pyspark_transform",
            "PySpark Transform",
            "Generates PySpark transformation code: cleaning, dedup, joins, aggregations.",
            "⚡",
            "Data Engineering"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(1, 2.5))
        headers, rows = self.parse_csv(input_data)
        id_col = headers[0] if headers else "id"

        output = f"""# ⚡ PySpark Transformation Pipeline

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

spark = SparkSession.builder.appName("transform").getOrCreate()

# Read source
df = spark.read.format("delta").table("bronze.data_table")
print(f"Source rows: {{df.count()}}")

# Step 1: Deduplication
df_dedup = df.dropDuplicates(["{id_col}"])

# Step 2: Clean & standardize
df_clean = (df_dedup
    .withColumn("_email", lower(trim(col("email"))))
    .withColumn("_name", initcap(trim(col("name"))))
    .na.fill({{"points": 0, "is_active": "false"}}))

# Step 3: Type casting
df_typed = (df_clean
    .withColumn("date_field", to_date(col("date_field"), "yyyy-MM-dd"))
    .withColumn("points", col("points").cast("integer"))
    .withColumn("is_active",
        when(col("is_active").isin("true","yes","1","TRUE"), True).otherwise(False)))

# Step 4: Data quality filter
df_valid = df_typed.filter(col("is_active").isNotNull())

# Step 5: Write to Silver
df_valid.write.format("delta").mode("overwrite").saveAsTable("silver.data_table")
print(f"Output rows: {{df_valid.count()}}")
```

**Input:** {len(rows)} rows × {len(headers)} columns
**Transformations:** Dedup → Clean → Type Cast → Validate → Write
**Target:** silver.data_table"""

        return {
            "output": output,
            "duration_ms": random.randint(1500, 3000),
            "source": "MOCK"
        }


class DocumentGeneratorAgent(MockAgent):
    """Generates data dictionaries and technical documentation."""

    def __init__(self):
        super().__init__(
            "mock_doc_generator",
            "Document Generator",
            "Generates data dictionaries, README docs, and technical documentation from schema.",
            "📝",
            "Documentation"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(1, 2))
        headers, rows = self.parse_csv(input_data)

        output = f"""# 📝 Data Dictionary — Auto-Generated

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Source:** Uploaded CSV ({len(rows)} records)

## Column Definitions

| # | Column | Description | Nullable | Example |
|---|--------|-------------|----------|---------|
"""
        for i, h in enumerate(headers):
            example = rows[0][i] if rows and i < len(rows[0]) else '-'
            desc = h.replace('_', ' ').title()
            nullable = '✅' if h.lower() not in [headers[0].lower(), 'id'] else '❌'
            output += f"| {i+1} | `{h}` | {desc} | {nullable} | {example} |\n"

        output += f"""
## Dataset Stats
- **Total Records:** {len(rows)}
- **Total Fields:** {len(headers)}
- **Primary Key:** {headers[0] if headers else 'N/A'}

## Usage Notes
- This dataset contains business data
- PII fields should be masked in non-production environments
- Recommended refresh frequency: Daily"""

        return {
            "output": output,
            "duration_ms": random.randint(800, 2000),
            "source": "MOCK"
        }


class NotificationAgent(MockAgent):
    """Sends pipeline status notifications."""

    def __init__(self):
        super().__init__(
            "mock_notification",
            "Notification Agent",
            "Sends pipeline status notifications via email, Slack, or Teams webhooks.",
            "🔔",
            "Operations"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(0.5, 1.5))

        results = context.get("results", {}) if context else {}
        quality_score = context.get("quality_score", 0) if context else 0
        pii = context.get("pii_detected", []) if context else []

        status = "✅ SUCCESS" if quality_score >= 60 else "❌ NEEDS REVIEW"

        output = f"""# 🔔 Pipeline Notification

**Status:** {status}
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Execution Summary
- Quality Score: {quality_score}%
- Agents Run: {len(results)}
- PII Detected: {', '.join(pii) if pii else 'None'}

## Notifications Sent
- ✅ Slack #data-pipeline-alerts
- ✅ Email: data-team@company.com
- ✅ Teams: Data Engineering Channel
- ✅ PagerDuty: {'Triggered (quality review needed)' if quality_score < 60 else 'Not triggered'}

## Next Steps
{'⚠️ Quality below 60% — manual review recommended before production deployment' if quality_score < 60 else '✅ All quality checks passed — pipeline approved for production'}"""

        return {
            "output": output,
            "duration_ms": random.randint(500, 1500),
            "source": "MOCK"
        }


class ValidationAgent(MockAgent):
    """Validates schema compatibility and detects drift."""

    def __init__(self):
        super().__init__(
            "mock_schema_validator",
            "Schema Validator",
            "Validates schema compatibility, detects drift, and checks source-target alignment.",
            "🔍",
            "Data Quality"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(1, 2))
        headers, rows = self.parse_csv(input_data)

        output = f"""# 🔍 Schema Validation Report

## Source Schema ({len(headers)} columns)
| Column | Inferred Type | Nullable | Constraint |
|--------|--------------|----------|------------|
"""
        for h in headers:
            h_lower = h.lower()
            if 'id' in h_lower:
                dtype, const = 'STRING', 'PRIMARY KEY'
            elif 'date' in h_lower:
                dtype, const = 'DATE', 'NOT NULL'
            elif 'email' in h_lower:
                dtype, const = 'STRING', 'UNIQUE'
            elif 'point' in h_lower or 'amount' in h_lower:
                dtype, const = 'DOUBLE', '>= 0'
            elif 'active' in h_lower:
                dtype, const = 'BOOLEAN', 'NOT NULL'
            else:
                dtype, const = 'STRING', '-'
            output += f"| {h} | {dtype} | {'NO' if const != '-' else 'YES'} | {const} |\n"

        output += f"""
## Validation Results
- ✅ Schema is valid
- ✅ No breaking changes detected
- ✅ All required columns present
- {'⚠️ ' + str(len([h for h in headers if 'ssn' in h.lower() or 'credit' in h.lower()])) + ' sensitive columns need encryption' if any('ssn' in h.lower() or 'credit' in h.lower() for h in headers) else '✅ No sensitive columns detected'}
- **Drift Score:** 0% (no schema changes)"""

        return {
            "output": output,
            "duration_ms": random.randint(1000, 2000),
            "source": "MOCK"
        }


class ConnectionTestAgent(MockAgent):
    """Tests connectivity and credentials."""

    def __init__(self):
        super().__init__(
            "mock_connection_test",
            "Connection Tester",
            "Tests Databricks workspace, storage, and catalog connectivity. Validates credentials.",
            "🔗",
            "Operations"
        )

    def process(self, input_data, context=None):
        time.sleep(random.uniform(1, 2))

        output = f"""# 🔗 Connection Test Results

**Workspace:** adb-1377606806062971.11.azuredatabricks.net
**Test Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Connectivity Tests
| Service | Status | Latency | Details |
|---------|--------|---------|---------|
| Databricks Workspace | ✅ Connected | 45ms | API v2.0 |
| Azure Blob Storage | ✅ Connected | 23ms | miteuscoesa01 |
| Unity Catalog | ✅ Connected | 67ms | retail_uc |
| Delta Lake | ✅ Connected | 34ms | DBFS mounted |
| MLflow Tracking | ✅ Connected | 89ms | Experiment active |
| Serving Endpoints | ✅ Connected | 156ms | {random.randint(2,4)} endpoints running |

## Credentials
- Token: ✅ Valid (expires in 87 days)
- Permissions: ✅ CAN_MANAGE on workspace
- Cluster: ✅ Auto-start enabled

## Recommendations
- All systems operational and ready for pipeline execution
- Consider enabling query result caching for improved performance"""

        return {
            "output": output,
            "duration_ms": random.randint(1000, 2000),
            "source": "MOCK"
        }


# Registry of all available mock agents
MOCK_AGENT_REGISTRY = {
    "mock_data_profiler": DataProfilerAgent(),
    "mock_data_quality": DataQualityAgent(),
    "mock_data_classifier": DataClassifierAgent(),
    "mock_autoloader": AutoLoaderAgent(),
    "mock_sql_developer": SQLDeveloperAgent(),
    "mock_pyspark_transform": PySparkTransformAgent(),
    "mock_doc_generator": DocumentGeneratorAgent(),
    "mock_notification": NotificationAgent(),
    "mock_schema_validator": ValidationAgent(),
    "mock_connection_test": ConnectionTestAgent(),
}


def get_mock_agent_list():
    """Return list of mock agents for the UI."""
    return [
        {
            "name": agent.name,
            "display_name": agent.display_name,
            "description": agent.description,
            "icon": agent.icon,
            "category": agent.category,
            "status": "Ready",
            "source": "MOCK",
            "type": "Mock Agent"
        }
        for agent in MOCK_AGENT_REGISTRY.values()
    ]


def get_mock_agent(name: str):
    """Get a mock agent by name."""
    return MOCK_AGENT_REGISTRY.get(name)
