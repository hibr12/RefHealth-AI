# PROJECT: RefHealth AI
## PART 1: COMPLETE BACKEND DEVELOPMENT

Act as a senior backend engineer and software architect. Your responsibility is to develop the complete, secure, scalable backend for RefHealth AI.

### 1. Project Overview

RefHealth AI is a multi-hospital, AI-powered healthcare intelligence and referral coordination platform.

The system connects multiple registered hospitals and health centers through a shared central AI intelligence system.

Every registered hospital manages its own information, operational activities, referrals, and dashboard.

The central AI uses authorized information from all registered hospitals to provide:

1. Referral Delay Prediction.
2. Intelligent Hospital Recommendation.
3. Hospital Workload Prediction.

The system must be designed around these three AI components rather than functioning as a general hospital management system.

### 2. Technology Stack

Use:

- Node.js
- TypeScript
- Fastify
- PostgreSQL
- Prisma ORM
- JWT authentication
- RESTful API architecture
- Zod or an equivalent validation library
- Swagger/OpenAPI documentation

Do not use MongoDB or Express.js.

### 3. User Roles and Permissions

Implement three primary roles.

**SYSTEM_ADMIN**

Responsible only for platform administration.

Permissions:
- Register and approve hospitals.
- Update hospital registration information.
- Suspend or activate hospital accounts.
- Manage platform-wide settings.
- Manage platform-level user access.
- Monitor system availability and AI service health.

The system administrator must not be responsible for individual hospital operations.

**HOSPITAL_ADMIN**

Responsible for managing an individual registered hospital.

Permissions:
- Manage hospital information.
- Manage hospital departments and specialties.
- Manage services and equipment information.
- Manage hospital operational information.
- Manage hospital users and their permissions.
- Update workload and capacity information.
- Manage incoming and outgoing referrals.
- View hospital-specific analytics.
- Access AI services.

**HEALTHCARE_WORKER**

Permissions:
- Create patient referrals.
- Submit referrals to other hospitals.
- View authorized patient referral information.
- Access AI hospital recommendations.
- View referral delay predictions.
- View relevant hospital workload predictions.
- Track referral status.
- Provide feedback on AI predictions.

Enforce strict role-based and hospital-based access control.

### 4. Core Backend Modules

Develop the following modules.

**A. Authentication and Authorization**
- Login and logout.
- Secure password hashing.
- JWT access and refresh tokens.
- Role-based authorization.
- Hospital-based data isolation.
- Password reset.
- Account activation and deactivation.

**B. Hospital Registration**
- Hospital registration.
- Hospital approval.
- Hospital profile management.
- Hospital location.
- Departments and specialties.
- Available services.
- Medical equipment.
- Hospital capacity.
- Operating hours.
- Registration status.

**C. Hospital Information Management**

Allow each hospital to maintain its own operational information.

Examples:
- Available beds.
- Available services.
- Service availability.
- Equipment availability.
- Staff availability.
- Current workload.
- Pending referrals.
- Operational announcements.

Store information with timestamps and source attribution.

**D. Patient and Referral Management**

Implement patient records only to the extent necessary for referral coordination.

Features:
- Patient registration.
- Patient identification.
- Referral creation.
- Referral submission.
- Referral acceptance.
- Referral rejection with reasons.
- Referral status tracking.
- Referral history.
- Referral completion.
- Verified referral outcomes.

Support hospital-to-hospital referrals.

A referral must have a clear lifecycle:

DRAFT → SUBMITTED → ACCEPTED/REJECTED → IN_PROGRESS → COMPLETED.

Also support cancellation where appropriate.

**E. AI Integration Gateway**

Create a dedicated backend service responsible for communicating with the Python FastAPI AI service.

It must support:

- Referral delay prediction.
- Intelligent hospital recommendation.
- Hospital workload prediction.
- AI conversational assistant.
- Hospital knowledge retrieval.

Use configurable AI service URLs and API keys through environment variables.

Do not expose AI service credentials to the frontend.

Implement timeouts, error handling, request validation, and appropriate logging.

**F. Shared Hospital Intelligence Data**

