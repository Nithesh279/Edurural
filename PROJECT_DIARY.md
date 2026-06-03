# Project Diary: AI-Driven Multilingual Education Platform

## Week 1: Ideation & Team Formation
- **Team Discussion:** Held the first team meeting to brainstorm project ideas. Discussed various domains including healthcare, finance, and education.
- **Problem Identification:** 
  - Rural students struggle with language barriers and lack of personalised learning support.
  - Existing e-learning apps provide generic content without analysing individual needs.
  - Unreliable internet connectivity in remote areas hampers access to continuous online education.
- **Concept Finalization:** Decided to build an "AI-Driven Multilingual Verification & Translation Platform" to automatically translate educational videos into regional languages.
- **Role Assignment:** Assigned roles (Backend Developer, Frontend Developer, AI/ML Specialist) among team members.

## Week 2: Requirement Analysis & Tech Stack Selection
- **Requirements Gathering:** Listed essential features: User Authentication, Video Upload, Speech-to-Text (STT), Machine Translation (MT), Text-to-Speech (TTS), and Video Reconstruction.
- **Tech Stack Decision:** 
  - **Backend:** Python (Flask) for its robust ecosystem in AI/ML libraries.
  - **Frontend:** HTML5, CSS3, JavaScript for a responsive and intuitive UI.
  - **Database:** SQLite for lightweight data management during development.
  - **AI Models:** Evaluated Whisper (OpenAI) vs Faster-Whisper for transcription; chose Faster-Whisper for performance.
- **Environment Setup:** Set up the Git repository and development environment (VS Code, Virtual Environments).

## Week 3: System Architecture & Database Design
- **Database Schema:** Designed the relational database schema including tables for `Users`, `contents` (videos), `Subjects`, and `Comments`.
- **API Design:** Outlined the RESTful API endpoints for file uploads, processing status, and retrieving video data.
- **Prototype Logic:** Drafted the core logic for the video processing pipeline: extracting audio -> transcribing -> translating -> synthesizing speech -> merging audio/video.

## Week 4: Core Backend Development
- **Authentication System:** Implemented secure User Registration and Login using SHA-256 password hashing.
- **Video Processing Pipeline:**
  - Integrated `ffmpeg` for audio extraction from video files.
  - Implemented `faster-whisper` for high-accuracy speech-to-text transcription.
- **Translation Module:** Integrated translation libraries (`googletrans`/`deep_translator`) to convert English transcripts into Indian regional languages (Hindi, Tamil, Telugu, etc.).

## Week 5: Frontend Integration & Audio Synthesis
- **TTS Integration:** Implemented `edge-tts` for high-quality, natural-sounding voice synthesis in multiple regional languages.
- **Video Reconstruction:** Used `moviepy` and `ffmpeg` to merge the translated audio back with the original video, ensuring synchronization.
- **UI Development:** Built the core pages:
  - **Home/Dashboard:** For uploading videos and viewing status.
  - **Player:** Custom video player interface (`play.html`) to watch processed videos.

## Week 6: UI Enhancements & Course Structure
- **Chatbot Interface:** Designed and integrated the frontend chat interface for the future AI Chatbot, allowing users to see how the interaction will flow.
- **Course Management:** Implemented the "Courses" page to organize videos by subject and allow students to enroll in specific topics.
- **Responsive Design:** Refined the application layout to ensure compatibility across different screen sizes, preparing for mobile access.

## Week 7: Gamification & Engagement
- **Streak System:** Implemented a daily login streak feature to motivate students to learn consistently.
- **Teacher Tests:** Added functionality for teachers to manually create and assign tests to students, supplementing the AI-generated quizzes.
- **Analytics Dashboard:** Created a basic analytics view (`analytics.html`) for teachers to track video views and student engagement metrics.

## Week 8: Refinement, Testing & Documentation (Current)
- **Subject Filtering:** Refined the Q&A section to ensure questions are filtered by subject, so teachers only see relevant queries.
- **UI Polish:** Improved the visual aesthetics, fixing background consistency (enhancing Dark Mode/White themes) to make the platform more student-friendly.
- **Bug Fixes:** Resolved issues related to translation API timeouts and audio synchronization.
- **Documentation:** Compiling the final project report, creating the project diary, and preparing the presentation abstract for the upcoming hackathon (Srishti 2026).
- **Final Review:** Conducting end-to-end testing of the user flow from registration to watching a translated video and taking a quiz.

## Upcoming Plans & Future Scope

### 1. Advanced AI Chatbot Integration (Next Phase)
- **Problem:** Currently, students have to search through video content manually to find answers.
- **Solution:** We are developing a **Context-Aware AI Chatbot** using RAG (Retrieval-Augmented Generation).
- **Implementation Plan:**
  - **Vector Database:** Index video transcripts into a vector database (like FAISS or ChromaDB).
  - **LLM Integration:** Use a Large Language Model (e.g., Llama 3 or Gemini API) to answer student queries based *only* on the video content.
  - **Interactive UI:** A chat interface next to the video player for instant doubt resolution.

### 2. Live Doubt Solving & Mentorship
- **Feature:** Bridging the gap between AI and human interaction.
- **Plan:** Allow students to request a "Live Session" with a teacher for complex topics that the AI cannot fully explain.

### 3. Mobile Application
- **Goal:** Increase accessibility for students in remote areas who primarily use smartphones.
- **Tech Stack:** React Native or Flutter for a cross-platform (Android/iOS) mobile app.

### 4. Offline Learning Mode
- **Feature:** Allow students to download translated videos and quizzes.
- **Benefit:** Crucial for rural areas with intermittent internet connectivity.

### 5. Community & Peer Learning
- **Feature:** Discussion forums and study groups based on subjects.
- **Goal:** Foster a community where students can help each other and share knowledge.

### 6. Expanded Language Support
- **Goal:** Scale the platform to support all 22 scheduled languages of India (currently supports ~10).
- **Method:** Fine-tuning the translation models for lower-resource languages like Dogri, Maithili, etc.
