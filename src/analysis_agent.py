# analysis_agent.py

import os
import json
import warnings
import pandas as pd
from openai import AzureOpenAI
from IPython.display import display, Markdown

warnings.filterwarnings("ignore")

class AnalysisAgent:
    def __init__(self, api_key, api_base, api_version, gpt_deployment, temperature=0.0):
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.gpt_deployment = gpt_deployment
        self.temperature = temperature
        self.client = AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.api_base,
            api_key=self.api_key
        )

    def parse_sql_result(self, json_data):
        """Convert JSON SQL result into a DataFrame."""
        data = json.loads(json_data)
        df = pd.DataFrame(data)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='ignore')
        return df

    def dynamic_analysis_prompt(self, business_question=None, inputs=None):
        """Generate the dynamic prompt for analysis based on available inputs."""
        inputs = inputs or {}

        sql_content = f"""
        SQL Query Used:
        {inputs.get('sql_query')}

        Query Result:
        {inputs.get('sql_result_df').to_string(index=False) if inputs.get('sql_result_df') is not None else ""}""" if inputs.get('sql_query') and inputs.get('sql_result_df') is not None else ""

        knowledge_content = f"""
        Knowledge Answer:
        {inputs.get('knowledge_answer')}""" if inputs.get('knowledge_answer') else ""

        vega_content = f"""
        Selected Visualization Type:
        {inputs.get('visualization_type')}

        Final Visualization JSON:
        {json.dumps(inputs.get('visualization_json'), indent=4)}""" if inputs.get('visualization_type') and inputs.get('visualization_json') else ""

        # Create and send prompt to the API
        response = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a data analyst specializing in generating concise business insights and summaries from data query results, \
                                validating knowledge-based answers, or integrating visual data representations where applicable. \
                                Use any provided SQL, visualization, or knowledge data to generate insights or clarify answers."
                },
                {
                    "role": "user",
                    "content": f"""Here is the information you need to generate insights:

                                Business Question:
                                {business_question}

                                {sql_content}

                                {knowledge_content}

                                {vega_content}

                                Please provide a concise summary of the top findings, limited to 4-5 sentences. Ensure any knowledge answers are validated and clarified, \
                                and integrate visualization insights if relevant. Avoid unnecessary details."""
                }
            ],
            model=self.gpt_deployment,
            temperature=self.temperature
        )
        return response.choices[0].message.content
