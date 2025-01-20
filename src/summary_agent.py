# module/summary_agent.py
import pprint
from base_agent import SuperAgent
from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)
logger.info("This is an info log from the current module.")


class SummaryAgent(SuperAgent):
    def __init__(self, api_key, api_base, api_version, gpt_deployment):
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.gpt_deployment = gpt_deployment
        self.name = "sql_agent"

        # Initialize the parent class
        super().__init__(
            "Summary Agent", api_key, api_base, api_version, gpt_deployment
        )

    def generate_summary(self, conversation):
        # Prepare the system and user prompts

        system_prompt = """           
            You are an analytics summarization agent in a chatbot system designed for business analysts at Peacock. 
            You will be given the conversation that has been produced by the agents. 
            Your role is to provide clear, concise summaries of the conversation that focus on insights and results relevant to a business audience. 
            Avoid mentioning analytical processes, data sources, or technical details (e.g., "the data shows" or "the SQL query indicates"). 
            Present findings directly, in a professional and actionable manner, ensuring they are logically accurate and answer the questions posed. 
            Before sharing the results, carefully validate that the summary aligns with the key points of the conversation and correctly addresses the original query.
            """

        user_prompt = f"""
            Below is the information shared by other agents in the conversation. Summarize the key insights in 3 sentences or fewer, 
            focusing only on the results and findings without mentioning how the analysis was conducted or referring to data sources or processes.

            Conversation: {conversation}
            """

        try:
            # Use the parent class method to call GPT
            query = self.call_gpt(user_prompt, system_prompt)
            if query:
                # Ensure query is not None or empty
                pprint.pprint(query)
                return query

            else:
                raise ValueError("Query generation returned an empty result.")

        except Exception as e:
            print(f"An error occurred while generating the query: {e}")
            return None


#        return query
