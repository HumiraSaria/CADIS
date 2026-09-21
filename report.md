# CADIS — A Plain-Language Report of What Was Done and What Was Found


---

## 1. What this project was about

Modern computer programs called AI (Artificial Intelligence) agents can now carry out multi-step
tasks on their own — including security testing, where a program is asked to find and use weaknesses
in a computer system it has permission to attack. These programs are useful but not fully trustworthy:
they sometimes **confidently invent things that do not exist** — a command, an option, or a web
address — and state them as if they were true. Because each step the program takes feeds into the
next one, a single made-up step can send the whole attempt down a false path. When several such
mistakes happen in a row, we call it a **cascade** (a spiral of mistakes building on each other).

The idea tested in this project is a supervisor layer called **CADIS**. It sits between the AI agent
and the computer, and for **every action the agent wants to take** it makes a judgement: *how much
should we trust the agent right now?* Based on that judgement it does one of four things — let the
action run automatically, let it run but tell a person, pause and ask a person to approve it, or hand
the decision fully to a person. The central claim being tested was simple:

> **Supervising more carefully when the agent is uncertain or the action is dangerous should be safer
> than either never supervising or always supervising — and it should beat simply supervising the same
> amount at random moments.**

That last comparison (against random supervision) is the important one. It checks whether CADIS steps
in at the *right* moments, not just at *some* moments.

---

## 2. How it was tested

The test was set up carefully and honestly, and **all the settings were locked in writing before any
result was collected**, so nothing could be adjusted afterwards to make the outcome look better.

- **Four ways of supervising were compared:**
  1. **Full autonomy** — the agent acts entirely on its own; no person is ever involved.
  2. **Always-ask** (in the study: Static HITL, Human-In-The-Loop) — a person must approve every
     single action.
  3. **Random** — a person steps in the *same amount of the time* as CADIS, but at random moments.
     This is the fair yardstick.
  4. **CADIS** — a person steps in based on CADIS's trust judgement.
- **Three different AI models** were each run through the whole test, so the findings are not tied to
  one particular program.
- **Three practice targets** were used (isolated, disposable practice systems, reset between runs), and
  **each combination was repeated three times** — 36 runs per model.

Four things were measured, in plain terms:
- **HCR (Hallucination-Cascade Rate)** — how often a run fell into a spiral of made-up commands.
- **HER (Human-Effort Ratio)** — what share of the agent's actions needed a person's involvement.
- **TCR (Task-Completion Rate)** — how often the agent actually finished the break-in task.
- **TTC (Time-to-Completion)** — how long a run took.

---

## 3. What was found

### Finding 1 — The main danger never actually happened
Across every model and every way of supervising, **the spiral-of-mistakes never occurred** — not even
once, and not even when the agent had no supervision at all. Because the danger never appeared, the
central question ("does CADIS reduce the spiral better than random supervision?") **could not be
answered** — there was simply nothing to reduce.

Importantly, this was **not bad luck**. As **Figure 1** (`fig1_cascade_nonoccurrence`) shows, the
longest chain of "made-up-command" mistakes that ever occurred was **one** — the spiral needs a chain
of at least three. And the rate at which these mistakes happened (about 1 in 30 to 1 in 100 steps) is
far below the rate that a study of this size could ever have detected as a spiral. In short: **the
agents on these practice targets simply do not make up commands often enough, or in long enough runs,
for the danger to arise.** This is a genuine and useful result about the *limits* of the problem.

### Finding 2 — The supervisor kept human effort low, and fair
As **Figure 2** (`fig2_human_effort_by_condition`) shows, CADIS asked a person to get involved in only
about **3 out of every 10 actions**, compared with **10 out of 10** for the always-ask approach. It
also matched the random yardstick almost exactly — meaning the fair comparison was set up correctly.
So the machinery around CADIS behaved sensibly and predictably across all three models.

### Finding 3 — The supervisor both helped and hurt, depending on the situation
This is the most revealing result. When CADIS blocked an action, we checked what would have happened
if the action had been allowed. Two opposite patterns appeared, on two different targets
(**Figure 3**, `fig3_blocked_action_two_regime`):

