from typing import Literal, List
from langchain.chat_models import init_chat_model 
from dotenv import load_dotenv 
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.output_parsers import PydanticOutputParser 

from models.quiz_models import Question, Quiz


load_dotenv(override=True)



class QuizAgent:
    def __init__(self, model_name: str = "openai:gpt-4.1"):
        """
        Initialize the Tutor Agent with a language model of choice.
        """
        self.llm_model = init_chat_model("openai:gpt-4.1")


    def generate_quiz(
        self,
        topic: str,
        content: str,
        level: Literal["beginner", "intermediate", "advanced"] = "beginner",
        num_questions: int = 5,
        difficulty: Literal["easy", "intermediate", "hard"] = "easy"
    ) -> List[Question]:
        """
        Generates a list of quiz questions on a topic.

        Returns a list of dictionaries like:
        [
            {
                "question": "...",
                "options": ["A", "B", "C", "D"],
                "answer": "B"
            },
            ...
        ]
        """
        parser = PydanticOutputParser(pydantic_object=Quiz)
        format_instructions = parser.get_format_instructions()
        escaped_format_instructions = format_instructions.replace("{", "{{").replace("}", "}}")

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", 
             f"You are an expert tutor who generates quiz questions on a topic. "
             f"Generate {{num_questions}} quiz questions with the following characteristics:\n"
             f"Difficulty: {{difficulty}}\n"
             f"Level: {{level}}\n\n"
             f"Here is the content the user has already learned: {{content}}\n\n"
             f"Format the output as a JSON list according to the following schema:\n{escaped_format_instructions}"),
            ("human", "Generate quiz questions about {topic}."),
        ])

        chain = prompt_template | self.llm_model | parser
        quiz_output = chain.invoke({
            "topic": topic, 
            "content": content, 
            "num_questions": num_questions, 
            "difficulty": difficulty,
            "level": level
        })
        return quiz_output.questions
