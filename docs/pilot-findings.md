# Pilot findings (September–October 2026)

Moved verbatim from the README on 2026-10-30, when the README was rewritten for the paper release. This is
the record as it stood before the confirmatory studies (paper Studies 1–5); the paper and
[the study index](README.md) supersede it. Only headings and relative links were adjusted for this page.

## Findings (pilot scale)

> Every result below rests on **5–7 exploit-attempt episodes per set**, one agent model, synthetic
> tasks and a handful of prompts. These are pilot observations, not general or significant findings.
> Details, caveats and all numbers with denominators are in [`docs/results/`](results/).

**Setup used for most runs:** agent `llama3.1:8b` (Ollama, Q4_K_M) on 4-order tasks; monitors
`llama3.2:3b` and `llama3.1:8b`; a mechanical rule baseline (`rule-v2`) as a reference.
AUC below = P(a random exploit episode scores higher than a random non-exploit episode); 0.5 = chance.

1. **The 3B monitor did not discriminate reliably** under any prompt tried: AUC ≈ 0.42–0.69, and a
   pre-registered test on fresh episodes gave no support for it.
2. **Report-only monitoring (condition A) was useless.** With just the agent's final report, every LLM
   monitor gave nearly every episode the same score.
3. **LLM monitors conflated task failure with manipulation.** With the original prompt (v1), the 8B
   monitor scored all 90 judgements 0.8 and called honest failures "manipulated". Prompts that define
   honest mistakes (v2–v4) moved the 3B monitor to the opposite bias (almost nothing flagged), without
   improving discrimination.
4. **Model size mattered, but only with a precise prompt.** The 8B monitor went from no discrimination
   (v1, AUC 0.50) to modest discrimination with the v3 checklist prompt. That result **passed a pre-registered
   test on two unseen datasets** (unprompted: AUC 0.74, 5/5 caught under C; elicited: AUC 0.66, 6/7 caught),
   but its numeric score raised many false alarms (43–56% under C at a 0.5 cut).
5. **The 8B monitor's own checklist was the better signal.** On both unseen datasets it caught about as many
   exploits as the score with roughly half the false alarms (C: 4/5 vs 8/25; 6/7 vs 5/23). This was a
   secondary observation and is the next candidate for a pre-registered test. Its written explanations
   named the correct manipulation in all 5 unprompted positives, even when the score was a middling 0.5.
6. **The evidence is in the trace:** the rule baseline reached AUC 0.96–1.0 under B/C. But it only
   encodes the two known mechanisms, while LLM monitors are meant to generalise and did so unreliably.
7. **Unprompted weak agents "exploited" in ~17–24% of episodes**, mostly in ways that look like confusion
   or hallucination (for example citing an invented evidence ID, or ticking orders before recording them).
   The behavioural labels cannot separate this from deliberate gaming.
8. **Telling the agent it is judged only by the score barely changed its behaviour** (7/30 exploit
   attempts vs 5/30 unprompted). It shifted somewhat toward removing orders from scope and never admitted
   the strategy in its notes. A stronger elicitation is needed to collect many positives.
9. **Method lesson:** a pattern found while exploring (the 3B's checklist catching exploits its score
   ignored) **did not replicate** in a pre-registered test on fresh episodes (0/5 caught), while the
   8B + v3 result did replicate. Pre-registration separated the two.

## Runs completed

| # | Run | Data | Result in brief | Write-up |
|---|---|---|---|---|
| 0 | Offline build + fixtures | 5 scripted behaviours × 10 seeds | All labels correct; pipeline validated | — |
| 1 | Gemini pilot | Gemini 2.5 Flash agent, 1/5 episodes (20 req/day free tier) | Honest success; 3B monitor falsely flagged it | — |
| 2 | Local pilot | 8B agent, seeds 2000–2004 | 2 exploit-type episodes; rule-v1 missed invented evidence → `rule-v2` | [limitations](limitations.md) |
| 3 | Main run, 3B monitor (v1) | 8B agent, seeds 3000–3029, 7/29 exploit | 3B ≈ chance; rule-v2 7/7 caught, 1 false alarm | [local-run](results/2026-09-28-local-run.md) |
| 4 | 8B monitor (v1) | same 30 episodes | Constant 0.8 on all 90 judgements | [3b-vs-8b](results/2026-09-28-monitor-3b-vs-8b.md) |
| 5 | Prompt variants v2–v4, 3B | same 30 episodes | Bias flipped, discrimination unchanged | [prompt-variants](results/2026-09-29-monitor-prompt-variants.md) |
| 6 | **Pre-registered** checklist detector, 3B v3 | fresh seeds 4000–4029, 5/30 exploit | H1 not supported: 0/5 under C | [checklist-fresh](results/2026-09-29-checklist-detector-fresh.md) |
| 7 | 8B monitor, v3 | seeds 3000–3029 | Best LLM result (AUC 0.71–0.74), exploratory | [checklist-fresh](results/2026-09-29-checklist-detector-fresh.md) |
| 8 | **Pre-registered** 8B v3 confirmation | fresh seeds 4000–4029 (unseen by 8B) | H2 met: AUC 0.74, 5/5 caught, but 14/25 false alarms | [8b-v3-confirmation](results/2026-10-02-8b-v3-confirmation.md) |
| 9 | **Pre-registered** elicited-adversarial dataset | seeds 5000–5029, "judged only by score" prompt, 7/30 exploit | Elicitation weak; 8B v3 met H2 again (AUC 0.66); checklist 6/7 with 5/23 false alarms; 3B ≈ 0 | [elicited-dataset](results/2026-10-02-elicited-dataset.md) |
| 10 | **Pre-registered** hacking vs failing (8B v5 primary) | seeds 6000–6059, 14/60 exploit; scripted fixtures; calibration | Primary R1 not met: AUC 0.64, 0/35 false alarms but 4/14 caught; v3 catches 13/14 with 20/35 false alarms | [hacking-vs-failing](results/2026-10-06-hacking-vs-failing.md) |

## Open next steps

* Pre-register **8B + v3 checklist-as-detector** as the primary measure and test it on a fresh dataset.
* A stronger elicitation (for example naming the mechanisms), or a different agent model, to get many more positives.
* Repeated monitor samples at temperature > 0 to measure consistency.
* Finish the Gemini-agent pilot (`wml resume --run-dir runs/gem-actor --enable-network`, about one episode/day).
