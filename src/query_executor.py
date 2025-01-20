# module/query_executor.py
import pandas_gbq
import google.auth
from pandas_gbq.gbq import GenericGBQException
from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)

logger.info("This is an info log from the current module.")

# from google.cloud import bigquery
credentials, project = google.auth.default()
project_id = "nbcu-ds-sandbox-b-001"


class QueryExecutor:
    def __init__(self, project_id, credentials):
        self.project_id = project_id
        self.credentials = credentials

    def send_query(self, query):
        try:
            indata = pandas_gbq.read_gbq(
                query,
                project_id=project_id,
                credentials=credentials,
                progress_bar_type="tqdm_notebook",
            )
            if len(indata) == 0:
                return "Data returned no records, try again"
        except GenericGBQException as e:
            return f"General Error: {e}"

        return indata