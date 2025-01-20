# module/sql_agent.py
from common_imports import *
from base_agent import SuperAgent
from query_executor import QueryExecutor

import pandas_gbq
import google.auth

credentials, project = google.auth.default()
project_id = "nbcu-ds-sandbox-b-001"

from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)

logger.info("This is an info log from the current module.")


class SQLAgent(SuperAgent):
    def __init__(self, api_key, api_base, api_version, gpt_deployment):
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.gpt_deployment = gpt_deployment
        self.name = "sql_agent"
        self.client = AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.api_base,
            api_key=self.api_key,
        )

        # Initialize the parent class
        super().__init__("SQL Agent", api_key, api_base, api_version, gpt_deployment)

        # Load SQL-specific resources
        with open("../data/sql_schema.txt", "r") as f:
            self.table_structure = f.read()

        with open("../data/sample_queries.json", "r") as f:
            self.sample_queries = json.load(f)

    def generate_query(self, question):
        # Start timer
        start_time = time.time()

        # Prepare the system and user prompts
        system_prompt = (
            "You are an expert data analyst specializing in Google Cloud's BigQuery. "
            "Your task is to generate efficient, optimized, and accurate BigQuery SQL queries based on the user's input. "
            "Ensure you understand the table structure, relationships, and requirements before generating SQL. "
            "Important instructions:\n"
            "- Avoid using nested analytic functions (window functions) directly in calculations. "
            "When necessary, split calculations into multiple steps using Common Table Expressions (CTEs).\n"
            "- Ensure that all non-aggregated columns are included in the GROUP BY clause.\n"
            "- Date columns are already in DATE format and should not be parsed.\n"
            "- Avoid using reserved keywords (e.g., CURRENT, SELECT) as aliases in SQL queries. Instead, use descriptive alternatives like 'current_week' or 'recent'.\n"
            "- Always consider that the current date is the most recent date in the table."
            "- Ensure division by zero is handled in calculations. For example, use CASE statements to avoid errors.\n"
            "- Validate that time ranges (e.g., fiscal_week_id) are sequential and do not skip values, as this may affect calculations.\n"
            "- If the query involves week-over-week calculations, limit the output to the most recent week or provide an option to include only the last N weeks.\n"
            "- For ranking or highlighting top results, sort by relevant metrics (e.g., percentage increase) and use LIMIT clauses if necessary."
        )

        user_prompt = (
            f"Here is the table structure and a sample query for reference:\n\n"
            f"Table Structure:\n{self.table_structure}\n\n"
            "Example Query:\n"
            "To avoid nested window functions, use CTEs like this:\n"
            "WITH genre_views AS (\n"
            "  SELECT genres, fiscal_week_id, SUM(views) OVER (PARTITION BY genres ORDER BY fiscal_week_id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS recent_views\n"
            "),\n"
            "genre_comparison AS (\n"
            "  SELECT genres, recent_views - previous_views AS views_increase FROM genre_views\n"
            ")\n"
            "SELECT genres, views_increase FROM genre_comparison ORDER BY views_increase DESC;\n\n"
            f"Sample Queries:\n{self.sample_queries}\n\n"
            "Business Question:\n"
            f"{question}\n\n"
            "Generate the SQL query to answer the business question. Only return the SQL code without formatting, code block delimiters, or backticks."
            "Avoid using reserved keywords as aliases."
        )

        try:
            # Use the parent class method to call GPT
            query = self.call_gpt(user_prompt, system_prompt)
            if query:
                # Ensure query is not None or empty
                return query

            else:
                raise ValueError("Query generation returned an empty result.")

        except Exception as e:
            print(f"An error occurred while generating the query: {e}")
            return None

        # End timer and calculate execution time
        execution_time = time.time() - start_time
        print(f"Execution time: {round(execution_time, 2)} seconds")

        return query

    def send_query(self, query):
        try:
            indata = pandas_gbq.read_gbq(
                query,
                project_id="nbcu-ds-sandbox-b-001",
                credentials=credentials,
                progress_bar_type=None,
                # progress_bar_type="tqdm_notebook",
            )
            if len(indata) == 0:
                message = "Data returned no records, try again."
                print(message)  # Standard output

        except pandas_gbq.gbq.GenericGBQException as e:
            return f"General Error: {e}"
        except Exception as e:
            print(f"General Error: {e}")
        return indata
