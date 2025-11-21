# Archived Services

This directory contains services that are no longer actively used but are kept for reference.

## hybrid_agent_service.py

**Archived Date**: 2025-11-21

**Reason**: This service implements a hybrid agent using Dashscope (Alibaba Cloud) for decision-making + OpenAI for generation. However:

1. It's not integrated with the main application
2. It references non-existent database models (`CharacterState`, `WorldSetting`)
3. The actual 3Agent mode is implemented in `ai_orchestrator_helper.py`

**Note**: If you need to use this service, you'll need to:
- Update the model imports to use the correct models from `novel.py`
- Update the database session handling to use the correct pattern
- Integrate it with the main routing system
