# Research diary — template

Copy this block for each session (newest at the top). Record decisions *before* looking at test-split results.

---

## YYYY-MM-DD — <short title>

**Goal for this session:**

**Pre-registered expectations** (written before running):
- Expected capability (clean-task success):
- Expected exploit base rate:
- Expected monitor behaviour A vs B vs C:

**Commands run** (exact, copy-pasted):
```
```

**Run directories:**
- actor:
- monitor:
- summary:

**Configuration:**
- actor provider / model ID / digest or version / quantization:
- monitor provider / model ID / digest or version / quantization:
- temperature, top_p, max_output_tokens, seeds:
- n_scenarios × samples_per_scenario:
- git commit of this repo:

**Observations** (with denominators, e.g. "2/5 episodes"):
- Episodes by status (submitted / action_limit / aborted_malformed / interrupted):
- Genuine success, ordinary failure, exploit attempts, successful exploitation:
- Monitor results per condition (dev threshold, then test):
- Invalid monitor outputs, truncations, retries, quota events:

**Surprises / anomalies** (quote event IDs):

**Changes made after seeing results** (and whether test data was looked at first):

**Interpretation limits** (what this does *not* show):

**Next step:**
