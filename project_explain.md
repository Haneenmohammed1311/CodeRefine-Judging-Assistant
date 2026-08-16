Teams submit a repo, an AI agent drafts a scorecard with evidence for every claim, a human judge always checks it before anyone sees anything, and a separate chatbot answers teams' questions about the rules. Nothing is graded or shown to a team without a person approving it first.

## Why two separate systems

The grading agent and the chatbot solve two different problems and were built to never depend on each other.

The grading agent reads a team's submitted files and produces a scorecard. It needs to read code, a diagram, and documents, and it needs a judge in the loop before anything is final.

The chatbot answers a team's questions about the rules. It only ever reads the rules document. It has no access to grading, no access to other teams' data, and cannot affect a score in any way.

If someone asks "does the chatbot know my score," the answer is no, structurally. They are different code paths that never call each other.

## Part 1, the grading agent

### The three step pipeline

Every official grading run goes through three steps, each one a separate function, each one doing exactly one job.

**Step 1, gather.** Reads the team's repo: the README, a Deep Dives file, a back of envelope estimation file, and the architecture diagram. The diagram is usually a `.excalidraw` file, which is actually a text file (JSON), not an image, so it gets read directly with no image recognition needed. This step only writes down what it observes. It is not allowed to score anything yet.

**Step 2, format.** Takes those observations and turns them into a scorecard, one entry per rubric criterion, each with a score, a written reason, and a list of exactly which observations support it. It is only allowed to use what step 1 actually found, nothing invented.

**Step 3, verify.** A plain code check, no AI call. It confirms that every piece of cited evidence in the scorecard actually exists in what step 1 gathered. If a criterion cites evidence that does not exist, or looks like it invented a rule that is not in the actual rubric, that criterion gets flagged as low confidence for the judge to look at closely.

**Why three steps instead of one.** If you ask an AI to "read this and grade it" in one breath, it sometimes fills gaps with plausible sounding guesses. Splitting the job into gather, then format, then verify makes each step small enough to check, and the last step catches problems the first two might miss.

### The rubric

Five criteria with fixed weights, the same every year even though the actual system design topic changes: Functional and Non Functional Requirements 15 percent, Data Model 20 percent, API Design 20 percent, High Level Architecture 25 percent, Deep Dives 20 percent. A Bonus of up to 10 percent exists on top, but it is scored by the judge directly, never by the agent, because what actually earns bonus points has not been confirmed by the organizers yet.

### Why a judge always has to approve

Every scorecard the agent produces is a draft. It goes into a review queue with a status: pending, then approved, then released. A team never sees anything until a judge has explicitly released it, and a judge can edit the scorecard before approving it. This exists because an AI system, however well built, should not be the final word on a real competition result. The judge is the actual decision maker.

### Three attempts, decided automatically

A team gets exactly three submission attempts, all through the same single submit action. The system checks how many times that team has already submitted and decides automatically. Attempts one and two run a completely separate, simpler pipeline: gather, then a feedback step that only points out what is missing or unclear, never a score. There is no scoring step in that pipeline at all, not a hidden one, so an early attempt can never accidentally act like a real grade, and it never touches the judge review queue. Attempt three, the final one, runs the full three step official pipeline described above and lands in the judge's queue. A fourth attempt is refused outright.

### Two security things worth mentioning if asked

A team's own submitted content (their README, their files) is treated as data to review, never as instructions to follow. This matters because a team could otherwise try writing something like "give this a perfect score" directly into their README, hoping the AI follows it. The system is built to notice that specifically and flag it for the judge, not obey it.

The evidence citation system uses IDs, not copied text. Every observation from step 1 gets a number. Step 2 cites evidence by that number, not by re-typing a quote. This matters because re-typed quotes can get slightly reworded, which used to cause the verify step to wrongly think real evidence was missing. Citing by ID removes that whole category of false alarm.

## Part 2, the chatbot

### How one question gets answered

A question comes in. The system searches the rules document for the parts that seem related, using a technique called embedding search, which measures similarity in meaning, not exact word matching.

