---
description: One page that explains the system to people who do not read code
argument-hint: "[who it is for]"
---

I need to explain this project to someone who does not read code${ARGUMENTS:+ ($ARGUMENTS)}. Do this from the project folder:

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/flow hld`, `${CLAUDE_PLUGIN_ROOT}/bin/flow bottleneck`, `${CLAUDE_PLUGIN_ROOT}/bin/flow debug` and `${CLAUDE_PLUGIN_ROOT}/bin/flow gaps`. The first may run every test once.
2. Write a summary of two short paragraphs, for a reader who has never seen the code. Paragraph one: what the system does, in terms of what users or the business get, using the use case names. Paragraph two: what stands out, such as where the time goes, what fails, what no test covers. Use only what the commands printed. No module names unless the reader needs one. No jargon. Say "untested", never "broken". Quote shares, not milliseconds.
3. Run `${CLAUDE_PLUGIN_ROOT}/bin/flow brief --summary "<your summary>"`. It writes `flowscope-brief.html` in the project folder.
4. Tell me the path, and give me the two paragraphs so I can read them before I send the page. Mention anything in the page I should check first, such as a failing test or a guess you were not sure of.

Do not claim the system is correct or safe because the tests pass. They show what ran, not that it is right.
