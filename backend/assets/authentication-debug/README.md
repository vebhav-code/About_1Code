# AUTH-001: Session Expiry Bug

## Scenario
Users can successfully log in to the application. After approximately 40 seconds, they are automatically logged out with no error message.

## Your Task
1. Read through the `buggy_project/` source code
2. Reproduce the bug locally
3. Use any AI tool (ChatGPT, Gemini, Claude, Cursor, Copilot) to help you debug
4. Document your entire AI conversation in `debug_log.txt`
5. Fix the bug in the source code

## Setup
```bash
cd buggy_project
npm install
npm run dev
```

## Expected Behavior
Users should remain logged in for at least 24 hours (the intended session duration).

## Actual Behavior
Users are kicked out after ~40 seconds.

## Hints
- The bug is in the authentication/session handling code
- Look at how tokens and their expiration are configured
- This is a common real-world mistake

## Submission
Package your fixed code as `fixed_project.zip` and include your `debug_log.txt`, then upload both on the contest page.
