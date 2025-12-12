
from services.verifier import verifier

def test():
    print("🧠 Testing RAG Verifier (DistilBERT)...")
    
    # 1. Good Caption
    text_good = "A group of friends laughing at a dinner table with a birthday cake."
    score_good = verifier.verify(text_good)
    print(f"   Input: '{text_good}' -> Score: {score_good} (Expected > 0.8)")
    
    # 2. Hallucinated / Nonsense
    # DistilBERT MLM checks if words are predictable. 
    # Valid English but weird context might pass.
    # Gibberish might fail.
    # 'Low Confidence' in my implementation checks if the masked word is in top-k predictions.
    # If I give it a word it essentially cannot predict?
    # e.g. "A flying elephant under the ocean." (Grammatically correct, but semantic? MLM is syntactic/local).
    # Actually checking "Hallucination" with MLM is weak.
    # But checking "Gibberish" is good.
    # Let's try something weird.
    text_bad = "Xyzpdq lkjhgf poiuyt." # Should fail if tokenizer splits it weirdly?
    # Or just a random word sequence.
    text_bad_2 = "Table sky water computer banana."
    
    score_bad = verifier.verify(text_bad_2)
    print(f"   Input: '{text_bad_2}' -> Score: {score_bad}")

if __name__ == "__main__":
    test()
