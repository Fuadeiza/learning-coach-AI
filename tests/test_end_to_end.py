
import requests
import json
import uuid
from typing import Optional, Dict, Any

BASE_URL = "http://localhost:8000"

class AuthenticatedClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.session = requests.Session()
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def make_request(self, method: str, path: str, json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[Any, Any]:
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        
        try:
            if method.upper() == "POST":
                response = self.session.post(url, json=json_data, params=params, headers=headers)
            elif method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            print(f"{method.upper()} {path} → {response.status_code}")
            
            try:
                json_response = response.json()
                print("Response:", json.dumps(json_response, indent=2, default=str))
                return json_response
            except requests.exceptions.JSONDecodeError:
                print("Response content (not JSON):", response.text[:500])
                if response.status_code >= 400:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                return {"error": "Non-JSON response", "content": response.text}
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to {BASE_URL}. Is the server running?")
            raise
        except Exception as e:
            print(f"❌ Request failed: {e}")
            raise
    
    def post(self, path: str, json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[Any, Any]:
        return self.make_request("POST", path, json_data, params)
    
    def get(self, path: str, params: Optional[Dict] = None) -> Dict[Any, Any]:
        return self.make_request("GET", path, params=params)
    
    def register(self, email: str, password: str, user_name: Optional[str] = None) -> Dict[Any, Any]:
        print(f"\n👤 Registering user: {email}")
        return self.post("/auth/register", {
            "email": email,
            "password": password,
            "user_name": user_name
        })
    
    def login(self, email: str, password: str) -> Dict[Any, Any]:
        print(f"\n🔐 Logging in: {email}")
        response = self.post("/auth/login", {
            "email": email,
            "password": password
        })
        
        if "access_token" in response:
            self.access_token = response["access_token"]
            self.refresh_token = response["refresh_token"]
            print(f"✅ Logged in successfully")
            return response
        else:
            print(f"❌ Login failed: {response}")
            raise Exception("Login failed")
    
    def logout(self) -> Dict[Any, Any]:
        if not self.refresh_token:
            print("⚠️  No refresh token available for logout")
            return {"message": "Already logged out"}
        
        print("\n🚪 Logging out...")
        response = self.post("/auth/logout", {
            "refresh_token": self.refresh_token
        })
        
        self.access_token = None
        self.refresh_token = None
        print("✅ Logged out successfully")
        return response
    
    def get_profile(self) -> Dict[Any, Any]:
        return self.get("/auth/profile")
    
    def refresh_token_endpoint(self) -> Dict[Any, Any]:
        if not self.refresh_token:
            raise Exception("No refresh token available")
        
        response = self.post("/auth/refresh", {
            "refresh_token": self.refresh_token
        })
        
        if "access_token" in response:
            self.access_token = response["access_token"]
            print("✅ Token refreshed successfully")
        
        return response


def check_server_health():
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running and healthy")
            return True
    except:
        pass
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Server root response: {response.status_code}")
        return response.status_code < 500
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running or not accessible")
        return False
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        return False


def run_auth_test():    
    print("🔐 Testing Authentication Flow...")
    
    client = AuthenticatedClient()
    
    test_email = f"test_user_{uuid.uuid4().hex[:6]}@example.com"
    test_password = "TestPassword123!"
    test_name = "Test User"
    
    try:
        print("\n📝 Step 1: User Registration")
        registration = client.register(test_email, test_password, test_name)
        print(f"✅ Registration successful: {registration.get('user_id')}")
        
        print("\n🔐 Step 2: User Login")
        login_response = client.login(test_email, test_password)
        print(f"✅ Login successful, expires in: {login_response.get('expires_in')} seconds")
        
        print("\n👤 Step 3: Get Profile")
        profile = client.get_profile()
        print(f"✅ Profile retrieved: {profile.get('email')}")
        
        print("\n🔍 Step 4: Verify Token")
        verification = client.post("/auth/verify-token")
        print(f"✅ Token verified: {verification.get('valid')}")
        
        print("\n🔄 Step 5: Refresh Token")
        refresh_result = client.refresh_token_endpoint()
        print(f"✅ Token refreshed, new expires in: {refresh_result.get('expires_in')} seconds")
        
        print("\n🛡️  Step 6: Access Protected Endpoint")
        sessions = client.get("/my-sessions")
        print(f"✅ Protected endpoint accessed: {sessions.get('total_count', 0)} sessions")
        
        print("\n🚪 Step 7: Logout")
        logout_result = client.logout()
        print(f"✅ Logout: {logout_result.get('message')}")
        
        print("\n🚫 Step 8: Test Access After Logout")
        try:
            client.get("/my-sessions")
            print("❌ ERROR: Should not be able to access protected endpoint after logout")
        except Exception as e:
            print(f"✅ Correctly blocked access after logout: {e}")
        
        return test_email, test_password
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        raise


def run_full_e2e_test():
    print("🚀 Starting Full End-to-End Test with Authentication...")
    
    client = AuthenticatedClient()
    
    test_email, test_password = run_auth_test()
    
    client.login(test_email, test_password)
    
    try:
        print("\n🎯 Starting Learning Session...")
        session = client.post("/sessions/start/", {
            "user_id": "dummy",
            "topic": "Machine Learning",
            "level": "intermediate",
            "wants_quiz": True,
            "wants_plan": True
        })
        session_id = session.get("session_id")
        print(f"✅ Session started: {session_id}")
        
        print("\n📚 Generating Explanation...")
        explanation = client.post("/explain", {
            "topic": "Machine Learning",
            "level": "intermediate"
        })
        explanation_text = explanation.get("explanation", "")
        print(f"✅ Explanation generated ({len(explanation_text)} characters)")
        
        print("\n❓ Generating Quiz...")
        quiz = client.post("/quiz", {
            "topic": "Machine Learning",
            "content": explanation_text,
            "level": "intermediate",
            "num_questions": 3,
            "difficulty": "intermediate"
        })
        questions = quiz.get("questions", [])
        print(f"✅ Quiz generated with {len(questions)} questions")
        
        print("\n💾 Creating Questions and Recording Attempts...")
        for i, q in enumerate(questions):
            question_response = client.post("/questions/", {
                "topic": "Machine Learning",
                "level": "intermediate",
                "difficulty": "intermediate",
                "question_text": q.get("question", ""),
                "correct_answer": q.get("answer", ""),
                "options": q.get("options", [])
            })
            question_id = question_response.get("question_id")
            
            client.post("/quiz-attempts/", {
                "session_id": session_id,
                "question_id": question_id,
                "user_answer": q.get("answer", ""),
                "is_correct": True,
                "difficulty": "intermediate"
            })
            print(f"✅ Question {i+1} created and attempt recorded")
        
        print("\n📅 Generating Study Plan...")
        plan = client.post("/plan", {
            "topics": ["Machine Learning", "Deep Learning", "Neural Networks"],
            "days": 5,
            "daily_minutes": 45,
            "level": "intermediate"
        })
        sessions_count = len(plan.get("sessions", []))
        print(f"✅ Study plan generated with {sessions_count} sessions")
        
        print("\n📋 Logging Activities...")
        activities = [
            {"session_id": session_id, "type": "explanation", "content": {"explanation": explanation_text}},
            {"session_id": session_id, "type": "quiz", "content": {"questions": questions}},
            {"session_id": session_id, "type": "plan", "content": {"sessions": plan.get("sessions", [])}}
        ]
        
        for activity in activities:
            client.post("/activities/", activity)
            print(f"✅ Logged {activity['type']} activity")
        
        print("\n🏁 Ending Session...")
        client.post("/sessions/end/", {"session_id": session_id})
        print("✅ Session ended")
        
        print("\n📊 Checking Results...")
        my_sessions = client.get("/my-sessions")
        my_progress = client.get("/my-progress")
        my_activities = client.get("/my-activities")
        
        print(f"✅ Total sessions: {my_sessions.get('total_count', 0)}")
        print(f"✅ Progress entries: {len(my_progress.get('progress', []))}")
        print(f"✅ Total activities: {my_activities.get('total_count', 0)}")
        
        print("\n🎉 Full end-to-end test completed successfully!")
        
    except Exception as e:
        print(f"❌ E2E test failed: {e}")
        raise
    finally:    
        try:
            client.logout()
        except:
            pass


def run_test_suite():
    print("🧪 Learning Coach API Test Suite")
    print("=" * 50)
    
    if not check_server_health():
        print("Please start your FastAPI server first:")
        print("  uvicorn mcp_server.main:app --reload")
        return
    
    try:
        run_auth_test()
        
        print("\n" + "="*50)
        
        run_full_e2e_test()
        
        print("\n🏆 All tests passed!")
        
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_test_suite()