# AGENTS.md

## Project Context
This repository contains Klarumzug24, a moving price estimation platform.

## General Rules

- Do NOT rewrite existing core backend logic unless explicitly asked
- Do NOT hardcode business logic in the AI layer
- Always reuse existing functions and services
- Prefer minimal, safe, incremental changes

## AI Architecture Rules

- All AI-related code must be inside:
  backend/app/ai/

- Suggested structure:
  - agent.py
  - tools.py
  - prompts.py
  - schemas.py

## Coding Guidelines

- Keep code simple and readable
- Avoid unnecessary abstractions
- Add comments only when helpful
- Use existing project conventions

## Tool Integration

- Tools must call real backend logic
- Never fake or simulate responses
- Validate inputs before tool execution

## Chat Behavior

- All user-facing responses MUST be in German
- Ask for missing information before acting
- Use tools only when sufficient data is available
- Always clarify that price is an estimate

## Safety Rules

- Never invent prices
- Never assume missing data
- Never promise guaranteed results

## Workflow

1. Analyze existing project structure
2. Propose a minimal plan
3. Implement small changes step by step
4. Show modified files
5. Wait for user confirmation before large changes

## Testing

- If no tests exist, propose manual test steps
- Do not deploy or modify docker unless required