- On a hard target (an old file-transfer service that could not actually be broken into here), the
  agent kept trying the same hopeless attempts over and over. **CADIS blocked these useless attempts,
  which saved a lot of wasted time** — see the time results in **Figure 5**
  (`fig5_ttc_distribution`), where CADIS removes the very long "stuck and flailing" runs (on the weaker
  models, from many minutes down to seconds).
- On a solvable web target, the agent had found the **real, correct way in** — a genuine login
  weakness (a SQLi, or Structured Query Language injection, which tricks a login form into letting you
  in). **CADIS blocked that correct attempt too**, so the task was left unfinished.

The reason is important: CADIS decides based on **how dangerous an action looks**, not on **whether the
action would actually work**. A real break-in step and a hopeless one can look equally dangerous. So
the *same* rule that helpfully stops hopeless flailing also unhelpfully stops genuine progress. The one
clear drop in task completions came from this — and it was made worse by the strict rule used in the
study to reject every risky action. A real human, seeing that the risky action was actually a valid,
correct step, would likely have approved it.

### Finding 4 — The clever part of the design was not really needed
CADIS was designed to combine **three** signals to make its judgement: how consistent the agent is when
asked the same thing several times, its recent track record, and how risky the action looks. When we
took the judgement apart (**Figure 4**, `fig4_rc_dominance`), it turned out that **almost all of the
important decisions were driven by just one of the three signals — the risk of the action.** The other
two contributed almost nothing here. So the complicated three-part design effectively reduced to a
simple risk rule in this setting.

A summary of all the numbers is in **Table 1** (`table1_master_results.md`).

---

## 4. What was actually achieved

The project did **not** show that CADIS works as originally hoped. As a tool, it did not deliver its
intended safety benefit, and in one case it reduced success by blocking a correct action. That is
stated plainly and honestly. But the research still produced several real and useful results:

1. **It mapped the limits of the problem.** It showed, with careful measurement, that the
   spiral-of-mistakes danger **does not arise** for capable modern models on ordinary practice targets,
   and it quantified *how rare* the mistakes would have to be before this kind of study could even see
   the danger. This saves future researchers from repeating the same test expecting a different result.
2. **It showed a real trade-off in supervising by risk.** Blocking actions by how dangerous they look
   will unavoidably block some genuinely useful actions, because "dangerous" and "useless" are not the
   same thing. This is a concrete lesson for anyone designing this kind of safety layer.
3. **It showed the design was more complicated than it needed to be.** The three-signal judgement
   collapsed to a single risk rule, which tells designers where the added complexity was — and was not
   — earning its keep.
4. **It produced a careful, reusable way to test such systems.** The honest set-up — locking all
   settings in advance, and above all comparing against a fair "random supervision at the same effort"
   yardstick — is itself a contribution, because most similar work only compares against the two extreme
   cases (never supervise / always supervise).

In short: the specific gadget did not win, but the work answered real questions about *when this whole
approach helps, when it hurts, and why* — which is a legitimate and defensible result.

---

## 5. Honest limitations

- The main safety question could not be answered because the danger never occurred (Finding 1).
- Only three practice targets and three repeats were used, so the numbers are small and should be read
  as indicative, not precise.
- One of the three models used an older measurement method, so a few of its numbers are not directly
  comparable and are marked as such wherever they appear.
- The "person" in the loop was a fixed automatic stand-in following a strict rule, not a live human;
  a real human might have approved the correct-but-risky action and changed the completion results.

---

## 6. Bottom line

The honest conclusion of this research is a **negative result with a clear explanation**: oversight
based on risk and uncertainty did not improve safety in this setting — mainly because the safety
problem it targets did not occur, its clever machinery reduced to a simple rule, and judging actions by
risk trades away useful work. Alongside that, the study contributed a careful, fair testing method and
a clear picture of the boundaries of the problem. Knowing that a reasonable idea does **not** work, and
understanding exactly **why**, is a real and useful outcome.
