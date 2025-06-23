
from typing import List, Literal
from langchain.chat_models import init_chat_model 
from dotenv import load_dotenv 
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.output_parsers import PydanticOutputParser 

from models.plan_models import StudyPlan, StudySession


load_dotenv(override=True)


class PlannerAgent:
    def __init__(self, model_name: str = "openai:gpt-4.1"):
        """
        Initialize the Planner Agent with a language model.
        """
        self.llm_model = init_chat_model("openai:gpt-4.1")

    def generate_study_plan(
        self,
        topics: List[str],
        days: int,
        daily_minutes: int = 30,
        level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    ) -> List[StudySession]:
        """
        Returns a structured study plan, dividing topics across the given number of days.

        Args:
            topics (List[str]): List of topics to study
            days (int): Number of days for the study plan
            daily_minutes (int): Minutes to study per day
            level (str): Difficulty level (beginner, intermediate, advanced)

        Returns:
            List[StudySession]: A list of StudySession objects with day, topic, and duration
        """
        parser = PydanticOutputParser(pydantic_object=StudyPlan)
        format_instructions = parser.get_format_instructions()
        escaped_format_instructions = format_instructions.replace("{", "{{").replace("}", "}}")
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", 
             "You are an expert study planner who creates personalized learning schedules. "
             "Your plans should be well-structured, progressive, and appropriate for the learner's level."),
            ("human", 
             "Create a {days}-day study plan for the following topics: {topics}.\n\n"
             "Requirements:\n"
             "- Daily study time: {daily_minutes} minutes\n"
             "- Learner level: {level}\n"
             "- Distribute topics logically across the {days} days\n"
             "- For {level} learners, ensure proper pacing and difficulty progression\n"
             "- Break down complex topics into manageable daily sessions\n\n"
             f"Format your response according to this schema:\n{escaped_format_instructions}")
        ])
        
        chain = prompt_template | self.llm_model | parser
        response = chain.invoke({
            "topics": topics, 
            "days": days, 
            "daily_minutes": daily_minutes, 
            "level": level
        })
        return response.sessions

