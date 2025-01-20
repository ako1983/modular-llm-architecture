# module/base_agent.py
from openai import AzureOpenAI
from IPython.display import display, Markdown
from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)

logger.info("This is an info log from the current module.")


class SuperAgent:
    def __init__(self, name, api_key, api_base, api_version, gpt_deployment):
        """
        Initialize the SuperAgent with configuration details.
        """
        # Store configuration details with optional default values
        self.api_key = api_key or "default_api_key"
        self.api_base = api_base or "default_api_base"
        self.api_version = api_version or "default_api_version"
        self.gpt_deployment = gpt_deployment or "default_deployment"
        self.name = name or "default_name"

        # Initialize the AzureOpenAI client if API details are provided
        if self.api_key and self.api_base:
            self.client = AzureOpenAI(
                api_version=self.api_version,
                azure_endpoint=self.api_base,
                api_key=self.api_key,
            )
        else:
            self.client = None
            print(
                "\nWarning: API client is not initialized. Check your configurations."
            )
            display(Markdown("**Warning:** API client is not initialized."))

    def call_gpt(self, user_prompt, system_prompt, functions=None):
        """
        Call the GPT model with the provided user and system prompts.
        """
        # notes_prompt = None
        # lookup if there are any notes in a rag database (would be a string)
        # Rag/vector similarity
        # implement a notes agent that returns only relevant notes
        # update notes_prompt

        if not self.client:
            error_message = (
                "API client is not initialized. Please provide valid API details."
            )
            print(error_message)
            display(Markdown(f"**Error:** {error_message}"))
            raise ValueError(error_message)

        messages = [
            # {"role": "system", "content": system_prompt + notes_prompt},
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            if functions:
                chat_completion = self.client.chat.completions.create(
                    messages=messages,
                    model=self.gpt_deployment,
                    temperature=0,
                    seed=42,  # Seed for reproducibility
                    functions=functions,
                )

                # Return whole chate_completion object, as several parts will need to parsed.
                return chat_completion

            else:
                chat_completion = self.client.chat.completions.create(
                    messages=messages,
                    model=self.gpt_deployment,
                    temperature=0,
                    seed=42,  # Seed for reproducibility
                )
                response = chat_completion.choices[0].message.content
                return response

        except Exception as e:
            error_message = f"Error while calling GPT: {e}"
            print(error_message)
            display(Markdown(f"**Error:** {error_message}"))
            raise
