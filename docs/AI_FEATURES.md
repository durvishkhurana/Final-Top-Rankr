# AI features

TopRanker uses language models for explanation and drafting only. Scores, ranks,
precisions and every other number come from the judge. All AI features are optional:
with no provider key set they are switched off and the pages say so.

## Providers

| Provider | Used for | Setting |
|---|---|---|
| Groq | Text requests (analysis, coach, AI baseline) | `GROQ_API_KEY`, `GROQ_MODEL` (default `openai/gpt-oss-120b`) |
| Gemini | Image input (problem builder with a formula picture) and fallback when Groq fails | `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`) |

Gemini's free tier allows few calls a day, so `GEMINI_DAILY_LIMIT` caps it. Each user
also has `AI_DAILY_LIMIT_PER_USER` requests a day, and the whole server
`AI_DAILY_LIMIT_GLOBAL`.

## How a request is made

All requests go through `backend/ai/llm.py`:

1. The prompt is a versioned file in `backend/ai/prompts/` (for example
   `analysis.v1.md`) filled with `string.Template` placeholders.
2. The expected answer is a Pydantic schema; its JSON schema is appended to the prompt
   and the reply is validated against it.
3. An identical earlier request (same feature, prompt and image) is answered from the
   log without calling a provider.
4. Otherwise the preferred provider is tried, then the other one. A reply that does not
   match the schema is retried once; after that the user gets a clear error.
5. Every call is stored in `llm_calls`: feature, provider, model, user, tokens, latency,
   estimated cost, success and error.

Errors map to HTTP status codes: disabled (503), daily limit reached (429), provider
failure or unusable answer (502).

## Features

**Algorithm analysis** (`POST /api/submissions/{id}/analysis`). The model reads the
submitted code and names the closest algorithm family, its mutation, crossover,
selection, restart and local-search steps, and summarises what the code does. It sees
the code only.

**Run coach** (`POST /api/submissions/{id}/coach`). After judging, the model gets the
code and summary statistics computed by the judge: number of runs and failures, the
first error line, evaluations used, median precision after 10 % and 50 % of the budget,
final precision (median, best, worst), when the last improvement happened and the
score. All values are precisions relative to the reference value; raw objective values,
instance seeds, shifts, rotations and reference values are never sent. It returns a
diagnosis and one suggestion. Contest organisers set the coach to `specific`,
`concept` (ideas only, no code) or `off` per contest.

Both notes are generated once per submission and stored. Only the author and admins can
request or read them. They are labelled "AI-assisted assessment" in the interface.

**AI baseline** (`POST /api/admin/problems/{id}/ai-baseline`, admin only). The model is
given the public description, the search box, the dimension and the budget, the same
information a participant has, and writes an optimizer. The code is judged in the
sandbox like any submission and appears on the leaderboard as the bot entry
"AI-written optimizer (baseline)". When it is present, the leaderboard shows each
entry's score relative to it.

**Evolving AI challenger** (`/api/challengers`, started and steered by admins). An
optimizer written by the model that improves itself one generation at a time on one
problem and dimension (`backend/ai/challenger.py`, prompt `challenger.v1.md`):

1. Generation 1 is written from the public description alone (the AI baseline prompt).
2. Every later generation starts from the champion, the best judged generation so far.
   The model gets the champion's code and approach, the same summary statistics the run
   coach gets (relative precisions only), the last ten generations with their scores,
   and the best score of a human participant on that problem and dimension. It returns
   the new code, a one-sentence approach and what it changed.
3. The code is judged in the sandbox like any submission, under the bot account "AI
   challenger (evolving)". A worse generation is kept in the history; the champion
   only changes when a generation scores higher. The champion is the challenger's
   leaderboard entry, flagged like the baselines and left out of the global rating.

A worker job evolves every active challenger once a day at 04:00 UTC; an admin can also
press "Evolve now" or pause a challenger. Only one generation of a challenger runs at a
time. Each generation is one AI request counted against the challenger bot's own daily
limit (`AI_DAILY_LIMIT_PER_USER`) and the global one. When the model is unavailable the
generation is recorded as failed with the reason, and the champion stays. The problem
page shows every generation's score, approach and changes; its code stays private like
any submission's.

**Problem builder** (`POST /api/contributions/build`). A user describes a fitness
function in words, optionally with a PNG or JPEG of the formula (at most 2 MB; image
requests go to Gemini). The model drafts the name, description, box, dimensions and
Python source. The draft is a normal contribution: it is smoke-tested in a sandbox and
waits for an admin.

## In course tests

All numbers in these features (scores, points, the facts quoted to a student) are
computed by the platform. The model writes text and, when grading, a level between 0
and 1 that the platform multiplies by the question's points.

**Distractors** (`POST /api/tests/{id}/questions/{qid}/distractors`). Suggests wrong
choices for a multiple-choice question. They are only suggestions: the instructor adds
the ones they want.

**Pools of phrasings** (`POST .../pool`). For a one-line reasoning question about the
student's own run, the model writes about 20 phrasings of the instructor's template.
Phrasings may use only placeholders the platform can fill (`{budget}`,
`{last_improvement_evals}`, `{final_precision}` and a few more); others are dropped. The
instructor edits and approves the pool, and a test cannot be published before every
pool is approved. Each student gets one phrasing, chosen by
`hash(test, student, question)` and filled with facts from their own latest judged
submission (relative precisions and shares of the budget, as for the coach).

**Follow-up** (when the student saves a reasoning answer). One adaptive follow-up
question generated from the answer, the student's code and the run facts. If the model
is unavailable the test continues without it. This does not count against the
student's daily AI limit.

**Grading** (worker job after hand-in). Reasoning answers are graded against the
instructor's rubric. The model returns a level, a short rationale, a confidence, and
whether the answer, the follow-up answer, the code and the run facts contradict each
other; contradictions become flags for the instructor. The student's text is passed as
data and the prompt tells the model to ignore instructions in it; the instructor can
change any grade, and every grade (automatic or manual) is kept in an audit log.
Multiple-choice and numeric answers are graded by code only.

**Viva questions** (`POST /api/attempts/{id}/viva`, instructor). Three questions about
the student's own code to ask in person. Only the instructor sees them.

**Similarity second opinion** (`POST /api/courses/{id}/similarity/opinion`,
instructor). For one pair found by the token and syntax-tree comparison, the model gives
a verdict (likely shared, possibly shared, probably independent) with reasons. It is
not asked, and does not claim, to detect AI-written code.

## Contributed problems

Anyone signed in can propose a function `f(X)` at `/contribute`
(`POST /api/contributions`). Its source never runs in the API or worker process:

1. A worker job starts an evaluator container (`sandbox/evaluator.py`, same limits as
   submissions) and checks that the code loads, returns finite values on 200 random
   points, gives the same values twice, is finite at and slightly beyond the corners of
   the box, and is not constant.
2. Passing contributions wait for review; an admin reads the source and the checks and
   approves or rejects them (`/admin`, Contributions tab).
3. An approved contribution becomes problem `C-NNN` in the catalogue. Instances shift it
   by up to 0.2 of the box half-width (no rotation, so evaluations stay where the smoke
   test looked). While a submission is judged, the worker relays points to an evaluator
   container; reference values come from the best runs, as for other problems without a
   known optimum.
