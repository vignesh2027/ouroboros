# Ouroboros demo script

Run time: about 6 minutes. Two presenters: one clicks, one talks.

## Before you start

1. Open a terminal in the project folder and run `bash run_platform.sh`.
2. Open http://127.0.0.1:8000 in Chrome. It opens on the landing page. The page follows the computer's light or dark setting. The sidebar footer has Auto, Light and Dark buttons, so pick Light if the room is bright.
3. Look at Recent research in the sidebar. It should list the saved runs.

All six example questions and the two Compare questions (fasting and remote work) have been run once with the live model and cached. Clicking an example card replays from the cache: it finishes in seconds and makes no new model calls, and it works with no internet.

## The three ideas in one line each

- **BAQD (Belief-Aligned Query Drift):** how far the agent's next search has drifted toward what it already believes, instead of toward the question it was asked.
- **CQI (Counter-Query Injection):** when the search drifts or the evidence leans too far one way, the guard replaces the next search with one that looks for evidence against the current belief. On screen this is called a counter-search or balance check.
- **Evidence Support Score:** the share of the answer's claims that are backed by the evidence we retrieved, counted by claim, with a claim backed by two or more independent websites shown separately.

## What to click and what to say

**0. Landing page, about 1 minute**
- Scroll to "How everything is connected" and walk the diagram from left to right: the question goes to the agent, the agent searches five source types, our ranker orders the passages, the reader updates its belief and writes its own next search, and the balance guard either continues the loop or sends a counter-query. After the last round the writer produces a cited answer and the claim audit produces the evidence report.
- Point at the dashed box: an answer pasted from ChatGPT, Claude or Gemini goes to the same audit.
- Say: "The name is the ouroboros, a snake eating its own tail: the agent's searches feed its belief, and its belief shapes its next search."
- Scroll to Honest results and read it: the first study was a null result, and the live comparison on the small corpus has not shown a difference yet.
- Click Start researching.

**1. Home, about 30 seconds**
- Say: "You ask any question, and it shows what the evidence says, with sources you can open."
- Point at the ask box, the small "Balanced, Standard" options line under it, then at the six example questions.

**2. Ask an example, about 2 minutes**
- Click "Is intermittent fasting effective for weight loss?".
- Say: "The five steps tick off as it works: searching, reading, checking the search for bias, writing, checking every claim."
- Open the Sources tab. Say: "These are the real pages it read, with the website and year."
- Hover or click a small numbered citation in the answer. A card shows the title and snippet, and clicking scrolls to the source.
- Point at the Evidence block under the answer, and open Details: the score ring, the grade, claims backed, independent websites and the confidence gap. Say: "This is the share of claims backed by what we found. It is not the chance the answer is true."
- Open the Evidence map tab. Say: "Claims on the left, the sources that back them on the right. A filled dot means a claim is backed by two or more websites. A hollow ring means it rests on one. A dashed box means we found nothing for it." Hover a claim to light up its sources, click a source to jump to the passage. On a phone the map becomes a list of claim cards.
- Open the Research path tab. The Belief journey is at the top. Say: "Each round the agent writes down what it believes and its own next search. This chart shows how far its searches drifted toward its belief, where the balance check stepped in (the diamonds), how many passages agreed or went against, and how its confidence moved." Round 1 is blank on purpose, because there is no earlier belief to compare with. Point at a counter-search tag if one shows. Say: "Here the balance check stepped in and searched for the opposite view."
- Click "How this answer was made" beside the round count at the top of the answer. Say: "These are the real numbers for this answer: searches, documents fetched, passages ranked and read, claims checked. The table shows what a typical chatbot and a typical RAG search do, and what we do in this run." Say that typical systems vary and the columns are not any one product. Press Esc to close.
- Open the Evidence report tab and show a claim with its supporting passages.
- Use the follow-up box at the bottom, for example "What about for older adults?". This needs the internet. Say: "A follow-up is first rewritten into a question that stands on its own, then researched the same way."

**3. Check an AI answer, about 1 minute**
- Open Check an AI answer. The prefilled example shows the flow. Choose ChatGPT, Claude or Gemini, paste a real answer, then click Check this answer. This needs the internet.
- Say: "The same checker works on any AI's answer. Claims nothing supports are marked not verified. We do not call them false."
- The button "Get an unguarded answer to compare" shows a plain answer with no search. Skip it offline.

**4. Compare, about 1 minute**
- Click the fasting or remote work question, then click Compare.
- Say: "Same question. Left is a standard agent, right is the balanced one. Look at the table underneath."
- Read the numbers on screen. Do not claim a win if the table does not show one.

**5. How it works, about 1 minute**
- Show the flow diagram from Ask to Follow-up, including the loop back when a counter-search is needed. Say: "The ranking, the balance check and the audit are our own code." Point at the quiet line that says how many automated checks pass.
- On a small screen the diagram turns into a numbered list.

**6. Benchmark, about 30 seconds**
- Read the "Read this first" note aloud. Phase I used typed-in queries and was a null result. In the new live experiment the balanced and standard agents scored the same, and the 8-passage set runs out of passages by round 4, so it cannot tell them apart. Present it as a finding plus a next step, which is a bigger corpus.

## What the score does and does not mean

It does mean: of the claims in this answer, this share were backed by passages we retrieved in this run. It shows how well the answer is grounded in what we found.

It does not mean:
- It is not the probability that the answer is true.
- A low score does not prove the answer is wrong. The evidence we fetched may simply not cover it.
- A high score does not prove the answer is right. The sources could be weak or all say the same thing.
- It does not replace reading the sources. The links are there for that.

The confidence gap compares the model's own stated confidence with the score. A big gap means the model sounded surer than the evidence allows.

## If the internet fails

Run: `OFFLINE=1 bash run_platform.sh`

- The model and the search sources run from the cache only.
- Click any of the six example questions on the ask page, or the fasting and remote work questions in Compare, and they replay in full. The sidebar shows Offline mode.
- Saved runs open instantly.
- A question that was never run will show a plain message saying that only saved questions work offline. Do not type new questions in this mode.
- Check an AI answer, the unguarded answer and follow-up questions need the live service, so skip them offline.

## Questions examiners may ask

- Is the loop real? Yes. The model writes its own belief and its own next query on every hop. Nothing is scripted.
- What is hop 1 BAQD? Not defined, because there is no earlier belief yet, so it is blank rather than zero.
- Why a small model? It is cheap and fast. Everything is cached, so the demo costs nothing to repeat.
- Do the source sites change the result? Yes, a live run can differ from the saved one, because search sites change and sometimes refuse requests. That is why the demo uses saved runs.
