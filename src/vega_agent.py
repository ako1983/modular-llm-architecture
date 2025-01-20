import os, re, json, sys, pandas as pd, numpy as np, random, copy
from pathlib import Path
from datetime import datetime, timedelta
import requests
import time
import string
from json import JSONDecodeError
from openai import AzureOpenAI, OpenAIError
from azure.core.exceptions import HttpResponseError
import os
import autogen
from autogen import ConversableAgent
import autogen.agentchat.groupchat as gc
# from duckduckgo_search import DDGS
from typing import Annotated
import random
from autogen import UserProxyAgent, AssistantAgent
import openai
from base_agent import SuperAgent

class VegaAgent(SuperAgent):
    def __init__(self, api_key, api_base, api_version, gpt_deployment):
        super().__init__("Vega Agent", api_key, api_base, api_version, gpt_deployment)

        self.data_dir = Path('data')
        self.visualization_guide = None
        self.visualizations_templates = None
        self.load_visualization_guide()
        self.load_visualization_templates()
        self.sql_data = None

    def load_visualization_guide(self):
        with open("../data/json_templates/visualization_guide.json", "r") as f:
            self.visualization_guide = json.load(f)

    def load_visualization_templates(self):
        with open("../data/json_templates/visualization_templates.json", "r") as f:
            self.visualizations_templates = json.load(f)

     
    def choose_visualization(self, sample_data, row_count, additional_user_prompt):
        system_prompt = f"""
        You are an expert data visualization assistant specializing in selecting the most appropriate graph types for various datasets and queries. 
        Given the input data and the user's description of what they want to visualize, 
        your task is to return the name of the best Vega graph type
        
        Here are the available visualizations you may choose from:
        
        {self.visualization_guide}
        You will be given a data file and based on that, you will return only the name of the most appropriate graph type.
    
        
        Guidelines for choosing a visualization:
        1. For data with multiple series over time, prefer line charts.
        2. For data comparing categories or groups, consider bar charts.
        3. For data with a single series or a few categories, use simpler charts like line charts or bar charts as appropriate.
        4. If the data includes bounds and you need to visualize ranges or distributions, choose visualizations that can handle these features.
    
        Rules: 
        1. Simply return the name of the visualization key and nothing else
    
        """
        
        user_prompt = f"""
        return me the name of the visualization that would best describe this data: {sample_data}. 
        This sample data contains the numerical bounds as well as other random data
        The real data contains {row_count} rows.   
        """
    
        response = self.call_gpt(system_prompt, user_prompt)
    
        
        
        return response
        
    def inject_data(self, json_response, original_data):
        # Not converting all values to strings leads to probblems with converting date time strings to json
        #values = original_data.to_dict(orient='records')

        # This ensures all columns may be converted to json
        values = original_data.applymap(str).to_dict(orient='records')

        json_response['data']['values'] = values
    
        return json_response


    def get_sampling(self, full_data, count):
        # Extract date information if available
        date_columns = full_data.select_dtypes(include='datetime').columns
        
        # Get the bounds for all numeric columns
        bounds = {}
        for column in full_data.select_dtypes(include='number').columns:
            column_min = full_data[column].min()
            column_max = full_data[column].max()
            bounds[column] = [column_min, column_max]
    
        
        # Extract one row per bound for each numeric column
        bounds_rows = pd.DataFrame()  # Initialize empty DataFrame
        for col, (col_min, col_max) in bounds.items():
            # Get one row for the minimum bound
            min_row = full_data[full_data[col] == col_min].head(1)
            # Get one row for the maximum bound
            max_row = full_data[full_data[col] == col_max].head(1)
            # Append to the bounds rows
            bounds_rows = pd.concat([bounds_rows, min_row, max_row])
        
        bounds_rows = bounds_rows.drop_duplicates()
        
        # Ensure rows with the first and last date are included
        if len(date_columns) > 0:
            date_col = date_columns[0]  # Assuming there's only one date column
            first_date = full_data[date_col].min()
            last_date = full_data[date_col].max()
            bounds_rows = pd.concat([
                bounds_rows,
                full_data[full_data[date_col] == first_date].head(1),
                full_data[full_data[date_col] == last_date].head(1)
            ]).drop_duplicates()
    
        # Exclude bounds rows from the original DataFrame for sampling
        df_without_bounds = full_data[~full_data.index.isin(bounds_rows.index)]
        
        # Calculate how many rows to sample
        sample_size = count - len(bounds_rows)  # Number of random rows needed
    
        
        if sample_size > 0 and sample_size < len(df_without_bounds):
            df_random = df_without_bounds.sample(n=sample_size, random_state=1)
    
        elif sample_size >= len(df_without_bounds):
            df_random = df_without_bounds.sample(n=len(df_without_bounds), random_state=1)
    
        else:
            df_random = pd.DataFrame()  # No additional rows needed
        
        # Combine bounds with random sample
        df_combined = pd.concat([bounds_rows, df_random]).drop_duplicates().head(count).reset_index(drop=True)
        
        return df_combined

    def clean_json(self, input_string):
        start = input_string.find('{')  # Find the index of the first '{'
        end = input_string.rfind('}')    # Find the index of the last '}'
        json_output = input_string[start:end + 1].strip()  # Extract and strip whitespace
    
        return json_output

    def create_visualization(self, choice, data, row_count, additional_user_prompt):
    
        choice_template = self.visualizations_templates[choice]
        system_prompt = f"""
            You are a data assistant capable of interpreting user queries and returning data visualized using the Vega graph specification. When given a query about data, respond by first understanding the user's intent, then generate the appropriate data visualization in Vega-Lite format.
            
            
            Instructions:
            1. Analyze the provided data sample and ensure the JSON chart accurately represents the requested visual format (e.g., bar chart, scatter plot).
            2. For numeric fields, ensure they are represented with appropriate quantitative encoding.
            3. For categorical fields, ensure they are represented as nominal encoding.
            4. Ensure axes, labels, tooltips, and legends are clear and meaningful.
            5. If the x-axis contains long text, adjust the `labelAngle` and `labelPadding` for readability.
            6. Add interactivity where applicable, such as hover effects to display tooltips.
            7. Use a consistent and intuitive color scheme or style for the chart.
            8. Ensure that your response is valid JSON, formatted for use with `json.loads()`, and does not include any additional commentary.
            Ensure that:
            Your responses focus on returning a complete and valid JSON object in Vega-Lite format, ready to be rendered.
            You may assume that users are familiar with the general structure of the data but need help generating accurate and useful visualizations. Keep responses concise and provide a clear explanation of how the data is represented in the graph.
            you will be generating a {choice} graph.
            Return a json response in the following format {choice_template}
    
            
            Rules: 
            1. Don't include any other string besides the json itself. 
            2. Use double quotes instead of single quotes in your json 
            3. Don't include the word 'json' before the response
            4. Don't wrap your response in triple quotes (''')
            5. Include all given data points in the values field. Do not include a comment for a placeholder for other values, include all values in your response
            6. Include a wide sample of the data
            7. Make sure that the points are visible. You may need to make the points black if it is a scatter plot to make the points appear 
            8. Make sure to "zoom in" on the area of interest if you have to. If you choose to, you can do so by, adding a scale property with domain set to the desired range of the y-axis values in the y encoding.
            9. Return nothing else except for the json in json format. Your response will be needed to be loaded into a json.loads() function.
            10. If the range of the bounds is very high, consider using the 'quantitive' type for the axis instead of 'ordinal'
            11. Don't include any comments at all.
            12. Make sure I'm able to run a json.loads(<Your response>) command on your response
            13. If there are many points on the x axis, consider increasing the "labelAngle" to -45 and the "labelPadding" to 10
            14. Always include a width parameter and never set it to over 1000. You may also need to set the labelOverlap field to true in the x axis parameters
            15. Try to make your graph interactive by showing values when hovering over data.
            16. For charts like multi-series lines, make the lines highlight on hover.
            17. For the template given. Try to retain and apply all features in the encoding section. If highlighting and/or hovering is present, please retain that feature in your response.
        """
        
        user_prompt = f"""
        return a template for me of a vega json structure for this  sample data: {data} in the {choice} format. The sample of the data you have been provided is just
        a sample which will be injected with much more similar data. Please ensure that the template can scale. THere will be {row_count} total rows. 
        Consider the following additional request, given by the user: {additional_user_prompt}
        Do not return anything else except for the json. 
        Do not include any additional text or comments in your response. Ensure the JSON is valid and can be used directly with `json.loads(<Your response>)`.
    
        """
        i = 0
        while i < 4:
            try:             
                response = self.call_gpt(system_prompt, user_prompt)
                json_response = json.loads(response)  # Attempt to load the original response
                break  # Break the loop if successful
            except JSONDecodeError as e:
                # If a JSONDecodeError occurs, clean the response string
                cleaned_response_string = self.clean_json(response)
                
                try:
                    json_response = json.loads(cleaned_response_string)  # Attempt to load the cleaned response
                    print("Error Resolved")
                    break  # Break the loop if successful
                except JSONDecodeError as e_inner:
                    with open('errors/json_error.txt', 'w') as f:
                        f.write(response_string)  # Log the original response that caused the error
                    print(e_inner)
                    print("Retrying")
                    i += 1  # Increment the retry counter
        return json_response

    def get_vega_chart(self, pandas_dataset, additional_prompt):
        row_count = pandas_dataset.shape[0]
        sample_data = self.get_sampling(pandas_dataset, 20)
        
        choice_string = self.choose_visualization(sample_data, row_count, additional_prompt)
        print(f"Graph Choice: {choice_string}")
        print(f"Templates: \n {self.visualizations_templates[choice_string]}")
        json_response = self.create_visualization(choice_string, sample_data, row_count, additional_prompt)
        full_dict_response = self.inject_data(json_response, pandas_dataset)
        full_json_response = json.dumps(full_dict_response, indent = 4)
        
        return full_json_response
        