# DeepSeek-V4 Agent Defense -- layered examples

## Contents

- [Layer 1 examples (prompt structure)](#layer-1-examples-prompt-structure)
- [Layer 2 examples (context management)](#layer-2-examples-context-management)
- [Layer 3 examples (tool calling)](#layer-3-examples-tool-calling)

Companion to `SKILL.md`. The core keeps the failure-mode table, the layer
summary and the hosted-agent subset; `references/layer-rules.md` keeps the
rules these examples illustrate, and this file keeps the worked examples.
Apply the rule; consult the example only when the shape of the output matters.

## Layer 1 examples (prompt structure)

### Signal amplification -- first 2 sentences

Good:

```text
Read src/auth/session.py and find all places where user roles are checked
without signature verification. Then write a patch for each.
```

Avoid:

```text
I'm working on a codebase that has user authentication. We use Flask
sessions. Let me give you some background... [500 words later] ...oh, and I
need you to check role verification in session.py.
```

### Hierarchical context layout

```text
1. [TASK] Core instruction (what to do, 2-3 sentences max)
2. [RULE] Critical constraints (must-nots, format requirements)
3. [CODE] Most relevant code/files (the ones the task directly modifies)
4. [CODE] Supporting context (imports, dependencies, related files)
5. Background information (architecture docs, historical context)
```

### Position-aware content layout

```text
[CODE] src/auth/session.py
[START] -- File header, imports, key function signatures
[MIDDLE] -- Implementation details, helper functions
[END] -- Entry points, exports, public API
```

## Layer 2 examples (context management)

### Chunking pipeline for large codebases

```text
Step 1: Map the repo structure (tree view, <500 tokens)
Step 2: Route each task to a context window of <200K tokens
Step 3: Include only files relevant to the current task
Step 4: After each chunk, ask [CHECK] verification before proceeding
Step 5: Merge results with cross-references
```

### Pinch point pattern

```text
[TASK] Refactor src/api/handlers.py to use async/await
[RULE] Do NOT modify any test files
[RULE] Keep the existing API response format unchanged

... [code, context, etc.] ...

[BEFORE ACTION] Reminder: [RULE] Do NOT modify test files.
[BEFORE ACTION] Reminder: [RULE] Keep existing response format.
```

### Progressive context loading

```text
Wave 1 (<500 tokens):  Task instruction + key constraints
  -> Model responds with approach plan
Wave 2 (<50K tokens):  Task + most relevant file(s)
  -> Model edits/solves
Wave 3 (as needed):    Additional files for cross-referencing
  -> Model verifies consistency
```

## Layer 3 examples (tool calling)

### Reasoning-content passthrough (custom loop)

```python
# Always carry forward the full assistant message including reasoning_content
assistant_msg = response.choices[0].message
messages.append({
    "role": "assistant",
    "content": assistant_msg.content,
    "reasoning_content": assistant_msg.reasoning_content,  # MUST preserve
    "tool_calls": assistant_msg.tool_calls,
})
```

### Tool definition optimization

Good:

```json
{
  "name": "read_file",
  "description": "Read file at path. Example: src/auth.py",
  "parameters": {
    "path": {"type": "string", "description": "File path relative to project root"}
  }
}
```

Avoid:

```json
{
  "name": "read_file",
  "description": "This function reads a file from the filesystem. It takes a path parameter which should be a string pointing to the location of the file you want to read. The path can be absolute or relative to the current working directory.",
  "parameters": {
    "path": {"type": "string", "description": "The path to the file"}
  }
}
```
