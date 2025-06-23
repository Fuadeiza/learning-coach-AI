from typing import Literal
from langchain.chat_models import init_chat_model 
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate



load_dotenv(override=True)



class TutorAgent:
    def __init__(self, model_name: str = "openai:gpt-4.1"):
        """
        Initialize the Tutor Agent with a language model of choice.
        """
        self.llm_model = init_chat_model("openai:gpt-4.1")

    def explain_topic(
        self, 
        topic: str, 
        level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    ) -> str:
        """
        Generates an educational explanation of a given topic based on the learning level.

        Args:
            topic (str): The subject to explain (e.g., "Bayes Theorem").
            level (str): Learner's level: beginner, intermediate, or advanced.

        Returns:
            str: A clear explanation suitable for the user's level.
        """
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert tutor who explains concepts clearly and simply, adapting to the learner's level."),
            ("human", "Tell me about {topic} and explain it in a way that is easy to understand for a {level} learner."),
        ])
        chain = prompt_template | self.llm_model
        response = chain.invoke({"topic": topic, "level": level})
        return str(response.content)

