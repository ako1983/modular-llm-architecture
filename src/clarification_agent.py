# module/clarification_agent.py
import os
import sys

sys.path.append(os.path.abspath("../modules"))
from common_imports import *  # noqa: F403
from base_agent import SuperAgent

from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)


class ClarificationAgent(SuperAgent):
    def __init__(self, api_key, api_base, api_version, gpt_deployment):
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.gpt_deployment = gpt_deployment
        self.name = "clarification_agent"
        self.client = AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.api_base,
            api_key=self.api_key,
        )

        # Initialize the parent class
        super().__init__(
            "Clarification Agent", api_key, api_base, api_version, gpt_deployment
        )

    # def is_business_related(self, user_query):
    #     """
    #     Determines if the user's query is related to NBC/Peacock business.
    #     """
    #     system_prompt = """
    #     You are a Query Filter Agent for NBC/Peacock-related questions.
    #     Your TASK is to determine if the query is relevant to the NBC/Peacock business.

    #     - Relevant topics include:
    #     1. NBC/Peacock shows, genres, and viewing trends.
    #     2. Metrics such as views, ratings, and DMA-related insights.
    #     3. General business-related terms or concepts (e.g., churn, revenue metrics, engagement).
    #     4. Questions that can be answered by RAG or connected knowledge bases tied to NBC/Peacock.

    #     - Off-topic examples:
    #     1. "What is the weather today?"
    #     2. "Tell me about Netflix's top shows."
    #     3. General unrelated knowledge questions like "Who is the President of the U.S.?"

    #     - Rules:
    #     - If the query is clearly off-topic (e.g., weather, non-NBC services like Netflix), return:
    #         "I'm sorry, I can only answer questions related to NBC/Peacock shows, genres, and business metrics."
    #     - If there is any chance the query might be tangentially relevant to NBC/Peacock (e.g., churn, DMA insights),
    #         pass it on for further processing.
    #     """

    def detect_ambiguity(self, user_query):
        """
        Detects whether the user's query contains ambiguity.
        """
        system_prompt = """
        You are an expert in identifying ambiguous queries.
        Your TASK is to determine if the user's query requires clarification.
        
        - Look for vague terms or phrases such as:
          1. "Last week" (Ambiguity: fiscal week vs. calendar week).
          2. "Top shows/genres" (Ambiguity: top by views, ratings, or other metrics?).
          3. "Trend" (Ambiguity: specify the timeframe or measurement method).
          4. References to "DMA" or "region" (Ambiguity: which region?).
          5. "Broadcast survey period" (Ambiguity: fiscal month vs. calendar month?).
        
        - If these terms are detected, return "True" to indicate that clarification is needed.
        - Otherwise, return "False."
        """

        user_prompt = (
            f"User Query: {user_query}\n\nDoes this query require clarification?"
        )

        try:
            response = self.call_gpt(user_prompt, system_prompt)
            if "True" in response:
                logger.info("Ambiguity detected in the query.")
                return True
            elif "False" in response:
                logger.info("No ambiguity detected in the query.")
                return False
            else:
                raise ValueError("Unexpected response for ambiguity detection.")
        except Exception as e:
            logger.error(f"Error during ambiguity detection: {e}")
            return False  # Assume no ambiguity if an error occurs.

    def clarify_query(self, user_query):
        """
        Handles ambiguities in the user's query and generates a clarification response.
        """
        system_prompt = """
        You are a Clarification Agent specializing in understanding ambiguous user queries.
        Your TASK is to identify unclear aspects of the user's query and ask specific questions to clarify:
        
        - Example ambiguities and their corresponding clarification questions:
          1. Timeframes (e.g., "last week"): "Do you mean fiscal week or calendar week?"
          2. "Top shows/genres": "Should 'top' be defined by total views, ratings, or another metric?"
          3. "Trend analysis": "What timeframe should the trend cover? Weekly, monthly, or another period?"
          4. DMA or region: "Which specific DMA or region are you referring to?"
          5. "Broadcast survey period": "Is the 'broadcast survey period' a fiscal month or calendar month?"
          6. Device type: "Which device category should the query focus on (e.g., STB, MOBILE APP)?"
          7. Anomaly detection: "What criteria define an anomaly—statistical variance, threshold deviation, etc.?"
          8. Rate of change: "How should the rate of change be calculated—(end-start)/start or a different method?"
        
        - Rules:
          - Ask one clarification question at a time for each ambiguity.
          - Be concise and precise in your questions.
        """

        user_prompt = f"User Query: {user_query}\n\nProvide clarification questions."

        try:
            clarification = self.call_gpt(user_prompt, system_prompt)
            if clarification:
                logger.info("Clarification generated successfully.")
                return clarification
            else:
                raise ValueError("No clarification was generated.")

        except Exception as e:
            logger.error(f"Error during clarification generation: {e}")
            return "Unable to clarify the query. Please try again."