Create a centralized data structure that allows the AI to retrieve authorized information about all registered hospitals.

The system must distinguish:

- Public hospital information.
- Approved shared operational information.
- Hospital-private information.
- Patient-sensitive information.
- AI-generated predictions.

Do not expose private hospital or patient information to unauthorized users.

**G. Hospital Conversation and Knowledge Management**

Create APIs to store hospital conversations and structured knowledge extracted from them.

The system must:
1. Receive authorized hospital conversations.
2. Extract potentially useful operational information.
3. Create proposed knowledge updates.
4. Allow authorized hospital users to approve or reject updates.
5. Store approved information in the central knowledge system.

Never automatically treat unverified conversational statements as confirmed hospital facts.

**H. Feedback and AI Monitoring**

Implement:
- Prediction records.
- Prediction IDs.
- Model version tracking.
- Actual referral outcome recording.
- Feedback submission.
- Hospital-level AI performance statistics.
- Network-level AI performance statistics.
- Audit logs.

### 5. Database Design

Design a normalized PostgreSQL database using Prisma.

Include appropriate models for:

- Users.
- Hospitals.
- Hospital memberships and permissions.
- Departments.
- Specialties.
- Services.
- Equipment.
- Hospital capacity.
- Hospital operational updates.
- Patients.
- Referrals.
- Referral status history.
- AI predictions.
- AI feedback.
- AI model versions.
- Hospital conversations.
- Knowledge records.
- Knowledge approval requests.
- External information sources.
- Notifications.
- Audit logs.

Add proper relationships, indexes, unique constraints, timestamps, and appropriate deletion policies.

Use hospital_id to enforce multi-hospital data isolation.

Do not create unnecessary general hospital management features such as payroll, pharmacy management, or financial accounting.

### 6. Security Requirements

Implement:
- Secure authentication.
- Password hashing.
- Hospital-level authorization.
- Input validation.
- Rate limiting.
- CORS configuration.
- Secure error handling.
- Audit logging.
- Protection against unauthorized cross-hospital data access.
- Appropriate protection of sensitive patient information.

Never expose patient records through shared AI knowledge retrieval unless explicitly authorized and necessary for a legitimate referral workflow.

### 7. API Documentation and Testing

Provide complete Swagger documentation.

Create tests for:
- Authentication.
- Authorization.
- Hospital registration.
- Hospital information updates.
- Referral creation.
- Referral submission.
- Cross-hospital referral permissions.
- AI integration.
- Feedback submission.
- Hospital data isolation.

### 8. Development Instructions

Before coding:
1. Inspect the existing repository.
2. Identify existing files and technologies.
3. Prepare the backend architecture.
4. Explain the implementation plan.

Then implement the backend incrementally.

Do not generate placeholder endpoints that pretend to work.

Every endpoint must have functional business logic and database integration.

Create:
- Complete source code.
- Prisma schema.
- Database migrations.
- Environment example file.
- Seed scripts.
- API documentation.
- Testing instructions.
- Backend README.

Use Git Bash-compatible commands when providing terminal instructions.

### FINAL REQUIREMENT

The backend must operate independently and be ready for integration with the React frontend and Python AI service.

Do not begin frontend development in this phase.




## PART 2: COMPLETE FRONTEND DEVELOPMENT

Act as a senior frontend engineer and UI/UX designer.

Develop a complete, responsive, professional frontend for RefHealth AI.

The frontend must communicate with the independently developed backend through REST APIs.

### 1. Technology Stack

Use:
- React.js.
- Vite.
- TypeScript.
- Tailwind CSS.
- Axios.
- React Router.
- React Query (TanStack Query).
- Appropriate charting library.
- React Hook Form.
- Zod validation.

Follow a clean, reusable component architecture.

### 2. Design Direction

Create a professional healthcare technology platform.

Design characteristics:
- Modern and clean interface.
- Professional healthcare appearance.
- Consistent typography.
- Clear navigation.
- Responsive layouts.
- Accessible colors and contrast.
- Professional charts and analytics.
- Intuitive interactions.

Avoid overcrowded dashboards and unnecessary animations.

