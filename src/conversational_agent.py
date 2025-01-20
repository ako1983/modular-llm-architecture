
import sys
import os
from IPython.display import display, Markdown
from pathlib import Path

curr_dir = Path(os.getcwd())
root_dir = Path(curr_dir.parents[0])
sys.path.append(str(root_dir))

from sql_agent import SQLAgent
from knowledge_agent import KnowledgeAgent
from summary_agent import SummaryAgent
from sql_debugger import SQLDebugger
from vega_agent import VegaAgent
from base_agent import SuperAgent
from logging_config import setup_logger
from clarification_agent import ClarificationAgent


# Set up the logger for this module
logger = setup_logger(__name__)
logger.info("This is an info log from the current module.")

artifacts_dir = Path(curr_dir.parents[0] / "artifacts/")

### Acts as a manager agent by routing which agents need to be executed


class ConversationalAgent(SuperAgent):
    def __init__(
        self,
        embed_api_key,
        embed_api_base,
        embed_api_version,
        embed_gpt_deployment,
        initial_data_texts,
        initial_metadata,
        api_key,
        api_base,
        api_version,
        gpt_deployment,
    ):
        super().__init__(
            name="Conversational Agent",
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            gpt_deployment=gpt_deployment,
        )
        self.sql_debugger = SQLDebugger(api_key, api_base, api_version, gpt_deployment)
        self.sql_agent = SQLAgent(api_key, api_base, api_version, gpt_deployment)
        self.knowledge_agent = KnowledgeAgent(embed_api_key, embed_api_base, embed_api_version, embed_gpt_deployment, initial_data_texts, initial_metadata, api_key, api_base, api_version, gpt_deployment)
        self.summary_agent = SummaryAgent(api_key, api_base, api_version, gpt_deployment)
        self.vega_agent = VegaAgent(api_key, api_base, api_version, gpt_deployment)

    def execute_agent_calls(self, function_json, original_user_question):
            conversation = []
            result = ""
            json_result = {
                'Chart': None,
                'Query_Result':None,
                'SQL_Query': None,
                'Summary': None
            }
            print(f"User Question: {original_user_question}")
            conversation.append([f"User: {original_user_question}"])
            result += f"User Question: {original_user_question}"
    
            for agent_call in function_json:   
                agent = agent_call['Agent'] 
                if not agent:
                    print("Warning: Missing 'Agent' key in function_json.")
                    continue
    
                if agent == 'knowledge_agent': 
                    print("\n====================")
                    print("Knowledge Agent")
                    print("====================")
                    args = agent_call['args']
                    prompt = args.get('prompt') if args else None
    
                    if not args:
                        print("Warning: Missing 'args' for knowledge_agent call.")
                        continue
                    
                    try:
                        print(f"Knowledge Agent Prompt: {prompt}")
                        results = self.knowledge_agent.ask_knowledge_agent(prompt, top_k=3) 
                        print(f"Knowledge Agent Results: {results}")
                        conversation.append([f"Knowledge Agent: {results}"])
                        result += f"\nKnowledge Agent: {results}"
                    except Exception as e:
                        print(f"Error executing knowledge agent: {e}")          
    
                elif agent == 'sql_agent':  
                    print("\n====================")
                    print("SQL Agent")
                    print("====================")
                    args = agent_call['args']
                    prompt = args.get('prompt') if args else None
    
                    if not prompt:
                        print("Warning: Missing 'prompt' for sql_agent call.")
                        continue
    
                    try:
                        print(f"SQL Agent Prompt: {prompt}")
                        sql_query = self.sql_agent.generate_query(prompt)
                        print(f"Pre-Validated SQL Query: {sql_query}")
    
                        if sql_query is None:
                            print("Warning: The SQL query generation returned None.")
    
                        if not isinstance(sql_query, str):
                            print("Error: The generated SQL query is not a string.")

                        query_result = self.sql_agent.send_query(sql_query)
                        
                        
                        print(f"Pre-Validation Query Result: {query_result}")
                        sql_query, query_result, description = self.sql_debugger.validate_and_fix_sql(sql_query, original_user_question, query_result)

                    
                            
                        conversation.append([f"SQL Query Results: {query_result}"])
                        conversation.append([f"SQL Query: {sql_query}"])
                        result += f"\nSQL Query Results:\n{query_result}"
                        json_result['SQL_Query'] = sql_query
                        json_result['Query_Result'] = str(query_result)
                    except Exception as e:
                        print(f"Error executing sql_agent: {e}")
    
                elif agent == 'chart_agent':
                    print("\n====================")
                    print("Vega Agent")
                    print("====================")
                    try:
                        if "query_result" in locals():
                            chart = self.vega_agent.get_vega_chart(query_result, "no additional prompt")
                            print(f"Generated Chart: {str(chart)}")
                        else:
                            print("Error: chart agent tried running, however no SQL results have been produced.")
                            chart = None
                    except Exception as e:
                        print(f"Error executing chart_agent: {e}")
    
                    #conversation.append([f"Vega Agent: {chart}"])
                    result += f"\nVega Agent: {chart}"
                    json_result['Chart'] = chart
                elif agent == 'summary_agent':
                    print("\n====================")
                    print("Summary Agent")
                    print("====================")
                    try:
                        summary = self.summary_agent.generate_summary(conversation)
                        #print(f"Generated Summary: {summary}")
                        conversation.append([f"Summary Agent: {summary}"])
                        result += f"\nSummary Agent: {summary}"
                    except Exception as e:
                        print(f"Error executing summary_agent: {e}")

                    json_result['Summary'] = summary
                elif agent in ['analysis_agent', 'follow_up_agent']:
                    print(f"Agent {agent} is not implemented.")
    
                else:
                    print(f"Unknown agent: {agent}")



            return json_result


        
        
