# RAG Logging Fix Plan

## Issue Description
Currently, when the Planner or Writer agents use RAG tools (e.g., `search_chapters`, `check_plot_consistency`), the execution details (search queries, results, reasoning) are logged to the server console (stdout) but **not** persisted to the `auto_generator_logs` database table.

**Impact**:
- Frontend users cannot see what the agents are searching for or what they found.
- The "Generation Logs" panel only shows high-level status updates ("Planning started", "Planning finished"), making the system feel opaque.
- Users cannot verify if RAG is actually working or helpful.

## Proposed Solution
Implement a `log_callback` mechanism that allows `ai_orchestrator_helper.py` to send log messages back to `AutoGeneratorService`, which then persists them to the database.

### 1. Modify `ai_orchestrator_helper.py`

Update the following functions to accept an optional `log_callback: Callable[[str, str], Awaitable[None]]` argument:
- `generate_outline_with_agents`
- `_generate_outline_with_agents_impl`
- `_call_outline_planner_agent`
- `_call_outline_writer_agent`
- `_execute_tools`

**Signature Change**:
```python
# Before
async def _execute_tools(db_session, tool_calls, project_id, chapter_number): ...

# After
async def _execute_tools(
    db_session, 
    tool_calls, 
    project_id, 
    chapter_number, 
    log_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
): ...
```

**Usage in `_execute_tools`**:
```python
if log_callback:
    await log_callback("info", f"🛠️ Agent is using tool: {function_name}...")

# ... execute tool ...

if log_callback:
    await log_callback("info", f"✅ Tool {function_name} returned results")
```

### 2. Modify `auto_generator_service.py`

In `_auto_generate_outlines`, define a callback wrapper and pass it to the orchestrator:

```python
# Define callback
async def log_callback(log_type: str, message: str):
    await cls._log(db, task.id, log_type, message)

# Pass to orchestrator
result = await generate_outline_with_agents(
    # ... other args ...
    log_callback=log_callback
)
```

## Detailed Changes

### `backend/app/services/ai_orchestrator_helper.py`

1.  **`_execute_tools`**:
    - Add `log_callback` parameter.
    - Log "🔍 Executing tool: [Tool Name]" before execution.
    - Log "📄 Tool Output: [Summary]" after execution.

2.  **`_call_outline_planner_agent` & `_call_outline_writer_agent`**:
    - Add `log_callback` parameter.
    - Pass `log_callback` to `_execute_tools`.
    - Optionally log "🤔 Agent is thinking..." when receiving a non-final response.

3.  **`generate_outline_with_agents` & `_generate_outline_with_agents_impl`**:
    - Propagate `log_callback` down the call stack.

### `backend/app/services/auto_generator_service.py`

1.  **`_auto_generate_outlines`**:
    - Create the `log_callback` closure capturing `db` and `task.id`.
    - Pass it to `generate_outline_with_agents`.

## Verification Plan
1.  Start a new "3-Agent Dialogue" auto-generation task.
2.  Monitor the "Generation Logs" panel in the frontend.
3.  Verify that logs appear like:
    - `INFO`: 🔍 Planner is searching for "foreshadowing about the amulet"
    - `INFO`: ✅ Search returned 3 results
    - `INFO`: 🛠️ Checking plot consistency...