Use a consistent design system throughout the application.

### 3. Authentication Interfaces

Create:
- Login page.
- Hospital registration interface.
- Account activation interface.
- Password reset.
- Unauthorized access page.

After login, redirect users to the dashboard appropriate to their role.

### 4. System Administrator Dashboard

The System Administrator should have a minimal platform administration dashboard.

Features:
- Total registered hospitals.
- Pending hospital registrations.
- Approved hospitals.
- Suspended hospitals.
- Hospital registration requests.
- Approve and reject registration requests.
- Update hospital registration details.
- Activate and deactivate hospital accounts.
- Platform health status.
- AI service availability.

Do not give the System Administrator unnecessary access to individual hospital operations.

### 5. Hospital Administrator Dashboard

Every hospital should have its own workspace.

Features:

**Overview**
- Hospital information.
- Total referrals.
- Incoming referrals.
- Outgoing referrals.
- Pending referrals.
- Accepted referrals.
- Rejected referrals.
- Completed referrals.
- Current hospital workload.
- Predicted workload.

**Hospital Profile**
- Hospital name.
- Location.
- Contact information.
- Departments.
- Specialties.
- Available services.
- Equipment.
- Capacity.
- Operating hours.

**Operational Information**
- Available beds.
- Service availability.
- Staff availability.
- Equipment status.
- Workload updates.
- Operational announcements.

**Hospital Users**
- Add healthcare workers.
- Assign permissions.
- Activate or deactivate accounts.

### 6. Healthcare Worker Dashboard

Provide:
- Referral statistics.
- Create referral.
- Incoming referrals where authorized.
- Outgoing referrals.
- Referral tracking.
- AI recommendations.
- Delay risk information.
- Relevant hospital workload information.

### 7. Referral Management Interface

Build a complete referral workflow.

The referral form should collect the information required by the existing AI models and the referral process.

After submitting referral information, the interface should display:

1. Referral delay prediction.
2. Ranked hospital recommendations.
3. Predicted workload of suitable hospitals.
4. Explanations for recommendations.
5. Relevant warnings about missing or outdated data.

Allow the healthcare worker to review and select a hospital.

Never automatically finalize a clinical referral based only on AI predictions.

### 8. Central AI Assistant Interface

Create an accessible conversational AI assistant.

The assistant should be available to authorized hospital users.

Example questions:

- Which hospitals provide cardiology services?
- Which hospital is suitable for this referral?
- Which hospitals currently have high workloads?
- Why was this hospital recommended?
- What is the predicted delay risk?
- What are our hospital's current operational challenges?

Display:
- Conversation history.
- AI responses.
- Relevant hospital information.
- Sources and information timestamps where available.
- Loading indicators.
- Error handling.

Support a proposed hospital knowledge update workflow where users can review and approve information extracted from conversations.

Do not make the assistant appear to know information that the backend or AI service has not retrieved.

### 9. AI Intelligence Dashboard

Create a dedicated AI analytics section.

Include:

**Referral Delay Analytics**
- Delay predictions.
- High-risk referrals.
- Actual versus predicted outcomes.
- Delay trends.

**Hospital Recommendation Analytics**
- Recommended hospitals.
- Recommendation explanations.
- Hospital suitability comparisons.

**Workload Analytics**
- Current workload.
- Predicted workload.
- Historical trends.
- Hospital comparisons.

**AI Monitoring**
- Model versions.
- Prediction counts.
- Model evaluation metrics.
- Data freshness.
- AI service health.

Clearly distinguish predictions from actual observations.

### 10. Shared Hospital Intelligence

Create an interface that displays authorized information about registered hospitals.

Features:
- Search hospitals.
- Filter by location.
- Filter by specialties.
- Filter by services.
- View relevant hospital capacity.
- View verified operational information.
- View information freshness.

Only show information the current user is authorized to access.

### 11. External Information Sources

Create an interface where hospital administrators can register official external information sources.

Examples:
- Hospital website.
- Official Facebook page.
- Official Telegram channel.

Display connection and permission status.

Do not implement fake social media connections. Only show successfully authorized integrations.

