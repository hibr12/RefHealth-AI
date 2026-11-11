# RefHealth AI – Complete AI Integration and Project Rebranding

I want to make two major improvements to my existing project:

1. Integrate Groq and Google Gemini into one intelligent AI chat assistant.
2. Rename the entire project from CoeCare-Health AI to RefHealth AI.

Before making any changes, thoroughly inspect the existing repository, understand its architecture, and identify the components that need modification.

Do not immediately start rewriting existing code. First understand how the current system works.

# PART 1: COMPLETE PROJECT REBRANDING

## 1. Official project identity

The project has officially been renamed.

- Old project name: CoeCare-Health AI
- New project name: RefHealth AI
- AI assistant name: RefHealth AI Assistant

Use exactly `RefHealth AI` throughout the project.

Do not introduce spelling variations such as RefHeath AI, Ref Health AI, or RefHealth.

## 2. Rename the entire project

Search the complete repository and update all references to the old project name.

Check the following:

- Frontend application titles and metadata.
- Navigation bars, dashboards, headers, footers, and login pages.
- Registration pages and user-facing messages.
- Backend application metadata and API descriptions.
- Swagger/OpenAPI documentation.
- AI service names, system prompts, and assistant identity.
- Database seed data and default application settings where appropriate.
- README files and technical documentation.
- Deployment documentation and environment-variable examples.
- Package metadata and configuration files where appropriate.
- Email templates, notifications, and error messages.
- Comments and internal documentation that refer to the old project identity.

Important requirements:

- Use `RefHealth AI` for all user-facing branding.
- Use `RefHealth AI Assistant` as the AI assistant identity.
- Preserve existing functionality.
- Do not unnecessarily rename database tables, API endpoints, migrations, or internal identifiers.
- Do not modify historical migration files unnecessarily.
- Do not break existing integrations or database relationships.

## 3. Rebranding verification

After completing the rename:

- Search the entire repository for `CoeCare`, `CoeCare-Health AI`, and other variations of the old name.
- Verify that all active interfaces display RefHealth AI.
- Verify that documentation and configuration examples use the new name.
- Report any remaining old-name references and explain why they were preserved.

# PART 2: INTEGRATE GROQ AND GOOGLE GEMINI

I want two different AI providers working together in one chat assistant.

They must have separate responsibilities.

## 4. Groq API – Language model and response generation

Use Groq as the primary Large Language Model (LLM).

Configuration:

- API base URL: `https://api.groq.com/openai/v1`
- Model: `openai/gpt-oss-20b`
- Environment variables:
  - `LLM_BASE_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`

Responsibilities:

- Understand user questions.
- Interpret retrieved knowledge.
- Generate intelligent natural-language responses.
- Maintain conversational context.
- Explain RefHealth AI functionality.
- Generate context-aware answers based on verified system information.

Groq should generate the final response returned to the user.

## 5. Google Gemini API – Embedding generation

Use Google Gemini for embedding generation and semantic retrieval.

Configuration:

- API base URL: `https://generativelanguage.googleapis.com/v1beta`
- Embedding model: `gemini-embedding-001`
- Environment variables:
  - `EMBEDDING_BASE_URL`
  - `EMBEDDING_API_KEY`
  - `EMBEDDING_MODEL`

Responsibilities:

- Convert user questions into vector embeddings.
- Generate embeddings for knowledge-base documents.
- Support semantic similarity searches.
- Help retrieve relevant information from the RefHealth AI knowledge base.

Important: Gemini is responsible for embeddings in this architecture, not generating the final chat response.

Ensure document embeddings and query embeddings use compatible dimensions and configurations.

# PART 3: EXPECTED AI CHAT ARCHITECTURE

Implement the following workflow:

1. The user sends a message through the RefHealth AI frontend.
2. The existing backend receives the request.
3. The backend forwards the message to the AI service.
4. The AI service sends the user's question to Gemini.
5. Gemini generates a vector embedding.
6. The AI service uses that embedding to search the existing knowledge base or vector database.
7. The AI service retrieves the most relevant documents and information.
8. The original question, retrieved context, and conversation history are passed to Groq.
9. Groq generates the final context-aware response.
10. The response is returned through the existing backend API.
11. The frontend displays the answer to the user.

Architecture:

User
  |
  v
RefHealth AI Frontend
  |
  v
Backend Chat API
  |
  v
AI Service / RAG Orchestrator
  |
  |---------------------------|
  |                           |
  v                           v
Google Gemini API          Knowledge Base
(Embeddings)               / Vector Search
  |                           |
  v                           v
Query Embedding           Retrieved Context
  |                           |
  |---------------------------|
              |
              v
          Groq API
          (LLM)
              |
              v
       Final AI Response
              |
              v
       RefHealth AI Frontend

# PART 4: REFHEALTH AI ASSISTANT CAPABILITIES

The AI assistant must understand the actual functionality of the RefHealth AI platform.

It should be capable of answering questions about:

1. Hospital recommendations.
2. Referral acknowledgement delay predictions.
3. Next-day hospital workload predictions.
4. Referral submission and tracking workflows.
5. Healthcare worker functionality.
6. Hospital functionality.
7. Available AI capabilities.
8. Platform operations and features.
9. System usage instructions.
10. Technical questions about the platform when supported by its documentation.

The assistant should use actual project documentation and verified system information.

Do not invent features, hospital information, prediction results, or system capabilities.

The assistant must clearly distinguish between:
- Information retrieved from the knowledge base.
- Actual database information.
- AI-generated explanations.
- Model predictions.

The language model must not fabricate clinical recommendations or replace professional healthcare judgment.

# PART 5: ENVIRONMENT CONFIGURATION

Use separate environment variables for the two providers.

The expected configuration is:

Groq:

LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=your_groq_api_key
LLM_MODEL=openai/gpt-oss-20b

Gemini:

EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta
EMBEDDING_API_KEY=your_gemini_api_key
EMBEDDING_MODEL=gemini-embedding-001

Requirements:

- Never hardcode API keys.
- Never expose API keys to the frontend.
- Load credentials from the backend or AI service environment.
- Validate required environment variables.
- Keep the two providers independently configurable.
- Never confuse the LLM API key with the embedding API key.
- Do not commit `.env` files or API secrets to Git.

Preserve existing environment variables that are still required by the project.

# PART 6: ERROR HANDLING AND RELIABILITY

Implement appropriate handling for:

- Invalid Groq API keys.
- Invalid Gemini API keys.
- API rate limits.
- Provider timeouts.
- Network failures.
- Embedding generation failures.
- Vector-search failures.
- Missing knowledge-base information.
- Invalid chat request payloads.
- Unexpected provider responses.

Do not silently generate fabricated answers when retrieval fails.

Provide meaningful error messages and appropriate server-side logging without exposing API keys or sensitive patient information.

If one provider fails, handle the failure safely and transparently rather than returning misleading responses.

# PART 7: EXISTING PROJECT FUNCTIONALITY

This is extremely important.

The existing RefHealth AI platform already has three major AI components:

1. Referral acknowledgement delay prediction.
2. Intelligent hospital recommendation.
3. Next-day hospital workload prediction.

These are separate machine-learning components.

Do not replace them with Groq or Gemini.

Do not train new prediction models unnecessarily.

Do not modify their existing prediction logic, model files, training pipelines, or API contracts unless a genuine integration requirement makes it necessary.

Groq and Gemini should primarily support the intelligent chat assistant.

Preserve the existing:

- Frontend functionality.
- Backend architecture.
- Authentication and authorization.
- Database structure and relationships.
- AI prediction services.
- Hospital management functionality.
- Referral workflows.
- Existing API endpoints.
- Existing security mechanisms.

# PART 8: INVESTIGATE THE EXISTING CHAT API

The existing frontend has previously returned this error:

HTTP 422 Unprocessable Entity

Request:

POST http://127.0.0.1:5173/api/assistant/chat

Investigate the cause before changing the implementation.

Inspect:

- Frontend request payload.
- Backend request validation.
- API route definitions.
- AI service request schema.
- Required fields.
- Response format.
- Authentication requirements.
- Backend-to-AI-service communication.

Determine whether the 422 error is caused by an invalid payload, schema mismatch, missing fields, or another issue.

Fix the underlying problem if it is related to the integration.

Ensure the frontend, backend, and AI service agree on the same request and response contracts.

# PART 9: TESTING AND VERIFICATION

After implementation, perform comprehensive tests.

### Provider tests

- Verify that Groq can generate a response.
- Verify that Gemini can generate embeddings.
- Verify that both API keys are loaded correctly.
- Verify that both providers work independently.

### Retrieval tests

- Verify that knowledge-base documents have valid embeddings.
- Verify that user questions retrieve relevant documents.
- Verify that retrieval results are passed correctly to Groq.

### Complete chat tests

- Send a question through the frontend.
- Verify the complete Gemini-to-retrieval-to-Groq workflow.
- Verify that the final answer appears correctly in the frontend.
- Verify conversation history handling.
- Test questions about the three existing AI components.

### Failure tests

- Test invalid API keys.
- Test unavailable providers.
- Test timeout scenarios.
- Test empty or invalid messages.
- Test questions with no relevant knowledge-base information.
- Test authentication and authorization.

### Build verification

Run the appropriate tests and build commands for each affected component.

Verify that:
- Frontend builds successfully.
- Backend builds successfully.
- AI service starts successfully.
- Existing prediction endpoints still work.
- Existing database integrations remain functional.
- The complete chat workflow works with real API requests.

Do not claim successful integration unless it has actually been tested.

# PART 10: IMPLEMENTATION APPROACH

Follow these steps in order:

1. Inspect the complete repository structure.
2. Understand the existing frontend, backend, and AI service architecture.
3. Identify the current chat implementation.
4. Identify existing Groq and Gemini integration code.
5. Inspect the current knowledge base, embeddings, and vector-search implementation.
6. Investigate the existing HTTP 422 error.
7. Prepare a short implementation plan.
8. Implement the necessary changes.
9. Complete the project-wide rebranding.
10. Test the modified components.
11. Verify that existing functionality has not been broken.

Avoid unnecessary dependencies, duplicate services, and unnecessary architectural changes.

Reuse existing implementations wherever possible.

Do not remove working functionality just to simplify implementation.

# FINAL DELIVERABLE

When finished, provide a detailed implementation report containing:

1. Summary of the original architecture.
2. Summary of the new RefHealth AI architecture.
3. Explanation of how Groq and Gemini work together.
4. List of modified files.
5. List of newly created files.
6. Environment variables required.
7. Explanation of the HTTP 422 issue and its resolution.
8. Testing results.
9. Confirmation that the three existing AI prediction components remain functional.
10. Remaining issues or manual configuration requirements.

IMPORTANT FINAL INSTRUCTIONS:

- Work with the existing repository, not a newly created replacement project.
- Preserve existing functionality and data.
- Do not unnecessarily rewrite the entire application.
- Do not expose API credentials.
- Do not fabricate test results.
- Use the exact official project name: RefHealth AI.
- Keep Groq responsible for LLM response generation.
- Keep Gemini responsible for embedding generation.
- Ensure the two providers work together through one RAG-based chat workflow.

The final objective is to have a fully integrated, properly tested **RefHealth AI platform with one intelligent chat assistant powered by Groq and Gemini**, while preserving all three existing healthcare AI prediction components.