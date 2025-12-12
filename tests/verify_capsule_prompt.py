import sys
import os
sys.path.append(os.getcwd())

from services.config import config
# Force Local or Gemini? Let's use whatever is configured, or force one for testing.
# The user's env seems to be Local now.

from services.ai_service import ai_service
import time

def verify_capsule_prompt():
    print("🚀 Starting Time Capsule Prompt Verification...")
    
    # 1. Define Test Context
    context = {
        "date": "2023-10-10",
        "location": "서울숲",
        "people": ["아빠", "딸"],
        "caption": "아빠와 딸이 벤치에 앉아서 웃고 있다. 낙엽이 떨어지고 있다."
    }
    author = "지안이 아빠"
    
    print(f"📥 Input Context:\n {context}")
    
    # 2. Run Generation
    print("\n⏳ Generating Question (may take a few seconds)...")
    try:
        start_time = time.time()
        question = ai_service.generate_time_capsule_question(author_name=author, context=context)
        duration = time.time() - start_time
        
        print(f"✅ Generated Question ({duration:.2f}s):")
        print(f"👉 \"{question}\"")
        
        if not question or "AI 연결 실패" in question:
            print("❌ Generation Failed (AI Error)")
            return

        # 3. Validation Logic
        failures = []
        
        # Rule 1: No Hallucinated Relatives
        forbidden_words = ["이모", "고모", "삼촌", "할머니", "할아버지", "조카", "친구"]
        for word in forbidden_words:
            if word in question:
                failures.append(f"Hallucination detected: '{word}' found.")
                
        # Rule 2: Presence of Context Keywords
        required_keywords = ["아빠", "딸", "서울숲", "가을", "낙엽", "웃", "행복"]
        # Match roughly (any of these)
        found_any = False
        for kw in required_keywords:
            if kw in question:
                found_any = True
                break
        
        if not found_any:
            failures.append("Context MISSING: None of the keywords (아빠, 딸, 서울숲...) detected.")
            
        # Rule 3: Question Format
        if not question.strip().endswith("?"):
            failures.append("Format Error: Does not end with '?'")

        if failures:
            print("\n❌ Verification FAILED:")
            for f in failures:
                print(f"   - {f}")
        else:
            print("\n✅ Verification PASSED: Logic holds strong.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_capsule_prompt()