### 12. Technical Requirements

- Connect all interfaces to actual backend APIs.
- Implement authentication persistence securely.
- Handle loading and error states.
- Implement route protection.
- Implement role-based navigation.
- Validate forms.
- Use reusable components.
- Avoid hardcoded dashboard statistics.
- Avoid mock data in production functionality.
- Support desktop, tablet, and mobile devices.

### 13. Development Instructions

Before development:
1. Inspect the existing frontend repository.
2. Review the backend API documentation.
3. Identify API endpoints and data structures.
4. Create the frontend architecture.

Implement the frontend incrementally.

Do not use fake data to simulate completed backend functionality.

If an API is not yet available, document the dependency rather than pretending the feature works.

Create complete source code, environment configuration, README, and testing instructions.

### FINAL REQUIREMENT

The frontend must be fully functional independently of the AI integration, using real backend APIs.

Do not rebuild the backend in this phase.



# PROJECT: RefHealth AI
## PART 3: CENTRAL AI INTELLIGENCE DEVELOPMENT

Act as a senior AI engineer, machine learning engineer, and AI systems architect.

Your task is to upgrade the existing Python AI service into a centralized, multi-hospital healthcare intelligence system.

### 1. MOST IMPORTANT INSTRUCTION

An existing AI service has already been developed.

It contains three main AI components:

1. Referral Delay Prediction.
2. Intelligent Hospital Recommendation.
3. Hospital Workload Prediction.

It also contains prediction APIs, model versioning, feedback collection, and monitoring foundations.

Before changing anything:

- Inspect the complete existing AI repository.
- Understand its folder structure.
- Inspect the existing models.
- Inspect training scripts.
- Inspect datasets.
- Inspect prediction endpoints.
- Inspect feedback and monitoring systems.
- Test the current implementation.

Preserve all working components.

Do not rebuild the AI service from scratch.

Do not delete existing models or datasets.

Document what works, what needs improvement, and what needs to be developed.

### 2. Technology Stack

Use:

- Python.
- FastAPI.
- Pandas.
- NumPy.
- Scikit-learn.
- Joblib.
- PostgreSQL.
- SQLAlchemy or an appropriate database integration.
- pgvector where appropriate.
- An LLM provider through a configurable API.
- RAG architecture.

Use environment variables for API keys and credentials.

Prefer affordable or free development options where practical.

### 3. Component One: Referral Delay Prediction

Preserve and improve the existing referral delay model.

Requirements:
- Receive referral information through an API.
- Validate input.
- Predict whether the referral may be delayed.
- Return delay probability.
- Return risk classification.
- Return model version.
- Return prediction ID.

Support hospital-specific and network-wide evaluation.

Do not claim that a model is accurate without sufficient representative validation data.

### 4. Component Two: Intelligent Hospital Recommendation

Upgrade the existing recommendation foundation.

The recommendation engine must evaluate all eligible registered hospitals.

Consider:

- Required specialty.
- Service availability.
- Distance.
- Available capacity.
- Current workload.
- Predicted workload.
- Referral delay probability.
- Historical referral acceptance.
- Historical processing performance.
- Information freshness.

Return a ranked list of suitable hospitals.

For each recommendation, provide:
- Hospital ID.
- Hospital name.
- Suitability score.
- Reasons for recommendation.
- Important limitations.
- Relevant information timestamps.

Do not recommend hospitals that lack required essential services.

Do not present a suitability score as a clinically validated probability.

### 5. Component Three: Hospital Workload Prediction

Preserve and improve the existing workload prediction foundation.

Use available hospital historical data to forecast future workload.

Requirements:
- Historical workload analysis.
- Referral volume analysis.
- Workload forecasting.
- Hospital-specific forecasting.
- Network-level workload analysis.
- Prediction confidence or uncertainty where supported.

Return:
- Hospital ID.
- Current workload.
- Predicted workload.
- Forecast period.
- Workload classification.
- Model version.
- Prediction timestamp.

Do not invent missing historical data.

### 6. Central Hospital Knowledge System

Develop a shared knowledge system.

It should contain authorized information from all registered hospitals.

