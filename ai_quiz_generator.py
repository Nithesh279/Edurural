import re
import random

class AIQuizGenerator:
    def __init__(self):
        pass
    
    def generate_quiz_from_text(self, text, num_questions=5, difficulty="medium"):
        """Generate quiz questions from text content."""
        questions = []
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 20]
        
        for i, sentence in enumerate(sentences[:num_questions]):
            words = sentence.split()
            if len(words) < 4:
                continue
            
            # Create fill-in-blank style question
            blank_idx = random.randint(1, len(words) - 2)
            answer = words[blank_idx]
            words[blank_idx] = "______"
            
            questions.append({
                "id": i + 1,
                "question": " ".join(words),
                "answer": answer,
                "type": "fill_blank"
            })
        
        return questions
    
    def generate_quiz(self, content, num_questions=5):
        """Alias for generate_quiz_from_text."""
        return self.generate_quiz_from_text(content, num_questions)
