from langchain.chat_models import init_chat_model 
from langchain_core.prompts import ChatPromptTemplate 
import json
import re

class ContentAgent:
    def __init__(self, model_name: str = "openai:gpt-4.1"):
        self.llm_model = init_chat_model(model_name)

    def suggest_materials(self, topic: str, level: str = "beginner") -> dict:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You're an AI that recommends high-quality learning resources. 
            Return your response as a JSON object with the following structure:
            {{
                "materials": [
                    {{
                        "title": "Resource Title",
                        "description": "Brief description of what this resource covers",
                        "url": "https://example.com",
                        "type": "video|article|documentation|course|book|tutorial",
                        "provider": "YouTube|Medium|Official Docs|Coursera|etc",
                        "difficulty": "beginner|intermediate|advanced",
                        "estimated_time": "X hours/minutes",
                        "rating": "4.5/5 (if known, otherwise omit)"
                    }}
                ],
                "prerequisites": ["prerequisite1", "prerequisite2"],
                "learning_path": ["step1", "step2", "step3"],
                "related_topics": ["topic1", "topic2"]
            }}"""),
            ("human", 
             "Suggest 4-5 high-quality learning resources for the topic '{topic}' for a {level} learner. "
             "Include a mix of different resource types (videos, articles, documentation, courses). "
             "Prioritize trusted sources like official documentation, well-known educational platforms, "
             "popular YouTube channels, and reputable blogs. "
             "Also provide prerequisites, a learning path, and related topics.")
        ])
        chain = prompt_template | self.llm_model
        response = chain.invoke({"topic": topic, "level": level})
        
        try:
            # Try to parse JSON response
            content = str(response.content).strip()
            
            # Clean up the response if it has markdown code blocks
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            result = json.loads(content)
            
            # Validate and ensure required fields
            if 'materials' not in result:
                result['materials'] = []
            
            # Ensure each material has required fields
            for material in result['materials']:
                if 'title' not in material:
                    material['title'] = 'Learning Resource'
                if 'description' not in material:
                    material['description'] = 'Educational content for ' + topic
                if 'type' not in material:
                    material['type'] = 'resource'
                if 'difficulty' not in material:
                    material['difficulty'] = level
                if 'estimated_time' not in material:
                    material['estimated_time'] = 'Varies'
            
            # Ensure other fields exist
            if 'prerequisites' not in result:
                result['prerequisites'] = []
            if 'learning_path' not in result:
                result['learning_path'] = []
            if 'related_topics' not in result:
                result['related_topics'] = []
                
            return result
            
        except (json.JSONDecodeError, Exception) as e:
            # Fallback to simple format if JSON parsing fails
            lines = [line.strip() for line in str(response.content).strip().splitlines() if line.strip()]
            
            # Try to extract URLs from the lines
            materials = []
            for i, line in enumerate(lines[:5]):  # Take first 5 lines
                url_match = re.search(r'https?://[^\s]+', line)
                url = url_match.group() if url_match else line
                
                materials.append({
                    "title": f"Learning Resource {i+1}",
                    "description": f"Educational content about {topic}",
                    "url": url,
                    "type": "resource",
                    "provider": "Various",
                    "difficulty": level,
                    "estimated_time": "Varies"
                })
            
            return {
                "materials": materials,
                "prerequisites": [f"Basic understanding of {topic} concepts"],
                "learning_path": ["Start with fundamentals", "Practice with examples", "Apply to projects"],
                "related_topics": []
            }