Knowledge categories:

- Hospital profiles.
- Departments.
- Specialties.
- Services.
- Medical equipment.
- Hospital capacity.
- Workload information.
- Referral history.
- Operational announcements.
- Verified hospital performance.

Every knowledge record must include:

- Hospital ID.
- Information category.
- Information content.
- Source.
- Verification status.
- Creation timestamp.
- Last updated timestamp.
- Expiration or review date where appropriate.

Support structured information retrieval and semantic search.

Use PostgreSQL for structured information and pgvector for semantic retrieval where appropriate.

Do not duplicate information unnecessarily.

### 7. AI Conversational Assistant

Develop an LLM-powered conversational assistant.

The assistant should understand healthcare workers' natural-language questions.

Examples:

- Which hospitals provide cardiac services?
- Which hospitals are currently suitable for a neurology referral?
- Why is a particular hospital recommended?
- Which hospitals are experiencing high workloads?
- What services are available at a particular hospital?

Use RAG to retrieve relevant, authorized, up-to-date information.

The assistant must:

1. Understand the question.
2. Identify the relevant hospital context.
3. Retrieve authorized information.
4. Call the appropriate prediction or recommendation component when needed.
5. Generate an understandable response.
6. Identify its information sources and timestamps.
7. Communicate uncertainty when information is missing or outdated.

Never invent hospital information.

Never expose private patient records or unauthorized hospital information.

The assistant must not replace clinical judgment.

### 8. Hospital Conversation Knowledge Extraction

Develop a controlled knowledge extraction mechanism.

When an authorized hospital user communicates information to the assistant:

- Identify potentially useful operational facts.
- Extract structured information.
- Identify the hospital associated with the information.
- Create a proposed knowledge update.
- Request confirmation from an authorized hospital user.
- Store approved information in the shared knowledge system.

Keep conversations private unless information is explicitly approved for sharing.

### 9. External Information Integration

Design an extensible external information integration layer.

Potential sources:

- Official hospital websites.
- Authorized Facebook integrations.
- Authorized Telegram integrations.
- Other supported official sources.

Only collect information through authorized APIs, permitted feeds, or explicitly permitted public access.

Support:
- Source registration.
- Source authentication.
- Data collection.
- Information extraction.
- Source verification.
- Approval workflow.
- Update timestamps.

Do not assume that providing a social media account URL grants access to its private data.

Treat external information as supplementary until verified by the hospital.

### 10. Multi-Hospital Intelligence

The central AI must support all registered hospitals.

Every hospital should have its own knowledge profile.

The system should maintain:

- Individual hospital knowledge.
- Shared authorized hospital information.
- Network-wide operational insights.
- Hospital-specific model evaluation.
- Network-wide model evaluation.

Implement strict permission-aware retrieval.

A hospital should benefit from shared intelligence without accessing another hospital's private conversations or patient records.

### 11. Feedback and Continuous Improvement

Extend the existing feedback system.

Collect:
- Prediction ID.
- Hospital ID.
- Model version.
- Actual referral outcome.
- Actual workload outcome.
- Recommendation outcome.
- Feedback timestamp.

Support:
- Model performance monitoring.
- Data drift monitoring.
- Hospital-specific evaluation.
- Network-level evaluation.
- Candidate model training.
- Model comparison.
- Human approval.
- Model version activation and rollback.

New hospital information may update the knowledge base immediately after appropriate verification.

Predictive models must only be updated through controlled training and evaluation.

### 12. AI API Architecture

Provide clean FastAPI endpoints.

Examples:

POST /predict/referral-delay

POST /recommend/hospitals

POST /predict/hospital-workload

POST /assistant/chat

POST /knowledge/ingest

GET /knowledge/hospitals/{hospital_id}

POST /knowledge/approve

POST /feedback

GET /monitoring/models

GET /monitoring/health

Adapt endpoint names to the existing implementation where possible.

Do not break existing API contracts unnecessarily.

### 13. Testing

