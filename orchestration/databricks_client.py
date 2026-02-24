"""
Databricks integration module.
Handles connections to Databricks workspaces, APIs, and serving endpoints.
"""

import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()


class DatabricksConfig:
    """Configuration for Databricks workspace connection"""

    def __init__(self):
        self.host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
        self.token = os.getenv("DATABRICKS_TOKEN", "")
        self.workspace_id = os.getenv("DATABRICKS_WORKSPACE_ID", "")

    def is_configured(self) -> bool:
        """Check if Databricks is properly configured"""
        return bool(self.host and self.token)

    def get_api_url(self, endpoint: str) -> str:
        """Build full API URL"""
        return f"{self.host}/api/2.1{endpoint}"

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }


class DatabricksClient:
    """Main client for Databricks API interactions"""

    def __init__(self):
        self.config = DatabricksConfig()
        self.http_client = httpx.AsyncClient(
            headers=self.config.get_headers(),
            timeout=30.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def call_api(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call Databricks API endpoint.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data

        Returns:
            Response JSON
        """
        if not self.config.is_configured():
            raise Exception("Databricks not configured. Set DATABRICKS_HOST and DATABRICKS_TOKEN")

        url = self.config.get_api_url(endpoint)

        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                json=data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"Databricks API error: {str(e)}")

    async def list_tables(
        self,
        catalog: str = "main",
        schema: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        List Delta tables in a catalog/schema.

        Args:
            catalog: Catalog name (Unity Catalog)
            schema: Schema name

        Returns:
            List of table metadata
        """
        try:
            response = await self.call_api(
                "GET",
                f"/unity-catalog/tables?catalog_name={catalog}&schema_name={schema}",
            )
            return response.get("objects", [])
        except Exception as e:
            print(f"Error listing tables: {e}")
            return []

    async def get_table_metadata(
        self,
        full_name: str,  # catalog.schema.table
    ) -> Dict[str, Any]:
        """
        Get detailed metadata for a table.

        Args:
            full_name: Full table name in format: catalog.schema.table

        Returns:
            Table metadata including columns, properties
        """
        try:
            response = await self.call_api(
                "GET",
                f"/unity-catalog/tables/{full_name}",
            )
            return response
        except Exception as e:
            print(f"Error getting table metadata: {e}")
            return {}

    async def list_endpoints(self) -> List[Dict[str, Any]]:
        """
        List Model Serving endpoints in workspace.

        Returns:
            List of serving endpoints
        """
        try:
            response = await self.call_api(
                "GET",
                "/serving-endpoints",
            )
            return response.get("endpoints", [])
        except Exception as e:
            print(f"Error listing endpoints: {e}")
            return []

    async def get_endpoint_status(self, endpoint_name: str) -> Dict[str, Any]:
        """
        Get status of a specific serving endpoint.

        Args:
            endpoint_name: Name of the endpoint

        Returns:
            Endpoint status and details
        """
        try:
            response = await self.call_api(
                "GET",
                f"/serving-endpoints/{endpoint_name}",
            )
            return response
        except Exception as e:
            print(f"Error getting endpoint status: {e}")
            return {"status": "error", "message": str(e)}

    async def query_workspace(self, sql: str, warehouse_id: str) -> List[Dict[str, Any]]:
        """
        Execute a SQL query on Databricks workspace.

        Args:
            sql: SQL query to execute
            warehouse_id: SQL Warehouse ID

        Returns:
            Query results
        """
        try:
            # Execute query via SQL statement API
            execute_response = await self.call_api(
                "POST",
                "/sql/statements",
                {
                    "warehouse_id": warehouse_id,
                    "statement": sql,
                    "byte_limit": 1000000,
                },
            )

            statement_id = execute_response.get("statement_id")

            # Get results
            results_response = await self.call_api(
                "GET",
                f"/sql/statements/{statement_id}",
            )

            results = results_response.get("result", {}).get("data_array", [])
            return results
        except Exception as e:
            print(f"Error executing query: {e}")
            return []


class DatabricksVectorSearch:
    """Vector Search integration for RAG"""

    def __init__(self, client: DatabricksClient):
        self.client = client

    async def search(
        self,
        index_name: str,
        query_text: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search a Vector Search index.

        Args:
            index_name: Full name of vector search index
            query_text: Query text to search for
            top_k: Number of results to return

        Returns:
            List of search results with similarity scores
        """
        try:
            response = await self.client.call_api(
                "POST",
                "/vector-search/indexes/query",
                {
                    "index_name": index_name,
                    "query_text": query_text,
                    "num_results": top_k,
                },
            )
            return response.get("results", [])
        except Exception as e:
            print(f"Error searching vector index: {e}")
            return []


class DatabricksDeployment:
    """Deployment operations for orchestration solutions"""

    def __init__(self, client: DatabricksClient):
        self.client = client

    async def create_or_update_job(
        self,
        job_name: str,
        notebook_path: str,
        cluster_config: Dict[str, Any],
        schedule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a Databricks job.

        Args:
            job_name: Name of the job
            notebook_path: Path to notebook to execute
            cluster_config: Cluster configuration
            schedule: Optional job schedule (cron syntax)

        Returns:
            Job configuration and ID
        """
        try:
            job_config = {
                "name": job_name,
                "tasks": [
                    {
                        "task_key": "main",
                        "notebook_task": {
                            "notebook_path": notebook_path,
                            "base_parameters": {},
                        },
                        "new_cluster": cluster_config,
                    }
                ],
            }

            if schedule:
                job_config["schedule"] = schedule

            response = await self.client.call_api(
                "POST",
                "/jobs/create",
                job_config,
            )

            return {
                "job_id": response.get("job_id"),
                "status": "created",
                "job_name": job_name,
            }
        except Exception as e:
            print(f"Error creating job: {e}")
            return {"status": "error", "message": str(e)}

    async def deploy_model(
        self,
        model_name: str,
        model_version: str,
        endpoint_name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Deploy a model to a serving endpoint.

        Args:
            model_name: MLflow model name
            model_version: Model version to deploy
            endpoint_name: Serving endpoint name
            config: Endpoint configuration

        Returns:
            Deployment status
        """
        try:
            # Create or update serving endpoint
            endpoint_config = {
                "name": endpoint_name,
                "config": config,
                "served_models": [
                    {
                        "model_name": model_name,
                        "model_version": model_version,
                        "workload_size": "Small",
                        "scale_to_zero_enabled": True,
                    }
                ],
            }

            # Check if endpoint exists
            try:
                await self.client.get_endpoint_status(endpoint_name)
                # Update existing
                response = await self.client.call_api(
                    "PUT",
                    f"/serving-endpoints/{endpoint_name}/config",
                    endpoint_config,
                )
            except:
                # Create new
                response = await self.client.call_api(
                    "POST",
                    "/serving-endpoints",
                    endpoint_config,
                )

            return {
                "endpoint_name": endpoint_name,
                "status": "deployed",
                "model": f"{model_name}:{model_version}",
            }
        except Exception as e:
            print(f"Error deploying model: {e}")
            return {"status": "error", "message": str(e)}

    async def get_deployment_status(self, endpoint_name: str) -> Dict[str, Any]:
        """
        Get deployment status for an endpoint.

        Args:
            endpoint_name: Serving endpoint name

        Returns:
            Deployment status and health
        """
        try:
            status = await self.client.get_endpoint_status(endpoint_name)
            return {
                "endpoint_name": endpoint_name,
                "state": status.get("state"),
                "created_at": status.get("creation_timestamp"),
                "last_updated": status.get("last_state_update_timestamp"),
                "served_models": status.get("served_models", []),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class DatabricksMLflow:
    """MLflow tracking integration"""

    def __init__(self, client: DatabricksClient):
        self.client = client

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """Get MLflow run details"""
        try:
            response = await self.client.call_api(
                "GET",
                f"/mlflow/runs/get?run_id={run_id}",
            )
            return response.get("run", {})
        except Exception as e:
            print(f"Error getting run: {e}")
            return {}

    async def log_metric(
        self,
        run_id: str,
        metric_name: str,
        metric_value: float,
        step: int = 0,
    ) -> bool:
        """Log a metric to MLflow"""
        try:
            await self.client.call_api(
                "POST",
                "/mlflow/runs/log-metric",
                {
                    "run_id": run_id,
                    "key": metric_name,
                    "value": metric_value,
                    "step": step,
                },
            )
            return True
        except Exception as e:
            print(f"Error logging metric: {e}")
            return False


# Global instances
databricks_client: Optional[DatabricksClient] = None
vector_search: Optional[DatabricksVectorSearch] = None
deployment: Optional[DatabricksDeployment] = None
mlflow_tracker: Optional[DatabricksMLflow] = None


def initialize_databricks():
    """Initialize Databricks clients"""
    global databricks_client, vector_search, deployment, mlflow_tracker

    databricks_client = DatabricksClient()

    if databricks_client.config.is_configured():
        vector_search = DatabricksVectorSearch(databricks_client)
        deployment = DatabricksDeployment(databricks_client)
        mlflow_tracker = DatabricksMLflow(databricks_client)
        print("✅ Databricks clients initialized successfully")
    else:
        print("⚠️  Databricks not configured. Set DATABRICKS_HOST and DATABRICKS_TOKEN")
