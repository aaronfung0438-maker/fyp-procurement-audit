# Procurement Audit Study — Participant Briefing

Thank you for joining this study. Please read this page carefully before
starting. The study takes about **35 to 45 minutes** in total and **cannot
be paused mid-way without losing your progress**.

## Your Role

You are acting as an **internal auditor at a 30-person electronics
company**. The company has just received a batch of recent purchase
orders (POs) submitted by engineers and approved by procurement
officers. Your job is to review each order and decide whether it is
**Normal** or **Suspicious**.

A **Suspicious** order is one where you believe something is unusual,
inconsistent, or warrants further internal investigation. A **Normal**
order is one that, given the information available, looks routine for
this company.

### Useful Context About the Company

- The company has a **roster of routinely-used suppliers** identified
  in the data as **S-001 through S-025**. Any other supplier ID
  appearing in an order represents either a newly-onboarded supplier
  or a one-off purchase — both can be legitimate, but unfamiliar
  suppliers are also a common context for procurement risk.
- Approval thresholds in the company's policy mean that small orders
  are signed off locally, while larger orders need higher-level review.
  Look out for orders whose totals are sized to land just under those
  thresholds.
- Engineers (`R-ENG-XX`) submit the orders; procurement officers and
  managers (`A-PROC-XX`, `A-CTO`, `A-CEO`) approve them at different
  authority levels.

## What You Will See for Each Order

Every order is presented as a single screen with three sections:

- **Section A — Order Details.** Raw fields such as PO ID, supplier,
  item, quantity, unit price, total amount, requester, approver, dates,
  and lead time.
- **Section B — Free-text Notes.** Two short notes written by the
  requester and the supplier (purchase note + supplier profile).
- **Section E — Deviation Sentences.** A small set of natural-language
  comparison sentences (for example: *"Unit price $0.13 vs SKU
  historical median $0.11 (1.13× higher)"*). These are computed
  automatically; they describe how this order compares to the company's
  own history and to general market data. They do **not** tell you
  whether the order is suspicious — that decision is yours.
  **Section E is shown to every participant in every group**,
  regardless of whether you also receive AI assistance.

Some groups will additionally see AI output. Your group-specific page
(next) will explain exactly what you will see.

## Common Red Flags in Procurement (Background Knowledge)

You are **not** expected to memorise a checklist, and there is no
single rule that decides whether an order is suspicious. The list below
is a non-exhaustive summary of the kinds of patterns that internal
auditors typically look for — it is the same kind of background
knowledge a new graduate auditor would receive on day one.

A real anomaly often looks like a combination of two or three weak
signals from the list, not one obvious smoking gun. Conversely, any
single deviation can have a perfectly legitimate business explanation.

1. **Inflated unit price.** The unit price is much higher than typical
   market or historical rates for the same item — e.g. paying 3× the
   normal price for a standard component.
2. **Threshold-skimming totals.** The order's total amount sits just
   below an internal approval threshold (for example, $980 when the
   threshold is $1,000), suggesting the order was sized to avoid
   higher-level review.
3. **Unfamiliar supplier.** The order goes to a supplier with no prior
   history at the company, sometimes a newly-registered or
   thinly-documented entity.
4. **Vendor-spending concentration.** A disproportionate amount of
   recent spending is being channelled to a single supplier, beyond
   what the company's needs would explain.
5. **Possible conflict of interest.** Hints in the free-text notes that
   the requester and the supplier may have a personal or pre-existing
   relationship (family, friend, prior employment).
6. **Approval irregularity.** The approver field is empty, the approval
   was granted by someone too junior for the amount, or the approval
   was given suspiciously quickly (a so-called *rubber stamp*).
7. **Quote manipulation.** Only a single quote was considered when
   competitive bidding would have been normal, or there are signs the
   tendering process was steered toward a specific supplier.
8. **Recent bank-account change.** The supplier has recently provided
   new banking or payment details. This pattern matches Business Email
   Compromise (BEC) fraud, where attackers redirect legitimate
   payments to attacker-controlled accounts.

Use this list as a mental checklist when you read each order, but do
not treat any single item as automatic proof of fraud — the company
also has many *normal* orders that may legitimately exhibit one of
these features.

## Your Decisions per Order

For every order you must do **three** things:

1. Pick **Normal** or **Suspicious**.
2. Give a confidence rating from **1 (not confident at all)** to **7
   (extremely confident)**.
3. Type a **short rationale** (one or two sentences) explaining why you
   chose this answer.

## Format and Pacing

- There are **2 practice questions** first. After each practice question
  you will see whether your answer was right or wrong. Use these to get
  used to the layout.
- Then there are **32 official questions**. You will **not** receive
  feedback during the official block.
- Aim for roughly **45 to 75 seconds per official question**. The total
  for the official block should fall around **30 minutes**.
- A simple progress bar at the top of the screen shows how far you are.

## Important Rules

- **You cannot return to a previous question.** Once you click *Submit*
  on an order, the next order loads and the previous one is locked.
  Make sure you are happy with your three answers before clicking.
- **Each submitted answer is recorded immediately** and cannot be
  edited.
- **Do not refresh the page or close the browser tab during the
  experiment.** There is no resume function. If you refresh, your
  session is lost and the researcher will need to invalidate your
  partial data and ask you to re-attempt the study from the beginning.
  Please complete the whole flow in one continuous sitting.
- Please use a **laptop or desktop** with a stable internet connection
  and a browser window at least **1200 pixels wide** (the order layout
  will look cramped on mobile).
- The first time the page loads it may take **5 to 30 seconds** to wake
  up — this is normal.
- Please do **not** discuss the questions or your answers with other
  participants until the study window is closed. Sharing strategies
  would invalidate the data.

## After the 32 Official Questions

If your group includes AI assistance, you will be asked **5 short Likert
questions** about your experience with the AI. The whole survey takes
about 2 minutes.

If your group does not include AI assistance, you will go straight to a
short thank-you page.

## Privacy and Data Use

Your name will be normalised (lowercase, trimmed of spaces) and used
only as your participant identifier. Your answers and timestamps will be
stored in a private Google Sheet that only the researcher can access.
Aggregate results may be reported in the FYP thesis; no individual
participant will be identified by name.

---

**Press *Continue* below when you are ready. The next page will explain
your group-specific instructions.**