Test:
- All three AI components.
- Hospital recommendation ranking.
- Hospital knowledge retrieval.
- Conversational assistant.
- Permission-aware retrieval.
- Knowledge approval.
- Feedback collection.
- Model versioning.
- Monitoring.
- API authentication.
- Failure handling.

Use realistic test data without presenting synthetic results as real hospital performance.

### 14. Documentation

Provide:
- AI architecture.
- Model documentation.
- Dataset documentation.
- API documentation.
- Training instructions.
- Prediction instructions.
- Environment configuration.
- Integration instructions.
- Testing instructions.

### FINAL REQUIREMENT

The upgraded AI service must operate independently and be ready for integration with the Node.js backend.

Preserve the existing three AI components and extend them into a centralized hospital intelligence system.

Do not start frontend development.


# PROJECT: RefHealth AI
## PART 4: COMPLETE SYSTEM INTEGRATION, TESTING AND DEPLOYMENT

Act as a senior full-stack engineer, AI integration engineer, software architect, and QA engineer.

Your responsibility is to integrate the three independently developed components:

1. Node.js backend.
2. React frontend.
3. Python FastAPI AI service.

The goal is to deliver a complete, functional, secure, multi-hospital AI-powered healthcare intelligence platform.

### 1. Inspect All Three Projects

Before integration:

- Inspect the backend.
- Inspect the frontend.
- Inspect the AI service.
- Read their documentation.
- Inspect environment variables.
- Inspect API contracts.
- Inspect database schemas.
- Identify incompatible data structures.
- Identify missing endpoints.
- Identify integration dependencies.

Do not assume that independently developed components already work together.

Create an integration plan.

### 2. Establish Communication

Connect the components using the following architecture:

React Frontend → Node.js Backend → Python FastAPI AI Service.

The backend communicates with PostgreSQL.

The AI service accesses authorized shared hospital knowledge and the necessary operational data through clearly defined interfaces.

The frontend must never directly access the AI service's secret credentials.

Use:
- HTTP REST APIs.
- JSON communication.
- JWT authentication.
- Secure service-to-service authentication.
- Environment variables.
- Proper request validation.

### 3. Complete Hospital Registration Workflow

Verify this complete workflow:

1. System administrator registers or approves a hospital.
2. Hospital receives its account access.
3. Hospital administrator logs in.
4. Hospital administrator completes hospital information.
5. Hospital information is stored in PostgreSQL.
6. Authorized information becomes available to the central AI knowledge system.
7. The hospital can use the three AI components.

### 4. Complete Referral Workflow

Test the following scenario:

Hospital A needs to refer a patient.

1. Healthcare worker logs in.
2. Creates a referral.
3. Backend validates the referral.
4. AI predicts referral delay.
5. AI identifies suitable hospitals.
6. AI evaluates predicted hospital workloads.
7. Backend combines the results.
8. Frontend displays recommendations.
9. Healthcare worker reviews the results.
10. Healthcare worker selects a suitable hospital.
11. Referral is submitted.
12. Hospital B receives the referral.
13. Hospital B accepts or rejects it.
14. Referral status is updated.
15. Actual referral outcome is recorded.
16. Feedback becomes available for AI evaluation.

Verify every step using actual API requests and database records.

### 5. Verify Central AI Intelligence

Register multiple test hospitals.

Give each hospital different:
- Specialties.
- Services.
- Equipment.
- Capacity.
- Workload.
- Referral histories.

Verify that:

- The AI can retrieve authorized information from all registered hospitals.
- Recommendations consider all eligible hospitals.
- Hospital information updates are reflected in subsequent retrievals.
- Private conversations remain private.
- Patient records are not exposed across hospitals.
- The AI explains its recommendations.
- Outdated information is identified.
- Missing information is handled safely.

### 6. Integrate the Conversational Assistant

Connect the frontend AI assistant to the backend and AI service.

Verify that users can:

- Ask questions about their own hospital.
- Ask questions about other hospitals using authorized shared information.
- Request hospital recommendations.
- Ask why a hospital was recommended.
- Ask about relevant workload information.
- Receive explanations based on retrieved information.

Ensure the assistant respects hospital permissions.

### 7. Test Every User Role

Test:

