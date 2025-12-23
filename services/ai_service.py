from services.config import config
from services.logger import get_logger

logger = get_logger("ai_service")

class AIService:
    def generate_time_capsule_question(self, author_name: str, context: dict = None) -> str:
        """
        Generates a deep, reflective question for the Time Capsule.
        """
        provider = config.get("ai_provider")
        logger.info(f"Generating Time Capsule Question via {provider} for {author_name}")

        # 1. Context Analysis
        if context:
            date_str = context.get('date', '알 수 없는 날짜')
            location = context.get('location', '어떤 장소')
            people_list = context.get('people', [])
            people_str = ", ".join(people_list) if people_list else "소중한 사람"
            caption = context.get('caption', '사진 설명 없음')
            
            user_prompt = (
                f"다음은 타임캡슐에 담길 사진의 정보입니다:\n"
                f"- 촬영 날짜: {date_str}\n"
                f"- 장소: {location}\n"
                f"- 함께 있는 사람: {people_str}\n"
                f"- 시각적 묘사: {caption}\n\n"
                f"작성자({author_name})가 10년 뒤 이 사진을 다시 봤을 때, 당시의 감정을 떠올릴 수 있는 질문을 하나만 작성해 주세요."
            )
        else:
            # Fallback: No Context (Generic Mode)
            user_prompt = f"작성자({author_name})가 10년 뒤의 자신이나 가족에게 남길 메시지를 쓸 수 있도록, 깊이 있는 질문을 하나만 던져주세요."

        # 2. System Prompt Engineering (Antigravity Protocol)
        system_prompt = (
            "당신은 사용자가 10년 뒤의 미래에 열어볼 '타임캡슐'에 넣을 메시지를 쓰도록 돕는 **회고록 가이드**입니다.\n"
            "목표: 사용자가 현재의 행복, 사랑, 다짐을 미래로 보낼 수 있도록 유도하는 질문을 1개 생성하세요.\n\n"
            "🚫 **Strict Constraints (절대 금지사항):**\n"
            "1. **없는 인물 창조 금지**: 입력된 '함께 있는 사람' 외의 인물(이모, 삼촌, 할머니 등)을 절대 언급하지 마세요. 모르면 '이 분', '함께 있는 사람'이라고 지칭하세요.\n"
            "2. **미래 시점 혼동 금지**: '10년 후에 나를 만나면' 같은 기괴한 표현 금지. '10년 뒤 이 글을 읽을 때~'가 맞습니다.\n"
            "3. **평가 금지**: '성품이 어떤가요?' 대신 '어떤 점이 좋았나요?'처럼 구체적인 경험/감정을 물어보세요.\n"
            "4. **언어**: 무조건 한국어(Korean). 정중하고 따뜻한 어조(해요체).\n"
        )

        try:
            if provider == "gemini":
                from services.gemini import gemini_service
                response = gemini_service.chat_query(system_prompt, user_prompt, temperature=0.8)
                return response.strip('" ')
            else:
                # Local Llama (Ollama)
                from services.ollama_manager import ollama_manager
                import ollama
                
                if not ollama_manager.ensure_running():
                    return "미래의 나에게 어떤 말을 남기고 싶으신가요? (AI 연결 실패)"

                model_name = ollama_manager.get_best_model()
                response = ollama.chat(
                    model=model_name, 
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    options={"temperature": 0.8}
                )
                return response['message']['content'].strip('" ')

        except Exception as e:
            logger.error(f"Failed to generate capsule question: {e}")
            return "1년 뒤의 나에게 어떤 이야기를 들려주고 싶으신가요?" 

    def generate_interview_question(self, context: dict) -> str:
        """
        Generates a context-aware interview question for a photo.
        Context keys: date, location, people (list), caption (optional)
        """
        provider = config.get("ai_provider")
        
        # Build Context String (Injection)
        # Build Context String (Injection)
        location = context.get('location', '알 수 없는 장소')
        date_str = context.get('date', '어느 날')
        # people = ", ".join(context.get('people', [])) or "혼자" # Disabled by User Request
        caption = context.get('caption', '사진 내용 없음')
        
        system_prompt = (
            "당신은 따뜻한 호기심을 가진 **가족 전기 작가(Family Biographer)**입니다. "
            "사용자가 이 사진에 담긴 비하인드 스토리를 기록하도록 유도해야 합니다. "
            "단순히 '이건 뭔가요?'라고 묻지 말고, 제공된 정보(날짜, 장소, 상황)를 활용해 구체적인 디테일을 콕 집어서 질문하세요.\n\n"
            "지침:\n"
            "1. 언어: **무조건 한국어(Korean)**. 말투는 다정하고 예의 바르게(해요체).\n"
            "2. 질문 방식: '그날 ~할 때 어떤 기분이 드셨나요?' 혹은 '~ 장소의 분위기는 어땠나요?' 처럼 구체적으로.\n"
            "3. **🚫 인물 이름 사용 금지**: 사진 속 인물의 구체적인 이름(예: Dad, 누구님 등)을 절대 언급하지 마세요. 대신 '함께한 분들', '가족분들', '아이' 등으로 지칭하세요.\n"
            "4. 입력 정보 활용: 제공된 날짜(계절), 장소, 사진 설명을 질문에 녹여내세요.\n"
            "5. 길이: 한 문장 또는 두 문장으로 짧게.\n"
        )
        
        user_prompt = (
            f"다음은 사진에 대한 정보입니다:\n"
            f"- Date: {date_str}\n"
            f"- Location: {location}\n"
            f"- Visual Description: {caption}\n\n"
            "이 정보를 바탕으로 사용자가 추억을 떠올릴 수 있는 감성적인 질문을 하나만 만들어주세요. (인물 이름 언급 금지)"
        )

        logger.info(f"Generating Interview Question via {provider} with Context: {date_str}, {location}")
        
        try:
            if provider == "gemini":
                from services.gemini import gemini_service
                response = gemini_service.chat_query(system_prompt, user_prompt, temperature=0.75)
                return response.strip('" ')
            else:
                # Local Llama
                from services.ollama_manager import ollama_manager
                import ollama
                
                if not ollama_manager.ensure_running():
                    return None 

                system_prompt = (
                    "당신은 따뜻한 한국인 AI 비서입니다. 주어진 사진 정보를 보고 자연스러운 한국어 질문을 하나만 하세요.\n"
                    "다른 언어 절대 금지. 오직 한국어만 사용.\n\n"
                    "예시:\n"
                    "정보: 날짜=2023-01-01, 설명=가족 식사\n"
                    "질문: 새해 첫날 가족들과 나누신 대화가 기억나시나요?\n\n"
                    "정보: 날짜=2019-08-15, 설명=해변의 아이들\n"
                    "질문: 아이들이 정말 신나 보이네요! 이날 물놀이는 즐거우셨나요?\n"
                )
                
                # Simple User Prompt
                user_prompt = (
                    f"정보: 날짜={date_str}, 장소={location}, 설명={caption}\n"
                    "질문:"
                )

                # Self-Correction Loop (Max 3 attempts)
                max_retries = 3
                for attempt in range(max_retries):
                    model_name = ollama_manager.get_best_model()
                    response = ollama.chat(
                        model=model_name, 
                        messages=[
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': user_prompt}
                        ],
                        options={
                            "temperature": 0.7, # Increased freedom as requested
                            "repeat_penalty": 1.1, # Slightly relaxed
                            "top_p": 0.9
                        }
                    )
                    
                    response_text = response['message']['content'].strip('" ')
                    
                    # Validation
                    if self._is_contaminated(response_text):
                        logger.warning(f"⚠️ Attempt {attempt+1} failed (Hallucination): {response_text}. Retrying...")
                        continue # Try again
                    
                    # Success
                    return response_text

                # If all retries fail, use fallback
                logger.error("❌ All AI attempts failed integrity check. Using fallback.")
                return self._get_fallback_question()
            
        except Exception as e:
            logger.error(f"Failed to generate interview question: {e}")
            return self._get_fallback_question()

    def _is_contaminated(self, text: str) -> bool:
        """
        Robustly checks if the text contains hallucinated scripts.
        Blocks: Japanese, Chinese, Cyrillic, Thai, Arabic, Devanagari, Greek, Hebrew.
        Allows: Korean, English (ASCII), Punctuation, Emojis.
        """
        import re
        
        # Deny-list of Unicode ranges often hallucinated by Llama-3B
        # \u3040-\u30FF: Japanese (Hiragana/Katakana)
        # \u4E00-\u9FFF: Chinese (CJK Unified Ideographs)
        # \u0400-\u04FF: Cyrillic (Russian)
        # \u0E00-\u0E7F: Thai
        # \u0600-\u06FF: Arabic
        # \u0900-\u097F: Devanagari (Hindi)
        # \u0370-\u03FF: Greek
        # \u0590-\u05FF: Hebrew
        unsafe_pattern = re.compile(r'[\u3040-\u30FF\u4E00-\u9FFF\u0400-\u04FF\u0E00-\u0E7F\u0600-\u06FF\u0900-\u097F\u0370-\u03FF\u0590-\u05FF]')
        
        # Specific token blacklists (hallucination artifacts)
        blacklist_tokens = ["-san", "-kun", "xiezhen", "shen", "chan", "desu"]
        text_lower = text.lower()
        for token in blacklist_tokens:
            if token in text_lower:
                return True
            
        return bool(unsafe_pattern.search(text))

    def _get_fallback_question(self) -> str:
        """ Returns a safe, pre-defined Korean question. """
        import random
        templates = [
            "이 사진을 다시 보니 어떤 기분이 드시나요?",
            "이때 가장 기억에 남는 에피소드가 있다면 알려주세요.",
            "사진 속 분위기가 참 좋네요! 어떤 상황이었나요?",
            "함께한 분들과 어떤 이야기를 나누셨는지 기억나시나요?",
            "이 순간으로 다시 돌아간다면 무엇을 하고 싶으신가요?"
        ]
        return random.choice(templates)

    def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """
        Generic method to generate text via the active AI provider.
        Supports seamless switching between Local (Ollama) and Gemini.
        """
        provider = config.get("ai_provider")
        
        try:
            if provider == "gemini":
                from services.gemini import gemini_service
                return gemini_service.chat_query(system_prompt, user_prompt, temperature)
            else:
                # Local (Ollama)
                from services.ollama_manager import ollama_manager
                import ollama
                
                if not ollama_manager.ensure_running():
                    return "죄송합니다. 로컬 AI 서버(Ollama)가 응답하지 않습니다."

                model_name = ollama_manager.get_best_model()
                # logger.info(f"Generating response via Local AI: {model_name}")
                
                response = ollama.chat(
                    model=model_name, 
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    options={
                        "temperature": temperature,
                        "num_ctx": 4096,
                        "keep_alive": "5m" 
                    }
                )
                return response['message']['content']
                
        except Exception as e:
            logger.error(f"AI Generation Error ({provider}): {e}")
            return f"오류가 발생했습니다: {str(e)}"

# Singleton
ai_service = AIService()
