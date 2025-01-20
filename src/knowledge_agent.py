import os
import json
import time
import requests
from IPython.display import display, Markdown
import chromadb
from chromadb.config import Settings
from base_agent import SuperAgent
from datetime import datetime  # Import datetime for timestamp functionality
from logging_config import setup_logger

# Set up the logger for this module
logger = setup_logger(__name__)

logger.info("This is an info log from the current module.")


class KnowledgeAgent(SuperAgent):
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
            name="Knowledge Agent",
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            gpt_deployment=gpt_deployment,
        )

        self.embed_api_key = embed_api_key
        self.embed_api_base = embed_api_base
        self.embed_gpt_deployment = embed_gpt_deployment
        self.embed_api_version = embed_api_version
        self.chroma_client = chromadb.Client(Settings())

        collection_name = "main"
        # Check for stored chroma output
        store_path = f"../output/chroma_outputs/{collection_name}_collection.json"

        if os.path.isfile(store_path):
            # Extract ids and embeddings from the JSON
            with open(store_path, "r") as f:
                data = json.load(f)

            # ids = data['ids']
            embeddings = data["embeddings"]
            metadatas = data["metadatas"]
            documents = data["documents"]

            self.main_collection = self.get_or_create_collection(
                collection_name, documents, metadatas, embeddings
            )
            print(
                f"Data successfully added to the Chroma collection: {collection_name}"
            )

        else:
            # Start the timer
            start_time = time.time()

            # Get or create the 'main' collection
            self.main_collection = self.get_or_create_collection(
                collection_name, initial_data_texts, initial_metadata
            )

            # End the timer
            end_time = time.time()
            execution_time = end_time - start_time  # Calculate elapsed time

            # Retrieve collection data
            collection_data = self.main_collection.get(
                include=["documents", "metadatas", "embeddings"]
            )

            # Convert the NumPy array to a list
            collection_data["embeddings"] = collection_data["embeddings"].tolist()

            # Add the execution time and current timestamp to the JSON data
            collection_data["execution_time_seconds"] = execution_time

            # Get the current timestamp in ISO format
            current_timestamp = datetime.now().isoformat()
            collection_data["timestamp"] = current_timestamp

            # Serialize the dictionary to a JSON string
            json_data = json.dumps(collection_data, indent=4)

            # Save the JSON data to a file
            with open(store_path, "w") as file:
                file.write(json_data)

            print(
                f"Collection data saved to {store_path} with execution time: {execution_time:.4f} seconds at {current_timestamp}"
            )

        self.system_prompt = """
        You are expert knowledge agent that will be used with a few other agents to come up with answers to a user's question. These users work for NBCU and you are an expert in NBCU knowledge. You will be a asked a general question and you will need to answer it. The query may be sent to a vector database to get specific answers to terms used in NBCU. You may or may not want to use the results from this vector db to help you in answering your question.
        
        """

    def get_or_create_collection(
        self, collection_name, texts, metadata, embeddings=None
    ):
        """Retrieve or create the main collection."""
        collections = self.chroma_client.list_collections()

        # Search for the collection named 'main'
        main_collection = next(
            (c for c in collections if c.name == collection_name), None
        )

        if main_collection:
            print(f"Collection '{collection_name}' exists.")
            return main_collection
        else:
            # Generate embeddings and create a new collection if 'main' does not exist
            if not embeddings:
                embeddings = self.generate_embeddings(texts)

            print(f"EMBEDDINGS: {embeddings}")
            return self.create_initial_collection(
                collection_name, embeddings, texts, metadata
            )

    def generate_embeddings(self, texts, batch_size=100):
        """Generate embeddings for given texts in batches."""
        embeddings = []
        headers = {"Content-Type": "application/json", "api-key": self.embed_api_key}
        url = f"{self.embed_api_base}/openai/deployments/{self.embed_gpt_deployment}/embeddings?api-version={self.embed_api_version}"

        # Process texts in batches
        for i in range(0, len(texts), batch_size):
            batch = [str(text) for text in texts[i : i + batch_size] if text]

            # Skip empty batches
            if not batch:
                print(f"Skipping empty batch at index {i}")
                continue

            data = {"input": batch}
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                batch_embeddings = [
                    item["embedding"] for item in response.json().get("data", [])
                ]
                embeddings.extend(batch_embeddings)

            else:
                print(
                    f"Error generating embeddings for batch starting at index {i}: {response.status_code} - {response.text}"
                )

        return embeddings

    def create_initial_collection(self, collection_name, embeddings, texts, metadata):
        """Create a new collection and upload initial data with embeddings."""
        collection = self.chroma_client.create_collection(name=collection_name)

        for i, embedding in enumerate(embeddings):
            collection.add(
                ids=[f"vector_{i}"],  # Unique ID for each item
                documents=[texts[i]],  # Document to store
                embeddings=[embedding],  # Corresponding embedding
                metadatas=[metadata[i]],  # Metadata
            )
        return collection

    def query_knowledge_base(self, query, top_k):
        """
        Query the knowledge base and retrieve top_k results.
        Enhanced with pprint and Jupyter display for better readability.
        """

        # We could 
        try:
            # Generate embeddings
            query_embedding = self.generate_embeddings([query])[0]

            results = self.main_collection.query(
                query_embeddings=query_embedding, n_results=top_k
            )

            return results

        except Exception as e:
            error_message = f"Error during query execution: {e}"
            print(error_message)  # Print error to console
            display(Markdown(f"**Error:** {error_message}"))  # Jupyter rich display
            return None

    def ask_knowledge_agent(self, query, top_k=3):
        """
        Use the vector db results along with the LLM to respond to the user question.

        """

        # Lookup query in vector db
        vector_db_result = self.query_knowledge_base(query, top_k=3)

        user_prompt = f"""
        
        Here is the result from the vector DB. 
        {vector_db_result}. Remeber, we are simply selecting the 3 closest vectors to what was in the original user question. 
        This means that they may or may not be related, it's just what's closest.
        So, don't feel as if you need to use the vector result, it is simply there to see if there is anything related in the vector database.
        Use this in conjuction with the user query respond accurately.
        User query: {query}. 
        
        Rules:
        Please give a smooth response - you don't need to directly mention there was a vector database lookup
        
        """

        # Use LLM
        response = self.call_gpt(
            user_prompt=user_prompt, system_prompt=self.system_prompt
        )

        return response
