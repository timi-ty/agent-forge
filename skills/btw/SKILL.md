---
name: btw
description: >-
  Interrupt the current task with a side-task that runs in a background subagent.
  Use when the user says /btw followed by a task description.
disable-model-invocation: true
---

# BTW -- Background Side-Task

Spin up a background subagent for a side-task, then immediately resume the main task. Results are collected and presented after the main task completes.

Multiple `/btw` commands can stack -- each one launches an independent background subagent.

## Workflow

```
BTW Progress:
- [ ] Step 1: Parse the side-task
- [ ] Step 2: Gather context
- [ ] Step 3: Warn on overlap
- [ ] Step 4: Launch background subagent
- [ ] Step 5: Resume main task
- [ ] Step 6: Collect and present results
```

---

### Step 1 -- Parse the Side-Task

Extract everything after `/btw` in the user's message as the side-task description. If the message is just `/btw` with no task, ask the user what they want done and stop until they respond.

### Step 2 -- Gather Context

Assemble a context block for the subagent prompt. Include:

1. **Workspace root path** -- from the system prompt or `$PWD`.
2. **Git state** -- run `git rev-parse --abbrev-ref HEAD` and `git status --short` (5-line cap) so the subagent knows the branch and dirty state.
3. **Mentioned files** -- any file paths explicitly named in the side-task description. Read them and include their contents (or a summary if very large) in the subagent prompt.
4. **Main-task summary** -- write one sentence describing what the main agent was doing before the interruption. This lets the subagent avoid stepping on it.

### Step 3 -- Warn on Overlap

Compare the files you have been actively editing (look at your own tool calls in this conversation) against the files the side-task is likely to touch.

If there is likely overlap, emit a short warning to the user:

> Heads up -- the side-task may touch files I'm currently editing. Proceeding anyway; I'll flag conflicts at the end.

Then proceed regardless.

### Step 4 -- Launch Background Subagent

Call the `Task` tool with these parameters:

- `subagent_type`: `generalPurpose`
- `run_in_background`: `true`
- `model`: `fast`
- `description`: a 3-5 word summary of the side-task
- `prompt`: a self-contained prompt built from Step 2's context block plus the side-task description. The prompt must end with:

> When you are done, return a concise summary of exactly what you changed (files, lines, commands) and any issues encountered.

Record the returned `output_file` path. If this is not the first `/btw` in the conversation, append it to the existing list rather than replacing it. Track each entry as `(task_description, output_file)`.

### Step 5 -- Resume Main Task

Look at your own previous messages and tool calls in this conversation. Identify where you left off on the main task and continue from there. Do NOT re-do completed work. Do NOT mention the btw machinery to the user again until Step 6.

If there is no prior main task (the `/btw` was the very first message), simply inform the user that the side-task is running in the background and wait for their next instruction.

### Step 6 -- Collect and Present Results

Run this step only after the main task is fully complete.

For each tracked `(task_description, output_file)`:

1. **Read the output file.**
2. **Check if the subagent is still running** -- if the file has no `exit_code` footer yet, poll up to 3 times with escalating waits (2 s, 4 s, 8 s). Re-read the file after each wait.
3. **If still running after polling**, report to the user:
   > BTW "{task_description}" is still running. Check the output later at: `{output_file}`
4. **If finished**, read the subagent's final output and include it in a summary.

Present all completed side-task results under a **BTW Results** heading:

```
## BTW Results

### {task_description}
{subagent summary}
```

#### Conflict check

After presenting results, compare the set of files modified by the main agent (from your own tool calls) against the files the subagent reports modifying. If any file appears in both sets, flag it:

> Potential conflict: both the main task and the BTW side-task modified `{file}`. Please review manually.

---

## Important Principles

- **Non-blocking** -- the side-task must never delay the main task. Launch it in the background and move on immediately.
- **Self-contained subagent prompt** -- the subagent has no access to this conversation's history. Its prompt must include everything it needs: workspace path, relevant file contents, git state, and the task description.
- **Stackable** -- every `/btw` adds to the list. Never discard a previous entry.
- **Minimal noise** -- do not narrate the btw machinery while working on the main task. The only user-visible output is the optional overlap warning (Step 3) and the final BTW Results section (Step 6).
