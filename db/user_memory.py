from typing import Optional, Dict

# In-memory fallback store (use Redis later)
_user_context = {}

def save_user_context(user_id: str, data: Dict):
    _user_context[user_id] = data

def get_user_context(user_id: str) -> Optional[Dict]:
    return _user_context.get(user_id)
