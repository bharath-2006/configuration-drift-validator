# 20 Viva Questions & Student-Friendly Answers

Prepare for your college project examination with these concise, student-friendly answers:

---

### Q1: What is configuration drift?
**Answer:** Configuration drift occurs when an environment's actual configuration (such as environment variables, database hosts, resource limits, or secrets) gradually diverges from the intended, approved configuration baseline, or when differences between staging and production cause unexpected errors.

### Q2: Why does configuration drift happen in real startups?
**Answer:** In fast-moving teams, multiple developers share an overloaded staging environment. Developers frequently tweak settings for local debugging (e.g. enabling `DEBUG=true` or pointing to a test database). These temporary settings often get committed accidentally or carried over into production deployment scripts.

### Q3: Why is testing in Staging insufficient to catch configuration mistakes?
**Answer:** Staging is lenient and often "works" even with dirty configs! For example, if a staging environment points to `dev-db` or has debug mode on, the app still runs and tests pass. But if that same configuration reaches production, real customer data gets corrupted or exposed. Staging tests the code logic, not the safety of production configurations.

### Q4: What is an environment variable?
**Answer:** An environment variable is a dynamic key-value pair stored outside the application source code (in the operating system or container environment). According to the Twelve-Factor App methodology, configurations that vary across environments (like database URLs and API keys) should be stored in environment variables so the same codebase can run anywhere.

### Q5: Why should secrets not be stored directly in your validator's database?
**Answer:** Storing raw passwords or API keys creates a severe security risk and violates privacy compliance. Our validator uses a **"Secret Metadata"** approach: it only checks metadata properties like `exists: true`, `source: secret-manager`, and `age_days: 15`. It verifies that the secret is present and rotated without ever seeing or storing the secret value itself.

### Q6: How does your validator detect drift?
**Answer:** The validator normalizes configurations across Development, Staging, and Production into canonical Python objects. It then runs checks across four layers:
1. Environment-specific policy rules (e.g., `DEBUG` must be `false` in Prod).
2. Forbidden pattern matching (e.g., `dev-db` or `localhost` in Prod).
3. Cross-environment missing keys and infrastructure discrepancies.
4. Runtime snapshot verification (comparing approved config with live container state).

### Q7: How do you distinguish expected differences from errors?
**Answer:** We implemented an **Environment-Aware Validation Policy** (`validation_policy.py`). For example, `DATABASE_HOST` having `dev-db` in dev and `prod-db` in prod is recognized as an *expected difference*. However, if `DATABASE_HOST` in prod points to `dev-db`, the policy engine flags it as a *dangerous drift*.

### Q8: What is a deployment gate?
**Answer:** A deployment gate is an automated checkpoint in a software release pipeline. If our validator detects any **CRITICAL** configuration discrepancy, the deployment gate automatically **BLOCKS** the deployment. Only when all critical issues are resolved is deployment allowed.

### Q9: Why did you use SQLite instead of MySQL or PostgreSQL?
**Answer:** SQLite is lightweight, self-contained, serverless, and requires zero installation. It stores the entire database in a single local `.db` file, making it 100% reliable for demonstration on any college student's laptop without configuring database servers or paying cloud fees.

### Q10: Why did you choose FastAPI over Flask or Django?
**Answer:** FastAPI is modern, fast, and uses Python type hints with Pydantic for automated request/response validation. It also automatically generates interactive Swagger API documentation at `/docs`, which is great for showing API endpoints to examiners during a viva.

### Q11: How does your rollback mechanism work?
**Answer:** Every configuration update creates a new immutable version in the database (Version 1, Version 2, etc.) while marking previous versions inactive. When a rollback is requested (e.g. from Version 3 back to Version 2), the system marks Version 2 active again, loads its exact variables, and records the event in the audit trail.

### Q12: What is the purpose of the Audit Trail?
**Answer:** The audit trail provides a tamper-evident, chronological log of every action: who modified a config, when a validation was run, what issues were found, who approved a change, and when rollbacks occurred. This is essential in production for accountability and post-incident reviews.

### Q13: What are false positives and false negatives?
**Answer:**
- **False Positive (False Alarm):** The tool flags an issue when nothing is actually wrong (e.g. flagging normal database name differences between staging and prod).
- **False Negative (Missed Issue):** The tool fails to detect a real mistake (e.g. missing `DEBUG=true` in production). Our system achieved 0 false positives and 0 false negatives on the benchmark.

### Q14: What are adversarial test cases?
**Answer:** Adversarial test cases are tricky inputs designed to fool naive comparison systems. Examples include using whitespace (`" prod-db "`), different casings (`"TRUE"` vs `true`), numeric strings (`"5432"` vs `5432`), or hiding development hostnames inside long connection URLs (`postgresql://user:pass@dev-db.internal:5432/app`). Our normalizer sanitizes these before comparison.

### Q15: What is runtime container drift?
**Answer:** Runtime drift happens when the running container's environment inside Docker or Kubernetes differs from what is documented in the Git repository (e.g., someone manually edited an environment variable on a running container). Our validator compares container runtime snapshots against approved configs to detect this.

### Q16: What is secret rotation and why is it checked?
**Answer:** Secret rotation is the security practice of periodically changing passwords and API keys (typically every 90 days) to limit the impact of leaked credentials. Our system checks `age_days` in secret metadata and flags a **MEDIUM** severity warning if a secret is older than 90 days.

### Q17: Why did you use Pydantic in the backend?
**Answer:** Pydantic provides data parsing and type validation. It ensures that incoming JSON payloads conform strictly to expected types, preventing runtime errors and crashes from malformed user input.

### Q18: What are the severity levels in your risk engine?
**Answer:**
- **CRITICAL:** Immediate production blockers (e.g. Prod `DEBUG=true`, Prod pointing to dev database, missing prod secret). Blocks deployment.
- **HIGH:** Significant risks (e.g. missing required variable, runtime container drift, disabled health check).
- **MEDIUM:** Compliance or reliability issues (e.g. secret older than 90 days, log level mismatch, insufficient replicas).
- **LOW:** Minor metadata or formatting variances.

### Q19: How would this validator fit into a real-world CI/CD pipeline?
**Answer:** In a real-world pipeline (like GitHub Actions or Jenkins), before executing `kubectl apply` or `docker compose up`, the pipeline would send an HTTP request to `GET /api/deployment-gate`. If `production_deployment_allowed` is `false`, the pipeline immediately aborts and alerts the team.

### Q20: What are the main limitations of your project?
**Answer:** 
1. It currently reads simulated runtime snapshots from JSON files rather than connecting directly to live cloud APIs (like AWS Secrets Manager or Kubernetes API).
2. Validation rules are declared in code rather than through a dynamic visual policy drag-and-drop builder. These are natural areas for future enhancement.