SYSTEM_ADMIN:
- Hospital registration.
- Hospital approval.
- Hospital account management.
- Platform configuration.
- AI service health monitoring.

HOSPITAL_ADMIN:
- Hospital profile management.
- Operational information updates.
- Hospital user management.
- Referral management.
- AI access.
- Hospital analytics.

HEALTHCARE_WORKER:
- Patient referral creation.
- AI predictions.
- Hospital recommendations.
- Referral submission.
- Referral tracking.
- Feedback submission.

Verify that unauthorized operations are rejected by the backend, not merely hidden in the frontend.

### 8. Complete Error Handling

Test:

- Backend unavailable.
- AI service unavailable.
- Database connection failure.
- Invalid authentication.
- Expired tokens.
- Unauthorized hospital access.
- Invalid referral data.
- Missing hospital information.
- AI timeout.
- Failed predictions.
- Invalid model responses.

The frontend must display meaningful error messages.

Do not display fabricated AI results when the AI service fails.

### 9. Security and Privacy Testing

Perform:

- Authentication testing.
- Authorization testing.
- Cross-hospital isolation testing.
- Patient information access testing.
- API security testing.
- Input validation testing.
- Audit log verification.
- Secret management verification.

Ensure that hospital users cannot access information beyond their permissions.

### 10. Complete System Testing

Run:

- Backend unit tests.
- Backend integration tests.
- Frontend build.
- Frontend functionality tests.
- AI component tests.
- AI API integration tests.
- End-to-end referral workflow tests.

Fix all critical and high-priority errors.

Do not simply report that tests passed without actually executing them.

### 11. Performance and Reliability

Implement appropriate:
- API timeouts.
- Database connection management.
- Request logging.
- Error monitoring.
- AI response handling.
- Caching where safe.
- Background jobs for non-immediate knowledge processing.
- Pagination for large datasets.

Avoid caching rapidly changing hospital operational information without appropriate freshness controls.

### 12. Deployment Preparation

Prepare the project for deployment.

Suggested hosting:

Frontend:
Vercel.

Backend:
Render.

AI service:
Render.

Database:
PostgreSQL hosting provider.

Prepare:
- Production environment variables.
- CORS configuration.
- Database migrations.
- Production build commands.
- Service URLs.
- API credentials.
- Health-check endpoints.
- Deployment documentation.

Never commit API keys, database passwords, JWT secrets, or other credentials to GitHub.

### 13. Final Documentation

Create complete documentation covering:

- Overall architecture.
- Backend setup.
- Frontend setup.
- AI service setup.
- Database setup.
- Environment variables.
- API endpoints.
- Hospital registration workflow.
- Referral workflow.
- AI integration.
- Testing.
- Deployment.
- Troubleshooting.

### 14. Final Acceptance Criteria

The project is considered complete only when:

1. Hospitals can register and access the platform.
2. Hospital administrators can manage their own hospital information.
3. Healthcare workers can create referrals.
4. The three AI components work through the application.
5. The AI can retrieve authorized information from multiple hospitals.
6. Hospitals can receive and process referrals from other hospitals.
7. AI recommendations use current available information.
8. Users can communicate with the central AI assistant.
9. Hospital information updates are reflected in the knowledge system.
10. Access permissions prevent unauthorized data exposure.
11. Feedback and monitoring work.
12. The frontend, backend, database, and AI service communicate successfully.
13. The complete system can be deployed and operated.

### IMPORTANT DEVELOPMENT RULES

- Do not rewrite working components unnecessarily.
- Do not remove existing AI models.
- Do not replace PostgreSQL with MongoDB.
- Do not introduce unnecessary features.
- Do not use fake data as real production data.
- Do not leave critical features as TODO comments.
- Do not claim successful integration without testing.
- Maintain consistent API contracts.
- Fix discovered errors before declaring completion.

At the end, provide a detailed implementation report containing:

1. Features successfully implemented.
2. Features successfully integrated.
3. Tests executed and their results.
4. Remaining limitations.
5. Deployment instructions.
6. Known issues requiring attention.

The final result must be a fully integrated, functional RefHealth AI platform.