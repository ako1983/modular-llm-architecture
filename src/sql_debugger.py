# sql_debugger.py
import os
import requests
import pandas as pd
import pandas_gbq
import google.auth
from google.cloud import bigquery
from pathlib import Path
from openai import AzureOpenAI
from azure.core.exceptions import HttpResponseError
import time
import sys
import os
import json
from IPython.display import display, Markdown
from sql_agent import SQLAgent
sys.path.append(os.path.abspath("../modules"))

from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)

logger.info("This is an info log from the current module.")


# Now you can import superAgent
from base_agent import SuperAgent
from json import JSONDecodeError


# We want this class to have the same functions as SQL agent,
class SQLDebugger(SQLAgent):
    def __init__(self, api_key, api_base, api_version, gpt_deployment):
        super().__init__(api_key, api_base, api_version, gpt_deployment)

        self.data_dir = Path("data")
        self.credentials, self.project = google.auth.default()

        # Load error templates and table structure
        with open("../data/error_fewshot.json") as f:
            self.error_templates = f.read()

        with open("../data/sql_schema.txt") as f:
            self.table_structure = f.read()

        # Create BigQuery client
        client = bigquery.Client()

        self.debug_system_prompt = """
            You are an expert in SQL. You're job is to be given erroneous SQL code and
            solve what is wrong with it and return the fixed code. 
    
            Rules:
            1. Simply return the corrected SQL code, no explanation is needed.
            2. No code block or backticks should be used.
            """
        self.functions = [
                {
                    "name": "send_query",
                    "description": "Send a provided sql query to be executed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql_query": {"type": "string", "description": "The SQL query to be executed."},
                            "description": {"type": "string", "description": "The  description of how the query was fixed"}
                           
                        },
                        "required": ["sql_code"],
                    },
                },
        ]



    def debug_sql(self, sql_query, column_results, user_question):
        """
        Debugs or improves the SQL code based on the error message or reason for improvement.
        """
        debug_user_prompt = f"""
            This SQL code is not working: {sql_query}. 
            The user had originally asked to produce SQL code based on this question: {user_question}.
            We think the error may be due to a strict equality clause. All possibilities of this equality clause have been queried here: {column_results}. Please check these results and see if there are any similar results that match with what the user may have been trying to spell.
    
            Please respond with how you are going to fix the sql_query. Additionally, execute the 'send_query' function with the new query: {self.functions}
            Simply fix the strict equality clause and nothing else
            Do not replace the strict equality clause with a 'LIKE' clause.
        """
        
        # Call GPT with the prompt
        response = self.call_gpt(debug_user_prompt, self.debug_system_prompt, functions=self.functions)
        
        # Extract function call
        if response.choices[0].message.function_call:
            function_call = response.choices[0].message.function_call
            if function_call.name == "send_query":
                try:
                    # Parse arguments
                    args = json.loads(function_call.arguments)
                    fixed_query = args.get("sql_query", "")
                    description = args.get("description", "")

                    return fixed_query, description
                except JSONDecodeError as e:
                    logger.error(f"Error decoding function arguments: {e}")
            else:
                logger.error(f"Unexpected function call: {function_call.name}")
        else:
            logger.error("No function call in GPT response.")
        
        return None, "Error: Unable to debug SQL."  

   # def kickoff(query)

    # Loop until there is not an empty result set. Give a max iteration of x
        # given an empty result set and the given query, we should follow routine steps:
            # Check for strict equality clauses (lookup all clauses) ("...Where title = 'Real Housewifes'")
                # lookup in big query all clauses and give to llm ( select names from fakedata)
                # Future/backlog: if the column name identifier is incorrect, we can try to fix by using the correct column name given the table metadata.
                # run it again in big query

    # Make sure the loop has context, to not repeat debugged steps.

    def query_column_data(self,sql_query, user_question):
        debug_system_prompt = f"""
                You are an agent in a multi-step process to query data based on a user's question. You have been called on because the original query generated by the SQL generation agent did not produce results. This is the original `user_question`: {user_question}. Here's the tables structure: {self.table_structure}.
                
                Your job is to identify strict equality clauses (e.g., "... WHERE title = 'Real housewives'") and generate a new query that retrieves **all distinct values** for the relevant column (e.g., `show_title`). This query will be used in a subsequent step to check if the original query's value contains any misspellings. 
                
                Fewshot:
                - Original query: `WHERE title = 'Real House wifes'`
                - Correct output: `SELECT DISTINCT title FROM <table_name> ORDER BY title;`
                
                Generate the query to return all possible distinct values for the specified column, avoiding any filtering clauses.
         
            Rules: 
            1. Please return nothing other than the sql query. Your output should be executed in SQL without having to parse anything out of your response.
            """

        debug_user_prompt = f"""

            Please determine a query to debug this query {sql_query}.
        """
        return self.call_gpt(debug_user_prompt, debug_system_prompt)
            

    def validate_and_fix_sql(self, sql_query, user_question, query_result):
        message_context = []
        description = 'Debug Agent was not run'
        i = 0
        # Continue to debug until the query result is not empty or it's tried 5 or so times.
        while query_result.empty and i < 3:
            print('query result is empty')

            # Get possiblities of strict clause
            column_query = self.query_column_data(sql_query, user_question)
            column_results = self.send_query(column_query)

            # Give possibilities and original question to llm
            sql_query, description = self.debug_sql(sql_query, column_results, user_question)
            print(description)
            print(sql_query)

            # Resend query
            query_result = self.send_query(sql_query)
            print(f"Query Result: {query_result}")
            i = i + 1 

        return sql_query, query_result, description
            



        