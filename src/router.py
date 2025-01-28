# module/router.py
from common_imports import *
from conversational_agent import ConversationalAgent

from clarification_agent import ClarificationAgent
from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)

logger.info("This is an info log from the current module.")


class Router:
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
        self.gpt_deployment = gpt_deployment
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.client = AzureOpenAI(
            api_version=api_version, azure_endpoint=api_base, api_key=api_key
        )
        self.conversational_agent = ConversationalAgent(
            embed_api_key,
            embed_api_base,
            embed_api_version,
            embed_gpt_deployment,
            initial_data_texts,
            initial_metadata,
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            gpt_deployment=gpt_deployment,
        )
        self.clarification_agent = ClarificationAgent(
            api_key, api_base, api_version, gpt_deployment
        )
        logger.info("Initializing Router instance")

        # Tweak the summary agent to always run. This is ok if only the knowledge agent runs.
        self.system_message = """
            You Role  is:  Act as a Busines Intelligence Manager with more than 15 years of experience. 
            Your Task is: to  carefully and deeply Understand the user's question as best as you can, and create a plan that engages the other agents to work as a group to serve the user.
            
            The agents available to you are: 

            1. SQL Agent (sql_agent) - write SQL queries and retrieve data from a database
            2. Chart Agent (chart_agent) - to take structured data, decide on the best chart, and assemble chart code that renders for the user
            3. Knowledge Agent (knowledge_agent) - performs a content search and assembles a good answer for the user
            4. Analysis Agent (analysis_agent) - summarizes a lot of different pieces of information into a narrative summary for the user, as well as makes recommendations
            5. Followup Agent (follow_up_agent) - Recommends follow-up questions that could be potentially looped back through to you, to repeat the decision making process.
            6. Summary Agent (summary_agent) - This agent should be called at the end of the conversation if more than one agent was used to summarize the entire conversation.
            ****
            After formatting the plan, you will execute the function call given to you with properly formatted parameters.
            You have been given a function which calls agent, you simply need to execute this function with a comma seperated list of all agents you need to call

            Rules:
            1. When calling the knowledge_agent, if possible, only simply put the name you want looked up as the parameter.
            2. If the SQL agent is called, DO NOT Print the SQL Query, and remember the chart agent should always be called to visualize the data.
            Examples:
                User: 'What is the definition of churn?' -> Execute `execute_agent_calls` with parameters 'agent_calls' of:
                '
                    [
                        {
                            "Agent": "knowledge_agent",
                            "args": {
                                "prompt": "churn"
                            }
                        },
                        {
                            "Agent": "summary_agent",
                            "args": {
                                "prompt": "Provide a final summary of the conversation."
                            }
                        }
                    ],
                '.

    """

        self.functions = [
            {
                "name": "execute_agent_calls",
                "description": "Executes multiple agent calls based on a provided string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_calls": {
                            "type": "object",
                            "description": """
                                JSON object where the key is the agent you want to execute and the value is what you need that agent to do.
                                This list should be in order of which agent needs to be executed.
                            """,
                            "additionalProperties": {"type": "string"},
                        }
                    },
                    "required": ["agent_calls"],
                },
            }
        ]

    def get_user_message(self, question):
        return f"""
            Come up with a plan for the following question: {question}.
            Please execute the function with your given parameters.
           only if you were asked to: give an explanation of what you're about to do.
           otherwise return a minimum and clean response.
        """

    def clarify_question(self, question):
        """
        Clarifies the user's question if ambiguity is detected.
        Handles up to 3 clarification attempts and returns the clarified question.
        If clarification fails, continues with the original question.
        """
        clarified_question = question

        for attempt in range(3):  # Allow up to 3 clarification attempts
            logger.info(f"Clarification attempt {attempt + 1}.")

            # Detect ambiguity
            clarification_needed = self.clarification_agent.detect_ambiguity(
                clarified_question
            )

            if clarification_needed:
                logger.info("Ambiguity detected. Asking for clarification.")

                # 1) The LLM generates the clarifying question
                clarifying_question = self.clarification_agent.clarify_query(
                    clarified_question
                )

                if not clarifying_question:
                    logger.warning(
                        "No clarification question was generated. Proceeding with the best guess."
                    )
                    return clarified_question  # Proceed with the current question

                # 2) Prompt the user for their clarifying response
                print("System clarification question:\n", clarifying_question)
                user_clarification = input(
                    "\nPlease provide your clarification: "
                ).strip()

                if not user_clarification:
                    logger.warning(
                        "User did not provide clarification. Proceeding with the best guess."
                    )
                    return clarified_question  # Proceed

                # 3) Append the user's clarification to the question
                clarified_question = (
                    f"{clarified_question}\nUser clarified: {user_clarification}"
                )

            else:
                logger.info(
                    "No ambiguity detected. Proceeding with the clarified question."
                )
                break

        else:
            logger.warning(
                "Maximum clarification attempts reached. Proceeding with the best guess."
            )

        return clarified_question

    def route_question(self, question):
        """
        Routes the user's question by orchestrating agent calls.
        If ambiguity is detected, uses the Clarification Agent to resolve it.
        """
        logger.info(f"Received question: {question}")

        # Step 1: Check for ambiguity before clarification
        if self.clarification_agent.detect_ambiguity(question):
            logger.info("Ambiguity detected. Invoking clarify_question.")
            clarified_question = self.clarify_question(question)
            if clarified_question:
                # answer_question =   user.input(f"Clarified question: {clarified_question}")
                logger.info(f"Clarified question: {clarified_question}")
                question = clarified_question
            else:
                logger.warning(
                    "Failed to clarify the question. Aborting routing process."
                )
                return "The question could not be clarified. Please refine your query."
        else:
            logger.info("No ambiguity detected. Proceeding with original question.")
        # Step 2: Proceed with routing the question
        system_msg = self.system_message
        user_msg = self.get_user_message(question)
        functions = self.functions

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.gpt_deployment,
                messages=messages,
                temperature=0,
                functions=functions,
                seed=42,  # Set a seed for reproducibility
            )

            # Parse response
            if response.choices[0].message.content:
                response.choices[0].message.content

            if response.choices[0].message.function_call:
                function = response.choices[0].message.function_call
                if function.name == "execute_agent_calls":
                    logger.info(f"Routing question to execute_agent_calls")
                    args = json.loads(function.arguments)
                    agent_calls = args["agent_calls"]
                    return self.conversational_agent.execute_agent_calls(
                        agent_calls, question
                    )
                else:
                    print(
                        f"Error: AI returned a function other than execute_agent_calls. \n{response.choices[0].message}"
                    )
                    return "AI returned a function other than execute_agent_calls."
            else:
                print(
                    f"Error: AI returned a function other than execute_agent_calls. \n{response.choices[0].message}"
                )

                return "AI did not return a function call."

        except HttpResponseError as e:
            return f"Error during classification: {e}"

        except Exception as e:
            return f"Error parsing: {e}"
