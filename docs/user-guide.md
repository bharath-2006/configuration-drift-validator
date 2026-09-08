# User Guide & Viva Demonstration Walkthrough

This guide provides step-by-step instructions for running, operating, and presenting the **Configuration Drift Validator** during a college project viva or technical demonstration.

---

## 1. Quickstart & Local Setup (Windows Laptop)

### Step 1: Open PowerShell / Terminal
Navigate to the project root directory:
```powershell
cd "c:\coe project"
```

### Step 2: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Automated Tests (Verifying Everything Works)
```powershell
python -m pytest -v
```
*Expected Output:* 20 passed tests in under 1 second.

### Step 4: Run the Benchmark Experiment
```powershell
python experiments/run_experiment.py
```
*Expected Output:* Shows comparison metrics between manual baseline (58.8% accuracy) vs the proposed validator (100% accuracy).

### Step 5: Launch the Web Dashboard
```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Open your web browser and navigate to:
👉 **`http://127.0.0.1:8000`**

*(Interactive Swagger API docs are also available at `http://127.0.0.1:8000/docs`)*

---

## 2. Complete 12-Step Viva Demonstration Scenario

This exact sequence demonstrates the end-to-end capabilities of the project to your college professor or external examiner:

### Step 1: Initial Healthy Baseline
- On the dashboard, click **"Reset Demo"** in the top right to load pristine seed data.
- Click **"Run Drift Validation"**.
- Point out the **Deployment Gate Banner**: It glows **GREEN** with the text:
  > **✅ Production Deployment APPROVED: No blocking configuration drift detected.**
- Show the 3 Environment Health Cards: **Development**, **Staging**, and **Production** all show **Healthy**.
- Explain: Normal differences (e.g. `dev-db` in dev vs `prod-db` in prod) are correctly recognized as **expected variations**, not errors.

### Step 2: Introduce an Intentional Configuration Mistake
- Click on the **"🎓 College Viva Demo Scenarios"** tab.
- Click the button: **"Trigger Scenario 1"** *(Production Points to Dev Database)*.
  *(Alternatively, you can go to the "Configuration Manager" tab, select "Production", change `DATABASE_HOST=dev-db`, and click "Save New Version".)*

### Step 3: Run the Drift Validator
- The dashboard automatically runs validation (or click **"Run Drift Validation"**).

### Step 4: Observe the Critical Detection
- The Deployment Gate instantly shifts to **RED GLOW**:
  > **❌ Production Deployment BLOCKED: 1 Critical configuration discrepancies detected.**
- Switch to the **"🔍 Drift Analysis Results"** tab.
- Show the detected discrepancy table:
  - **Severity:** `CRITICAL`
  - **Environment:** `PRODUCTION`
  - **Key:** `DATABASE_HOST`
  - **Expected:** `prod-db`
  - **Actual:** `dev-db`
  - **Reason:** *"Production DATABASE_HOST points to non-production database ('dev-db'). This will cause production data corruption or data loss in testing environments."*
  - **Fix:** *"Update DATABASE_HOST to point to the secure production database cluster ('prod-db')."*

### Step 5: Test the Simulated Deployment Gate
- Click the **"🚀 Deploy to Production"** button in the top banner.
- An alert modal appears:
  > **⛔ DEPLOYMENT BLOCKED BY SAFETY GATE!**
  > Production deployment is blocked because 1 Critical configuration issue is unresolved.
- Explain to the examiner that this automated gate prevents disastrous outages before containers are even scheduled!

### Step 6: Create a Change Request (Peer Review Workflow)
- Switch to the **"📋 Change Requests"** tab.
- Click **"+ Submit New Change Request"**.
- Fill in:
  - **Environment:** `Production`
  - **Title:** `Fix Production DATABASE_HOST back to prod-db`
  - **Proposed Changes JSON:** `{"variables": {"DATABASE_HOST": "prod-db"}}`
  - **Requester:** `developer`
- Click **"Submit for Review"**.

### Step 7: Reviewer Approves the Correction
- In the Change Requests table, observe Request #1 with status **PENDING** and risk level **HIGH**.
- Click the green **"✓ Approve"** button.
- When prompted for review notes, enter: *"Verified and approved by tech lead"*.
- The backend automatically approves the request AND creates a new configuration version with the corrected database host!

### Step 8: Re-Run Validation
- The dashboard updates automatically and runs validation.

### Step 9: Verify Deployment Unblocked
- Observe the Deployment Gate Banner: It has returned to **GREEN**:
  > **✅ Production Deployment APPROVED: No blocking configuration drift detected.**
- Click **"🚀 Deploy to Production"**: It now displays:
  > **🚀 PRODUCTION DEPLOYMENT APPROVED! Safety Gate Passed.**

### Step 10: Inspect the Tamper-Evident Audit Trail
- Switch to the **"📜 Audit Trail"** tab.
- Show the chronological ledger:
  1. System Reset
  2. Configuration Created / Mistake Injected (Risk: CRITICAL)
  3. Configuration Validation Run
  4. Change Requested (Risk: HIGH)
  5. Change Approved by tech-lead
  6. Configuration Created (New corrected version applied)
  7. Configuration Validation Run (Passed)

### Step 11: Demonstrate Configuration Rollback
- Switch to the **"⏪ Version Rollback"** tab.
- Select Environment: **Production**.
- Notice the version history dropdown showing Version 1, Version 2 (broken), and Version 3 (fixed).
- Select **Version 1**, enter reason: *"Testing emergency rollback procedure"*, and click **"Restore Target Version"**.
- The system immediately restores the exact configuration snapshot of Version 1 and records the rollback in the audit trail.

### Step 12: Demonstrate Edge Cases & Adversarial Resilience
- Go back to **"College Viva Demo Scenarios"** and demonstrate:
  - **Scenario 2:** Production `DEBUG=true` -> Detected as **CRITICAL**.
  - **Scenario 3:** Missing Secret `DATABASE_PASSWORD` -> Detected as **CRITICAL**.
  - **Scenario 4:** Runtime Container Drift (Running container has `LOG_LEVEL=DEBUG` while approved is `INFO`) -> Detected as **HIGH**.
  - **Scenario 5:** Expected Environment-Specific Differences -> Clean pass with 0 false alarms.

---

## 3. How to Demonstrate to Examiners

| Examiner Question | Where to Click / What to Point Out |
| :--- | :--- |
| *"How do you handle secrets safely?"* | Open **Configuration Manager** -> Show `secrets.json`. Explain that only **metadata** (`exists: true`, `source`, `age_days`) is stored. Real passwords never touch the system. |
| *"How does your tool know `dev-db` in Dev is OK, but in Prod is bad?"* | Open `backend/validation_policy.py`. Show `is_expected_difference` and `FORBIDDEN_PROD_INDICATORS`. |
| *"What happens if a developer tries to bypass the UI?"* | Show that the REST API (`POST /api/validate` and `/api/deployment-gate`) can be called directly by CI/CD tools like GitHub Actions or Jenkins. |
| *"How do you know this is better than manual review?"* | Open `docs/experiment.md` or show the terminal output of `python experiments/run_experiment.py`: 100% detection vs 58.8% manual detection with 36 false alarms eliminated. |