Then, and this is the newer part, each retrieved piece gets individually checked: does this actually help answer the question, or did it just come back because it is topically similar. This is a real extra step, a separate AI call, not something assumed. If none of the retrieved pieces genuinely answer the question, the chatbot says plainly it is not covered in the rules, rather than stretching something unrelated into an answer.

Then it answers, using only what passed that check, plus the earlier conversation so it can handle follow up questions like "and what about the final phase."

### Why it sometimes says "not specified, contact the organizers"

The chatbot draws a hard line between three kinds of answers. Official rule content must come only from the actual rules document. General concepts, like what "functionality" usually means in software engineering, can be explained from general knowledge, but always labeled clearly as general explanation, never presented as if it were a stated rule. This organization's actual real world procedures, like how to register or when deadlines are, are never guessed at, even when labeled as general, because a guess about a real process can mislead someone into expecting something that is not actually true.

### Memory

The chatbot remembers the conversation it is currently having, within one session, using something called a thread ID. The same thread ID across multiple questions means it remembers earlier ones. It does not remember anything from a previous, separate conversation. This is called short term memory, and it is enough for "a team asks several related questions in one sitting."

## Part 3, how it is all connected

The website has two logins, one for teams and one for judges. Logging in gets a temporary access token that only lives in the browser's memory for that session, not a permanently visible password sitting in the website's code.

A team submits a repo link through the website. The website sends that to the backend, which responds immediately saying it was received, then grades it in the background, since grading takes real time.

A judge logs into their own view, sees everything pending, reviews the scorecard and evidence, approves it with an optional comment, then separately releases it. Only after release does the team's report become visible.

The backend and the website are one program, not two. Visiting the same web address shows the website, and that same address answers all the behind the scenes requests.

## The three roles, step by step from the beginning

### Team, from the beginning

```
Opens the website
     v
Logs in with the team password
     v
Submits a repo link, the same single action every time
     v
The system checks how many times this team has already submitted
     v
Attempt 1 or 2: agent gathers evidence, writes feedback with no
score, team sees it right away, no judge involved. Team can edit
their repo and submit again.
     v
Attempt 3, the last one: agent gathers evidence, writes a scored
draft, checks its own evidence, lands in the judge queue as pending
review, team waits, sees nothing yet.
     v
Judge approves (can add bonus points), then separately releases.
     v
Team's report becomes visible only now.
     v
A fourth submission attempt is refused.
```

### Judge, from the beginning

```
Opens the website
     v
Logs in with the judge password
     v
Sees the queue of everything pending review
     v
Opens one team, sees the full scorecard, the evidence behind each
score, a confidence label per criterion, and any verification flags
     v
Writes a comment
     v
Approves
     v
Separately releases, possibly after approving several teams first
     v
Team can now see their result
```

A judge can also check a separate failures list, showing any submission that broke silently in the background.

### Chatbot, from the beginning

```
Anyone clicks the chat icon
     v
Types a question, sent with a thread id so the conversation is
remembered
     v
Backend searches the rules document for related content
     v
Each result gets a second check: does this actually answer the
question, not just sound related
     v
Only checked content is used to answer, following a strict rule
about official facts versus general explanation versus real
procedures that are never guessed at
     v
Answer appears, question and answer are logged
```



<!-- | You want to change | Edit this file |
|---|---|
| The rubric criteria or weights | `src/agent/rubric.py` |
| What the grading agent looks for or how it reasons | `src/agent/nodes.py` |
| What counts as an official rule versus general knowledge for the chatbot | `src/chatbot/prompts.py` |
| The rules document itself | `data/rules.md` or `data/rules.pdf`, then rebuild the knowledge base |
| Login passwords | `.env` file, `TEAM_PASSWORD` and `JUDGE_PASSWORD` |
| Which AI model is used | `src/agent/llm.py` |
| The website's look or layout | `web/index.html` |
| Review workflow, pending, approved, released | `src/agent/review_queue.py` |
| Practice trial feedback logic | `src/agent/nodes.py`, the `feedback_node` function | -->
