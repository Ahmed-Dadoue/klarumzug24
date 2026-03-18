# Klarumzug24 – Project Overview

## Description
Klarumzug24 is a German moving platform that helps users estimate moving costs and connect with suitable moving companies.

## Main Goal
Convert user input (chat or form) into structured moving data, calculate an estimated price, and optionally generate a qualified lead.

## Core Features
- Moving cost estimation (based on rules or ML model)
- Lead generation and distribution to companies
- Privacy layer (limited data exposure before acceptance)
- Company matching (round-robin or logic-based)

## AI Assistant: Dode

Dode is an AI-powered assistant integrated into Klarumzug24.

### Responsibilities
- Ask users relevant questions about their move
- Extract structured data from natural language
- Detect missing required information
- Call backend tools (e.g., price calculation)
- Return clear, structured answers in German

### Limitations
Dode must NOT:
- Invent prices or calculations
- Guarantee final binding offers
- Assume missing data without asking
- Modify backend logic

## Target Users
- Private customers planning a move
- People looking for quick price estimates
- Users who prefer chat over forms

## System Architecture
- Backend: FastAPI
- Database: SQLite (klarumzug.db)
- AI Layer: LangChain + OpenAI
- Frontend: Static HTML pages (docs/)
- Deployment: Docker

## Philosophy
Keep business logic deterministic and controlled.
Use AI only for:
- understanding input
- guiding the user
- orchestrating tool usage
