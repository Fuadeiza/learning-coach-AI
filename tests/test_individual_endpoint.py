#!/usr/bin/env python3
"""
Quick test script to debug individual endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(method, path, **kwargs):
    """Test a single endpoint with error handling"""
    url = f"{BASE_URL}{path}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, **kwargs)
        else:
            print(f"❌ Unsupported method: {method}")
            return
            
        print(f"\n🔍 {method.upper()} {path}")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ Success: {type(data)}")
                if isinstance(data, dict):
                    print(f"   Keys: {list(data.keys())}")
                    if 'sessions' in data:
                        print(f"   Sessions count: {len(data.get('sessions', []))}")
                    if 'total_count' in data:
                        print(f"   Total count: {data.get('total_count')}")
                return data
            except:
                print(f"   📄 Response (not JSON): {response.text[:200]}...")
        else:
            print(f"   ❌ Error: {response.text[:200]}...")
            
    except requests.exceptions.ConnectionError:
        print(f"   💥 Connection failed - is server running?")
    except Exception as e:
        print(f"   💥 Exception: {e}")

def main():
    print("🧪 Testing Individual Endpoints")
    print("=" * 50)
    
    # Test basic connectivity
    test_endpoint("GET", "/health")
    test_endpoint("GET", "/db-test")
    
    # Create a test user first
    print("\n👤 Creating test user...")
    user_data = test_endpoint("POST", "/users/", json={"email": "test@example.com", "user_name": "Test User"})
    
    if user_data and 'user_id' in user_data:
        user_id = user_data['user_id']
        print(f"✅ Created user: {user_id}")
        
        # Test getting sessions for this user
        print(f"\n📋 Testing sessions for user {user_id}...")
        test_endpoint("GET", f"/debug/sessions/{user_id}")
        test_endpoint("GET", f"/sessions/{user_id}")
        test_endpoint("GET", f"/sessions/{user_id}", params={"limit": 5})
        
        # Test progress
        print(f"\n📈 Testing progress for user {user_id}...")
        test_endpoint("GET", f"/progress/{user_id}")
        
        # Test with invalid UUID
        print(f"\n🚫 Testing with invalid UUID...")
        test_endpoint("GET", "/sessions/invalid-uuid")
        test_endpoint("GET", "/debug/sessions/invalid-uuid")
        
    else:
        print("❌ Failed to create user, skipping other tests")
    
    print("\n🏁 Test complete!")

if __name__ == "__main__":
    main()