# use-capability

**Goal**: Route user's stated goal to the right *existing* tool or skill and run it.

This is the runtime front door. It accepts a user's expressed intent, matches it with an available capability in the system (either existing tools or skills) and routes the execution to that capability. It ensures no new capabilities are created here - only use of what already exists.