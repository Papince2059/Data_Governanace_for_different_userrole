"""
Seed Data Script for Enterprise Data Governance System.
Populates PostgreSQL with:
  1. Acme Corporation Organization (tenant)
  2. 4 Departments (HR, Finance, Sales, IT)
  3. Groups and User-Group memberships
  4. 9 Users with bcrypt hashed passwords ('password123')
  5. 24 Detailed synthetic documents with 400+ words of realistic text each
  6. Sentence-Transformers embeddings (384-dim) into pgvector
  7. OpenFGA relationship tuples
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import bcrypt
from sentence_transformers import SentenceTransformer


def _hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


DEFAULT_PASSWORD_HASH = _hash_password("password123")

# Model for local embeddings
EMBEDDER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Organization
ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_ID = str(ORG_ID)

# Departments
DEPT_HR_ID = uuid.UUID("22222222-2222-2222-2222-222222222201")
DEPT_FIN_ID = uuid.UUID("22222222-2222-2222-2222-222222222202")
DEPT_SALES_ID = uuid.UUID("22222222-2222-2222-2222-222222222203")
DEPT_IT_ID = uuid.UUID("22222222-2222-2222-2222-222222222204")

# Users
USERS = [
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333301"),
        "username": "alice",
        "email": "alice@acme.com",
        "full_name": "Alice Smith",
        "role": "member",
        "dept_id": DEPT_HR_ID,
        "title": "HR Analyst",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "username": "helen",
        "email": "helen@acme.com",
        "full_name": "Helen Vance",
        "role": "member",
        "dept_id": DEPT_HR_ID,
        "title": "HR Manager",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333303"),
        "username": "bob",
        "email": "bob@acme.com",
        "full_name": "Bob Miller",
        "role": "member",
        "dept_id": DEPT_FIN_ID,
        "title": "Finance Analyst",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "username": "frank",
        "email": "frank@acme.com",
        "full_name": "Frank Castle",
        "role": "member",
        "dept_id": DEPT_FIN_ID,
        "title": "Finance Manager",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333305"),
        "username": "charlie",
        "email": "charlie@acme.com",
        "full_name": "Charlie Davis",
        "role": "member",
        "dept_id": DEPT_SALES_ID,
        "title": "Sales Executive",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "username": "sara",
        "email": "sara@acme.com",
        "full_name": "Sara Connor",
        "role": "member",
        "dept_id": DEPT_SALES_ID,
        "title": "Sales Manager",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333307"),
        "username": "david",
        "email": "david@acme.com",
        "full_name": "David Bowman",
        "role": "member",
        "dept_id": DEPT_IT_ID,
        "title": "IT Engineer",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333308"),
        "username": "irene",
        "email": "irene@acme.com",
        "full_name": "Irene Adler",
        "role": "member",
        "dept_id": DEPT_IT_ID,
        "title": "IT Administrator",
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333309"),
        "username": "admin",
        "email": "admin@acme.com",
        "full_name": "System Administrator",
        "role": "admin",
        "dept_id": None,
        "title": "Security Administrator",
    },
]

# Groups
GROUPS = [
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444401"), "name": "hr", "slug": "group:hr"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444402"), "name": "hr_managers", "slug": "group:hr_managers"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444403"), "name": "finance", "slug": "group:finance"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444404"), "name": "finance_managers", "slug": "group:finance_managers"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444405"), "name": "sales", "slug": "group:sales"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444406"), "name": "sales_managers", "slug": "group:sales_managers"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444407"), "name": "it", "slug": "group:it"},
    {"id": uuid.UUID("44444444-4444-4444-4444-444444444408"), "name": "it_admins", "slug": "group:it_admins"},
]

# Folders
FOLDERS = [
    {"id": uuid.UUID("55555555-5555-5555-5555-555555555501"), "name": "HR Department", "slug": "folder:folder_hr"},
    {"id": uuid.UUID("55555555-5555-5555-5555-555555555502"), "name": "Finance Department", "slug": "folder:folder_finance"},
    {"id": uuid.UUID("55555555-5555-5555-5555-555555555503"), "name": "Sales Department", "slug": "folder:folder_sales"},
    {"id": uuid.UUID("55555555-5555-5555-5555-555555555504"), "name": "IT Department", "slug": "folder:folder_it"},
    {"id": uuid.UUID("55555555-5555-5555-5555-555555555505"), "name": "Company Policies", "slug": "folder:folder_company"},
]

# Realistic documents with substantial content (>400 words)
DOCUMENTS_SPEC = [
    # --- HR Documents ---
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666601"),
        "key": "doc_employee_handbook",
        "title": "Employee Handbook",
        "dept_id": DEPT_HR_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555501"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "content": """
ACME CORPORATION — OFFICIAL EMPLOYEE HANDBOOK
Revision: 2024.1 | Classification: Internal HR

1. Purpose and Organizational Mission
Acme Corporation is committed to fostering an equitable, collaborative, and results-oriented work environment. 
This Employee Handbook outlines foundational standards, business conduct, workplace ethics, and employee entitlements. 
Every employee across all departments must read, understand, and comply with the provisions set forth herein.

2. Standards of Conduct and Professional Integrity
Employees are expected to exercise professional integrity, respectful communication, and ethical decision-making. 
Harassment, discrimination, or abusive conduct of any nature will not be tolerated. 
Conflicts of interest must be disclosed promptly to the Human Resources department. 
Corporate communication channels must be used responsibly and in alignment with information security policies.

3. Working Hours, Flexibility, and Core Operating Hours
Acme operates on a standard 40-hour workweek with core collaboration hours between 10:00 AM and 4:00 PM local time. 
Flexible working arrangements, including hybrid scheduling and core hour adjustments, require formal written approval from department leadership. 
Time tracking and attendance monitoring must be maintained diligently through the centralized HR portal. 
Overtime eligibility for non-exempt staff must be pre-approved by designated supervisors prior to commencement of work.

4. Comprehensive Compensation and Benefits Overview
Compensation at Acme Corporation includes base salary, annual performance incentive consideration, health benefits, retirement matching, and wellness subsidies. 
Full-time personnel receive comprehensive medical, dental, and vision insurance effective on the first calendar day of the month following 30 days of continuous employment. 
The 401(k) retirement savings plan offers company matching up to 5 percent of eligible salary deferrals, with vesting schedules administered per corporate policy.

5. Workplace Safety, Health, and Environment
Employee safety is paramount. Any workplace hazards, security anomalies, or health concerns must be reported immediately to Facilities and HR. 
Emergency evacuation routes and designated assembly points are posted in all facility common areas. 
The company maintains a smoke-free and substance-free work environment across all office properties.

6. Whistleblower Protection and Grievance Mechanisms
Acme provides confidential, retaliation-free reporting avenues for employees observing violations of law, regulations, or company standards. 
Reports can be submitted anonymously through the compliance hotline or directly to the Human Resources grievance committee.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666602"),
        "key": "doc_leave_policy",
        "title": "Leave and Attendance Policy",
        "dept_id": DEPT_HR_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555501"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "content": """
ACME CORPORATION — LEAVE AND ATTENDANCE POLICY
Effective: 2024 | Document ID: HR-POL-002

1. Scope and Objective
This policy defines the terms, accruals, approval workflows, and administration of employee paid and unpaid leave. 
It applies universally to all full-time and part-time salaried personnel of Acme Corporation.

2. Paid Time Off (PTO) Entitlement and Accruals
Full-time employees accrue Paid Time Off on a bi-weekly payroll cycle basis. 
Employees with 0 to 2 years of tenure accrue 20 days (160 hours) of PTO annually. 
Employees with 3 to 5 years of tenure accrue 25 days (200 hours) annually. 
Employees with over 5 years of tenure accrue 30 days (240 hours) annually. 
A maximum of 5 unused PTO days may roll over into the following calendar year, and must be utilized before March 31st of that subsequent year.

3. Request and Advance Notice Procedures
All planned leave requests exceeding two consecutive business days must be logged in the HR information system at least two weeks in advance. 
Supervisors are required to review and respond to submitted leave requests within three business days. 
In instances of emergency absence, employees must notify their immediate supervisor via email or phone no later than two hours prior to their scheduled start time.

4. Medical and Sick Leave Provisions
Employees receive 10 dedicated sick leave days per year separate from standard PTO. 
For medical absences exceeding three consecutive working days, an official medical practitioner certificate verifying fitness for duty must be submitted to HR. 
Sick leave may also be utilized to provide direct care for immediate family members requiring medical attention.

5. Parental and Family Care Leave
Acme provides 16 weeks of fully paid parental leave to eligible primary caregivers following the birth, adoption, or foster placement of a child. 
Secondary caregivers are entitled to 8 weeks of paid leave. Parental leave may be taken continuously or in structured blocks within the first 12 months.

6. Bereavement and Compassionate Absence
Up to 5 paid business days are granted for the loss of an immediate family member (spouse, child, parent, sibling). 
Up to 3 paid business days are provided for extended family members. Additional unpaid leave may be granted upon request to HR leadership.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666603"),
        "key": "doc_salary_records",
        "title": "Employee Salary Records — CONFIDENTIAL",
        "dept_id": DEPT_HR_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555501"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "content": """
CONFIDENTIAL — ACME CORPORATION EXECUTIVE SALARY BENCHMARKING & PAYROLL DATA
Classification: RESTRICTED — HR MANAGERS ONLY | Document: HR-SAL-2024-CONF

1. Compensation Governance and Pay Equity Analysis
This document contains sensitive synthetic compensation data, salary band brackets, and executive compensation guidelines. 
Access is strictly restricted to HR Managers and executive compensation committee members under OpenFGA ReBAC policy. 
Unauthorized access, distribution, or copying constitutes a major security and governance violation.

2. Departmental Salary Bands (Annual Synthetic Base Pay Ranges)
- Executive Band E1: $180,000 to $250,000 | Target Incentive: 35%
- Management Band M2: $120,000 to $165,000 | Target Incentive: 20%
- Senior Professional P3: $95,000 to $130,000 | Target Incentive: 15%
- Professional Band P2: $70,000 to $95,000 | Target Incentive: 10%
- Entry Professional P1: $55,000 to $70,000 | Target Incentive: 5%

3. Departmental Payroll Audit Summary
- Human Resources (Analyst Level P2): Base $72,500. Manager Level M2: Base $135,000. Total departmental payroll: $415,000.
- Finance Department (Analyst Level P2): Base $76,000. Manager Level M2: Base $142,000. Total departmental payroll: $580,000.
- Sales Department (Executive Level P2): Base $68,000 + Commissions. Manager Level M2: Base $130,000 + Override. Total: $690,000.
- Information Technology (Engineer Level P3): Base $105,000. Admin Level M2: Base $140,000. Total departmental payroll: $785,000.

4. Annual Merit Review Multipliers
Annual merit adjustments range between 2.0% for satisfactory performance to 8.5% for top-tier contributors exceeding strategic milestones. 
Promotional increases are capped at 15% without prior written authorization from the Chief People Officer. 
Discretionary equity grants vest over a standard 4-year schedule with a 1-year cliff.

5. Retention and Bonus Accruals
Special retention bonuses allocated for mission-critical engineering and finance leadership roles total $125,000 for the current fiscal cycle. 
All incentive payouts are contingent upon achieving corporate revenue thresholds and individual performance review ratings.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666604"),
        "key": "doc_performance_guidelines",
        "title": "Performance Review Guidelines",
        "dept_id": DEPT_HR_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555501"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "content": """
ACME CORPORATION — PERFORMANCE EVALUATION AND REVIEW GUIDELINES
Human Resources Operational Document | Reference: HR-PERF-004

1. Performance Management Philosophy
At Acme Corporation, performance evaluation is a continuous, transparent, and bidirectional process. 
These guidelines define the annual and mid-year review milestones, scoring rubrics, competency expectations, and improvement planning frameworks.

2. Annual Evaluation Cycle Milestones
The corporate evaluation cadence consists of four structured phases:
- Phase 1 (Q1 Goal Setting): Employees establish quarterly OKRs (Objectives and Key Results) aligned with strategic business targets.
- Phase 2 (Q2 Mid-Year Checkpoint): Formal mid-cycle check-in between employee and manager to calibrate goal progression and career development.
- Phase 3 (Q3 Self and Peer 360 Feedback): Employees complete self-evaluations and invite 3-5 colleagues to submit peer reviews.
- Phase 4 (Q4 Year-End Assessment): Managers assign final ratings, review merit allocations, and conduct compensation discussions.

3. Five-Tier Rating Rubric
- Rating 5 (Role Model / Exceeds All Expectations): Consistently delivers transformational business impact and mentors others.
- Rating 4 (Exceeds Expectations): Frequently surpasses OKR milestones and demonstrates initiative beyond core responsibilities.
- Rating 3 (Consistently Meets Expectations): Fulfills all job duties reliably and achieves anticipated performance benchmarks.
- Rating 2 (Needs Improvement): Does not consistently meet minimum standards in one or more core competency areas.
- Rating 1 (Unsatisfactory): Significant performance deficits requiring immediate intervention.

4. Performance Improvement Plans (PIP)
Employees receiving a Rating 2 or demonstrating sustained performance issues will be placed on a structured 60-day Performance Improvement Plan. 
The PIP specifies measurable milestones, bi-weekly check-ins, and clear success criteria developed collaboratively between HR and the manager.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666605"),
        "key": "doc_onboarding_policy",
        "title": "Employee Onboarding Policy",
        "dept_id": DEPT_HR_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555501"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "content": """
ACME CORPORATION — EMPLOYEE ONBOARDING AND INTEGRATION POLICY
Document Reference: HR-ONB-005 | Audience: All Staff

1. Onboarding Framework and Mission
A seamless, structured onboarding experience is vital to employee engagement, cultural alignment, and rapid time-to-productivity. 
This policy establishes standard operating procedures for welcoming, provisioning, and integrating newly hired personnel across all departments.

2. Pre-Arrival Provisioning and Coordination
Upon contract execution, HR coordinates with IT to initiate hardware and access provisioning at least 7 business days prior to start date:
- Hardware Allocation: IT configures standard laptop hardware, monitors, peripherals, and security tokens.
- Identity and Access Management: Single Sign-On (SSO) accounts and preliminary OpenFGA group memberships are generated according to job family.
- Welcome Kit: Corporate handbook, welcome materials, and logistical guidelines are dispatched to the new employee.

3. Week One Orientation Curriculum
- Day 1: Corporate mission overview, benefits enrollment walkthrough, Form I-9 verification, and IT security onboarding.
- Day 2: Department overview, meet the leadership team, assign an onboarding buddy, and configure development/productivity tools.
- Day 3-5: Deep dive into departmental workflows, compliance training modules, data governance policies, and initial 30-day goals.

4. The 30-60-90 Day Milestone Check-in Program
- 30-Day Check-in: Review role clarity, assess tooling comfort, evaluate buddy relationship, and confirm all compliance courses completed.
- 60-Day Check-in: Evaluate initial deliverable contributions, discuss cultural integration, and calibrate preliminary performance.
- 90-Day Transition: Formal completion of onboarding period, setting of full quarterly OKRs, and transition to regular performance cadence.
""",
    },

    # --- Finance Documents ---
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666606"),
        "key": "doc_financial_statements",
        "title": "Financial Statements",
        "dept_id": DEPT_FIN_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555502"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "content": """
ACME CORPORATION — ANNUAL FINANCIAL STATEMENTS
Consolidated Fiscal Year 2024 Audit | Synthetic Accounting Ledger

1. Statement of Comprehensive Income
Acme Corporation generated total consolidated net revenue of $48,250,000 for the fiscal year ended December 31, 2024, 
representing an annualized growth rate of 14.8% compared to fiscal year 2023. 
Cost of goods sold (COGS) totaled $16,887,500, yielding a gross profit of $31,362,500 and a consolidated gross margin of 65.0%.
Operating expenses included Research and Development ($12,450,000), Sales and Marketing ($10,120,000), 
and General & Administrative ($4,200,000). Operating income reached $4,592,500.

2. Consolidated Balance Sheet Overview
- Total Current Assets: $28,450,000, including cash and cash equivalents of $14,200,000 and accounts receivable of $8,750,000.
- Non-Current Assets: Property, plant, and equipment net of depreciation totals $6,800,000. Capitalized software and intangible assets total $9,150,000.
- Total Liabilities: Current liabilities stand at $9,400,000, primarily accounts payable and accrued payroll obligations. Long-term debt remains low at $2,500,000.
- Stockholders Equity: Retained earnings total $18,300,000 with additional paid-in capital of $14,200,000.

3. Statement of Cash Flows
Net cash provided by operating activities totaled $6,840,000. 
Capital expenditures for cloud infrastructure and technological tooling were $2,100,000. 
Financing activities included debt service of $800,000 and share repurchases of $1,200,000. Free cash flow for the year stood at $4,740,000.

4. Auditor Opinion and Internal Controls
Independent auditors have issued an unqualified clean audit opinion. 
Internal controls over financial reporting adhere to standard GAAP principles with no material weaknesses identified.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666607"),
        "key": "doc_quarterly_revenue",
        "title": "Quarterly Revenue Report",
        "dept_id": DEPT_FIN_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555502"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "content": """
ACME CORPORATION — Q3 2024 QUARTERLY REVENUE AND METRICS REPORT
Finance Department Analytical Summary | Reference: FIN-REV-Q3-2024

1. Executive Revenue Summary
Acme Corporation achieved quarterly net revenue of $13,420,000 in the third quarter of 2024, 
surpassing consensus guidance of $12,800,000 by 4.8%. 
This represents year-over-year revenue growth of 16.2% compared to Q3 2023 ($11,550,000).

2. Segment Breakdown and Recurring Revenue
- Enterprise SaaS Subscription Revenue: $9,650,000 (71.9% of total revenue), displaying annual recurring revenue (ARR) momentum of $38.6M.
- Professional Services & Implementation: $2,420,000 (18.0% of total revenue), reflecting strong onboarding of enterprise accounts.
- Platform Usage and API Metering: $1,350,000 (10.1% of total revenue), driven by increased consumption of AI inference and governance APIs.

3. Customer Acquisition and Retention Metrics
Net Revenue Retention (NRR) reached 118% across enterprise accounts, demonstrating healthy expansion within existing clients. 
Customer Churn remained below target at 0.8% monthly. Gross retention rate stood at 96.4%. 
The sales team added 42 new mid-market customers and 6 Fortune 500 enterprise accounts during the quarter.

4. Regional Performance Highlights
- North America: $8,720,000 (65.0% of total revenue) — grew 14% YoY.
- EMEA (Europe, Middle East, Africa): $3,490,000 (26.0% of total revenue) — grew 21% YoY.
- APAC (Asia-Pacific): $1,210,000 (9.0% of total revenue) — grew 24% YoY.

5. Profitability and Margins
Gross margin for Q3 expanded 180 basis points to 66.8%, driven by efficiencies in cloud hosting and optimized vector storage indexing. 
Adjusted EBITDA reached $2,150,000 (16.0% EBITDA margin).
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666608"),
        "key": "doc_department_budget",
        "title": "Department Budget",
        "dept_id": DEPT_FIN_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555502"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "content": """
ACME CORPORATION — FISCAL YEAR 2024 OPERATING DEPARTMENT BUDGETS
Financial Planning and Analysis (FP&A) | Reference: FIN-BDG-2024

1. Annual Budget Allocation Overview
The approved operational expenditure (OpEx) budget for Acme Corporation for FY 2024 is $26,770,000. 
This document outlines allocations across Human Resources, Finance, Sales, and Information Technology.

2. Human Resources Budget Allocation ($1,850,000 total)
- Personnel & Benefits Administration: $1,150,000
- Talent Acquisition and Executive Search: $320,000
- Learning, Development, and Leadership Training: $180,000
- HR Tech Stack (Workday, Lattice, Culture Amp): $120,000
- Employee Wellness and Culture Programs: $80,000

3. Finance Department Budget Allocation ($1,620,000 total)
- Accounting and Financial Reporting Team: $950,000
- External Audit and Tax Compliance: $310,000
- Enterprise ERP and Accounting Software (NetSuite): $210,000
- Banking and Merchant Transaction Processing: $90,000
- Treasury and Financial Planning Tools: $60,000

4. Sales Department Budget Allocation ($11,200,000 total)
- Sales Force Base Salaries & Commissions: $7,400,000
- Demand Generation, Events, and Conferences: $2,100,000
- Sales Enablement, Gong, Salesforce CRM Tooling: $950,000
- Client Travel and Executive Briefing Center: $750,000

5. Information Technology & Engineering Budget ($12,100,000 total)
- Core Infrastructure & Cloud Hosting (AWS, PostgreSQL, OpenFGA): $4,200,000
- Engineering and IT Staffing: $5,800,000
- Cybersecurity Tooling, SOC2 Compliance, Penetration Testing: $1,100,000
- Hardware Procurement, Workstations, and Helpdesk: $650,000
- SaaS Licenses and Enterprise Productivity Tools: $350,000
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666609"),
        "key": "doc_payroll_reconciliation",
        "title": "Payroll Reconciliation",
        "dept_id": DEPT_FIN_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555502"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "content": """
ACME CORPORATION — MONTHLY PAYROLL RECONCILIATION REPORT
Classification: RESTRICTED — FINANCE MANAGERS ONLY | Ref: FIN-PAY-2024-M09

1. Purpose and Reconciliation Scope
This report documents the monthly reconciliation between the general ledger and payroll processing registers for September 2024. 
Due to confidential employee compensation entries, access is restricted strictly to Finance Managers under OpenFGA policy.

2. Summary of Gross and Net Disbursements
- Total Gross Wages: $2,475,320.15
- Federal and State Income Tax Withholdings: $544,570.43
- FICA and Medicare Taxes: $189,362.00
- Employee Benefit Deductions (Medical/Dental): $123,766.00
- 401(k) Employee Voluntary Contributions: $173,272.41
- Company 401(k) Match Liability: $86,636.21
- Total Net Direct Deposit Disbursed: $1,444,349.31

3. Departmental Variance Analysis
- IT Department: Actual vs. Budget variance was +$12,400 due to on-call incident response differentials during database maintenance.
- Sales Department: Actual vs. Budget variance was -$35,200 due to deferred commission milestones scheduled for Q4 settlement.
- HR and Finance: Variances were under 1.2%, well within standard operating tolerances.

4. Tax Remittance and Statutory Filing Verification
All statutory federal, state, and local payroll taxes were remitted via electronic funds transfer (EFTPS) on schedule. 
Quarterly Form 941 filings have been compiled and verified with external tax counsel.

5. Sign-off and Authorization
Frank Castle, Finance Manager, verified and signed off on general ledger balance tie-outs on October 2, 2024.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666610"),
        "key": "doc_financial_forecast",
        "title": "Confidential Financial Forecast",
        "dept_id": DEPT_FIN_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555502"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "content": """
CONFIDENTIAL — ACME CORPORATION 3-YEAR STRATEGIC FINANCIAL FORECAST
Classification: HIGHLY RESTRICTED — FINANCE MANAGERS & C-SUITE | Ref: FIN-FST-2025-2027

1. Long-Term Strategic Modeling Assumptions
This document presents the strategic multi-year financial projection model for Acme Corporation spanning 2025 through 2027. 
Projections assume continued enterprise expansion of our AI data governance platform, maintaining gross margins above 68% 
and achieving sustained free cash flow positivity by Q2 2025.

2. Revenue Projections (Base Case Scenario)
- Fiscal Year 2025: Projected revenue of $62,500,000 (growth rate of 29.5%). ARR target: $54,000,000.
- Fiscal Year 2026: Projected revenue of $84,000,000 (growth rate of 34.4%). ARR target: $76,000,000.
- Fiscal Year 2027: Projected revenue of $115,000,000 (growth rate of 36.9%). ARR target: $105,000,000.

3. Capital Requirements and Debt Strategy
To support the anticipated expansion into European public sector markets, Acme projects a Series C funding round or mezzanine debt facility 
of $25,000,000 in early 2026. Debt service coverage ratio is anticipated to remain robust at 4.2x under all modeled interest rate environments.

4. Profitability Trajectory
Operating margin is modeled to expand from 9.5% in 2024 to 18.2% by 2027, driven by cloud cost optimization, automated data governance operations, 
and sales efficiency gains. Projected net income for 2027 reaches $18,400,000.

5. Risk Factors and Sensitivity Testing
Stress testing includes scenarios with 20% deceleration in enterprise tech spending, cloud hosting cost inflation of 15%, 
and currency headwinds across EMEA operations. In the downside scenario, Acme retains a minimum cash runway of 22 months without additional external capital.
""",
    },

    # --- Sales Documents ---
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666611"),
        "key": "doc_customer_information",
        "title": "Customer Information",
        "dept_id": DEPT_SALES_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555503"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "content": """
ACME CORPORATION — ENTERPRISE CUSTOMER INFORMATION DIRECTORY
Sales Operations & Account Management | Reference: SLS-CUST-2024

1. Overview of Key Enterprise Accounts
Acme Corporation serves over 350 enterprise clients globally across financial services, healthcare, telecommunications, and government sectors. 
This directory provides non-confidential customer metadata, industry classification, service tier, and primary account contacts.

2. Major Account Profiles
- Apex Financial Services: Global investment bank utilizing Acme for data compliance and Zanzibar-based authorization governance. 
  Contract ARR: $420,000. Renewal Date: November 2025. Contact: VP of Enterprise Architecture.
- BioHealth Laboratories: Clinical research organization deploying Acme Data Governance for HIPAA and clinical trial record retrieval. 
  Contract ARR: $280,000. Renewal Date: March 2025. Contact: Chief Information Security Officer.
- Global Logistics Corp: International supply chain enterprise utilizing pgvector semantic search and document classification. 
  Contract ARR: $195,000. Renewal Date: August 2025. Contact: Director of IT Infrastructure.
- Stellar Cloud Systems: Multi-tenant SaaS provider embedding Acme pre-retrieval ACL filtering within their AI customer portal. 
  Contract ARR: $510,000. Renewal Date: January 2026. Contact: Head of Product Engineering.

3. Customer Success and Health Scoring
Account health scores are evaluated weekly using telemetry metrics: API check latency, vector search volume, user login frequency, and support ticket severity. 
92% of enterprise customers currently maintain a 'Green' health rating with average NPS (Net Promoter Score) standing at +58.

4. Account Management Guidelines
Account managers must conduct quarterly executive business reviews (EBRs) with accounts generating over $100,000 in ARR. 
All customer correspondence and contract amendments must be archived in Salesforce CRM in accordance with data governance policies.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666612"),
        "key": "doc_sales_pipeline",
        "title": "Sales Pipeline Report",
        "dept_id": DEPT_SALES_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555503"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "content": """
ACME CORPORATION — SALES PIPELINE REPORT Q4 2024
Sales Strategy and Pipeline Velocity | Reference: SLS-PIPE-Q4-2024

1. Pipeline Health and Stage Breakdown
The qualified sales pipeline for Q4 2024 stands at $18,450,000 in total contract value across 74 active enterprise opportunities. 
Weighted pipeline forecast indicates $4,280,000 in anticipated Q4 new ARR bookings with an average deal size of $85,000.

2. Funnel Progression by Deal Stage
- Stage 1 (Qualification / Discovery): 28 deals valued at $5,200,000. Average duration in stage: 14 days. Conversion to Stage 2: 65%.
- Stage 2 (Technical Evaluation & POC): 22 deals valued at $6,800,000. Prospects currently testing OpenFGA integration and pgvector retrieval speed.
- Stage 3 (Security & Compliance Review): 14 deals valued at $4,100,000. Legal and CISO teams reviewing SOC2 Type II reports and Zanzibar model specs.
- Stage 4 (Contract Negotiation & Legal): 10 deals valued at $2,350,000. Redlines in progress with targeted execution before December 15.

3. Top 3 Strategic Opportunities
- Opportunity A (National Healthcare Network): 5-year enterprise data governance deployment across 22 regional medical centers. TCV: $1,400,000.
- Opportunity B (Multinational Telecommunications): Core Zanzibar authorization engine for customer-facing AI agents. TCV: $950,000.
- Opportunity C (FinTech Payment Gateway): High-throughput pre-retrieval filtering for compliance audit logs. TCV: $680,000.

4. Sales Velocity and Win Rates
Average sales cycle duration from initial discovery to contract execution is currently 68 days. 
Competitive win rate against legacy RBAC and static metadata solutions stands at 73%, driven by our low-latency OpenFGA pre-retrieval filtering architecture.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666613"),
        "key": "doc_quarterly_sales",
        "title": "Quarterly Sales Performance",
        "dept_id": DEPT_SALES_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555503"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "content": """
ACME CORPORATION — Q3 2024 SALES PERFORMANCE REVIEW
Sales Operations Analytics | Reference: SLS-Q3-PERF

1. Executive Performance Summary
The sales organization achieved 106% of its Q3 quota, closing $3,850,000 in new Annual Recurring Revenue (ARR). 
This represents an acceleration of 22% quarter-over-quarter. Strong execution in the mid-enterprise tier offset delayed procurement cycles in the government sector.

2. Rep Leaderboard and Quota Attainment
- Charlie Davis (Senior Sales Executive): 118% quota attainment ($825,000 closed). Recognized as Top Commercial Performer for closing BioHealth expansion.
- Regional Team West: 112% team attainment.
- Regional Team East: 104% team attainment.
- EMEA Strategic Team: 98% team attainment, facing extended European summer holiday delays in enterprise legal reviews.

3. Deal Metrics and Contract Characteristics
- Average Contract Duration: 2.4 years, with 68% of enterprise clients electing multi-year agreements with annual upfront billing.
- Professional Services Attach Rate: 42% of software deals included packaged implementation and authorization graph migration services.
- Discounting Discipline: Average software discount was kept under 8.2%, down from 11.5% in the preceding quarter.

4. Q4 Go-to-Market Priorities
For the final quarter, sales will emphasize two strategic campaigns:
- 'Zero-Trust AI RAG': Positioning our Zanzibar pre-retrieval filtering system against vulnerable post-filtering vector retrieval architectures.
- 'Compliance-in-a-Box': Bundled packages targeting HIPAA and SOC2 regulated entities preparing for upcoming annual audits.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666614"),
        "key": "doc_pricing_strategy",
        "title": "Product Pricing Strategy",
        "dept_id": DEPT_SALES_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555503"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "content": """
ACME CORPORATION — PRODUCT PRICING & COMMERCIAL PACKAGING STRATEGY
Classification: RESTRICTED — SALES MANAGERS ONLY | Ref: SLS-PRC-2024-CONF

1. Commercial Architecture and Strategic Intent
This document details proprietary commercial packaging, pricing tiers, volume discount curves, and contract negotiation thresholds. 
Access is restricted strictly to Sales Managers and commercial deal desk staff under OpenFGA policy.

2. Core Commercial Licensing Tiers
- Starter Edition ($18,000 / year): Up to 50,000 documents, single tenant, standard RBAC models, community support.
- Professional Edition ($48,000 / year): Up to 500,000 documents, multi-department ReBAC, OpenFGA engine, 99.9% uptime SLA.
- Enterprise Core ($95,000 / year): Up to 2,500,000 documents, Zanzibar graph modeling, pre-retrieval vector filtering, dedicated technical account manager.
- Enterprise Ultimate ($180,000+ / year): Unlimited document scaling, multi-region clustering, custom OpenFGA stores, on-premise deployment option.

3. Consumption and Usage Surcharges
- Vector Embedding Query Volume: Included allocation of 500,000 semantic queries per month. Overages billed at $0.005 per query.
- Document Ingestion Burst Rate: Standard allowance of 25,000 document ingestions per month. Overage pool billed at $0.02 per processed document.

4. Non-Standard Terms and Discount Approval Matrix
- Discounts 0% to 10%: Account Executives have discretionary authority.
- Discounts 10.1% to 20%: Requires written approval from Sales Manager (Sara Connor).
- Discounts 20.1% to 30%: Requires approval from Vice President of Sales and CFO.
- Discounts exceeding 30%: Strictly prohibited without Chief Executive Officer exception sign-off.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666615"),
        "key": "doc_sales_forecast",
        "title": "Sales Forecast",
        "dept_id": DEPT_SALES_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555503"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "content": """
ACME CORPORATION — 12-MONTH ROLLING SALES FORECAST
Classification: RESTRICTED — SALES MANAGERS ONLY | Ref: SLS-FST-2025-CONF

1. Executive Forecast Summary
This rolling 12-month commercial forecast outlines projected sales bookings, pipeline generation requirements, and quota capacity across 2025. 
The commercial target for FY 2025 is established at $18,200,000 in net-new ARR bookings.

2. Quarterly Bookings Targets
- Q1 2025: $3,600,000 (Historical seasonal low, focusing on pipeline creation and enterprise renewal consolidations).
- Q2 2025: $4,200,000 (Expansion in mid-market tier and initial European public sector rollouts).
- Q3 2025: $4,600,000 (Major enterprise procurement cycle closes).
- Q4 2025: $5,800,000 (Year-end budget flushes and multi-year contract renewals).

3. Headcount Capacity and Quota Coverage
Achieving the $18.2M target requires a fully ramped sales team of 24 Account Executives with individual annual quotas of $850,000. 
Current headcount stands at 16 Account Executives; the hiring plan calls for onboarding 4 additional reps in Q1 and 4 in Q2. 
Pipeline coverage ratio must be maintained at a minimum of 3.8x across all active sales territories.

4. Competitive Threats and Market Headwinds
Primary competitive dynamics include incumbent search platforms attempting to bolt on simplistic metadata filters, 
and open-source vector databases without relationship-based authorization models. 
Our strategic moat resides in native OpenFGA Zanzibar relationship graphs integrated with pgvector HNSW indexing.
""",
    },

    # --- IT Documents ---
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666616"),
        "key": "doc_infrastructure_arch",
        "title": "Infrastructure Architecture",
        "dept_id": DEPT_IT_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555504"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333308"),
        "content": """
ACME CORPORATION — SYSTEM INFRASTRUCTURE ARCHITECTURE SPECIFICATION
IT Engineering Document | Architecture Design Record ADR-001 | Status: Active

1. Architecture Vision and Core Principles
The Acme Enterprise Data Governance platform provides real-time, permission-aware document retrieval and conversational AI. 
The system architecture prioritizes zero-trust authorization, local data sovereignty, modular extensibility, and fail-closed security. 
No data is ever transferred to cloud endpoints without explicit cryptographic authorization.

2. Component Overview
- Application Layer: FastAPI (Python 3.12+) running with Uvicorn ASGI workers. Provides asynchronous REST APIs and Server-Sent Events (SSE).
- Authorization Engine: OpenFGA running as a dedicated local service on port 8080. Evaluates Zanzibar relationship graphs with sub-10ms response times.
- Relational and Vector Datastore: PostgreSQL 16 equipped with the pgvector extension. 
  Maintains two logically distinct databases: governance_db (application data, embeddings) and openfga_db (Zanzibar tuple store).
- Embedding Engine: sentence-transformers/all-MiniLM-L6-v2 running locally in-process. Generates 384-dimensional dense vectors.
- Large Language Model: Adapter interface supporting local Ollama (llama3.2) or deterministic mock inference for headless testing.
- Client Frontend: React 18 with TypeScript and Tailwind CSS served via Vite / Nginx.

3. Network Topology and Container Segregation
All services operate within an isolated Docker bridge network (edg_network). 
Host ports are mapped strictly for external management (PostgreSQL 5432, OpenFGA 8080, FastAPI 8000, Frontend 5173). 
Inter-service communication utilizes container DNS resolution with persistent volume mounts for database data.

4. High Availability and Scaling Strategy
In production environments, the PostgreSQL database is deployed with streaming replication and pgvector HNSW indexing. 
OpenFGA instances scale horizontally behind an Envoy load balancer, sharing the underlying openfga_db PostgreSQL relationship store.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666617"),
        "key": "doc_server_runbook",
        "title": "Server Maintenance Runbook",
        "dept_id": DEPT_IT_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555504"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333308"),
        "content": """
ACME CORPORATION — STANDARD SERVER MAINTENANCE RUNBOOK
IT Operations Procedure | Reference: IT-OPS-RUN-002

1. Scope and Objective
This runbook provides step-by-step operational instructions for executing routine maintenance, updates, 
database backups, and emergency recovery procedures for Acme local infrastructure servers.

2. Routine Weekly Maintenance Checklist
- Container Health Verification: Execute 'docker compose ps' and ensure all containers report 'healthy'.
- Disk Space Inspection: Verify that volume mount filesystems have greater than 25% available free capacity.
- Log Rotation: Review application logs in /app/logs; ensure rotated archives are compressed and purged after 30 days.
- Database Connection Pool: Check active asyncpg connections against maximum pool limits in governance_db.

3. Backup and Disaster Recovery Procedure
- Automated Daily Backup: A cron job executes pg_dump on governance_db and openfga_db every evening at 02:00 UTC.
- Manual Backup Command: Run 'docker exec edg_postgres pg_dump -U governance_user governance_db > backup.sql'.
- Restoration Verification: Test restorations into an ephemeral test database container monthly to verify dump integrity.

4. Patching and Container Image Updates
Prior to updating production images:
- Verify staging tests pass with: 'pytest tests/'
- Pull updated images: 'docker compose pull'
- Perform rolling restarts of backend and openfga containers while monitoring health endpoints at /health/ready.

5. Emergency Escalation Contacts
For critical outages impacting OpenFGA authorization checks or database availability, 
notify the on-call engineer (David Bowman) and IT Administrator (Irene Adler) via the internal pager alert system.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666618"),
        "key": "doc_access_policy",
        "title": "System Access Policy",
        "dept_id": DEPT_IT_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555504"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333308"),
        "content": """
ACME CORPORATION — ENTERPRISE SYSTEM ACCESS AND AUTHENTICATION POLICY
IT Security Policy | Document: IT-SEC-POL-003 | Compliance: SOC2 / ISO 27001

1. Purpose and Security Scope
This policy mandates technical controls, credential standards, and authorization protocols across all Acme computing environments. 
All employees, contractors, and administrative staff must adhere strictly to these standards.

2. Principle of Least Privilege
System access is granted exclusively on a need-to-know basis according to defined job responsibilities. 
In our Zanzibar-based architecture, permissions are enforced through OpenFGA relationship graphs rather than broad, coarse-grained roles. 
Direct administrative access to production databases or server shells requires formal justification and multi-party approval.

3. Credential Standards and Multi-Factor Authentication
- Password Complexity: Passwords must contain a minimum of 12 characters, including uppercase, lowercase, numbers, and symbols.
- Passwords are cryptographically hashed using bcrypt with an adaptive work factor.
- Multi-Factor Authentication (MFA): Mandatory for all administrative accounts and remote access connections.
- Session Expiration: JWT access tokens expire after 60 minutes. Refresh tokens expire after 7 days.

4. Account Lifecycle and Deprovisioning
- Immediate Revocation: Upon notice of employee termination, HR and IT trigger automated deprovisioning scripts. 
  OpenFGA user relationship tuples are deleted immediately, rendering all subsequent document queries unauthorized in real time.
- Inactive Accounts: Accounts with no recorded activity for 60 consecutive days are automatically suspended.

5. Audit Logging and Security Monitoring
Every authentication attempt (success and failure), permission check, grant, and revocation is written to an immutable 
authorization_audit_logs table in PostgreSQL. Audit records are retained for a minimum of 365 days for regulatory inspection.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666619"),
        "key": "doc_security_incidents",
        "title": "Security Incident Reports",
        "dept_id": DEPT_IT_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555504"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333308"),
        "content": """
CONFIDENTIAL — ACME CORPORATION SECURITY INCIDENT REPORTS & POST-MORTEMS
Classification: RESTRICTED — IT ADMINISTRATORS ONLY | Ref: IT-SEC-INC-2024-CONF

1. Document Classification and Restrictive Handling
This document contains detailed forensic reports, vulnerability analyses, and remediation post-mortems. 
Access is restricted strictly to IT Administrators under OpenFGA Zanzibar relationship rules. 
Unauthorized viewing constitutes a severe security breach.

2. Incident Record: INC-2024-082 (Simulated Authorization Bypass Test)
- Date: August 14, 2024 | Severity: Critical (Test Environment)
- Summary: Red team security audit evaluated potential post-retrieval vector filtering vulnerabilities in legacy search prototypes.
- Forensic Finding: In vulnerable architectures where vector search runs first and ACL checks occur second, 
  unauthorized document titles and similarity scores could leak in log traces and response headers. 
  Furthermore, highly selective access queries silently produced empty retrieval results due to top-k truncation.
- Remediation: Implemented Zanzibar-based Pre-Retrieval ACL Filtering using OpenFGA ListObjects. 
  The authorized document IDs are now passed directly into the PostgreSQL WHERE clause before vector cosine distance computation, 
  completely mitigating leakage vectors.

3. Incident Record: INC-2024-051 (Failed Credential Stuffing Attempt)
- Date: May 22, 2024 | Severity: Medium
- Summary: External IP range attempted 4,500 automated login requests against the /api/v1/auth/login endpoint over a 20-minute window.
- System Response: Rate limiting triggered automatically after 10 attempts per minute per IP. 
  All attempts were logged in authorization_audit_logs with LOGIN_FAILED status. Zero accounts were compromised.

4. Continuous Remediation and Hardening
All perimeter endpoints require strict Pydantic input validation, parameterized SQL statements, 
and automated fail-closed behavior if OpenFGA becomes unreachable.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666620"),
        "key": "doc_database_docs",
        "title": "Database Documentation",
        "dept_id": DEPT_IT_ID,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555504"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333308"),
        "content": """
ACME CORPORATION — TECHNICAL DATABASE ARCHITECTURE AND SCHEMA DOCUMENTATION
Classification: RESTRICTED — IT ADMINISTRATORS ONLY | Ref: IT-DBA-DOC-005

1. Database Architecture Overview
The platform utilizes a unified PostgreSQL 16 engine hosting two distinct logical databases:
- governance_db: Stores relational application entities, document chunk text, and 384-dimensional pgvector embeddings.
- openfga_db: Serves as the high-throughput datastore for the OpenFGA authorization engine, persisting Zanzibar relationship tuples.

2. pgvector Optimization and HNSW Index Configuration
The document_embeddings table stores chunk embeddings using the vector(384) data type. 
To achieve sub-5ms approximate nearest neighbor search over large collections, an HNSW (Hierarchical Navigable Small World) index is deployed:
  CREATE INDEX ix_document_embeddings_embedding_hnsw
  ON document_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
During active retrieval queries, the session parameter hnsw.ef_search is dynamically set to 100 to optimize the recall-latency Pareto frontier.

3. Pre-Retrieval SQL Filtering Query Structure
Semantic vector search queries enforce tenant isolation and authorized document filtering in the primary CTE:
  SELECT dc.id, dc.content, 1 - (de.embedding <=> :query_vec) AS similarity
  FROM document_embeddings de
  JOIN document_chunks dc ON de.chunk_id = dc.id
  JOIN documents d ON dc.document_id = d.id
  WHERE d.id = ANY(:authorized_doc_ids)
    AND d.tenant_id = :tenant_id
    AND d.status = 'active';
This structure prevents the query planner from examining unauthorized chunks, enforcing zero data leakage.

4. Database Migrations and Version Control
All schema changes are tracked and executed via Alembic async migrations. 
UUID primary keys use uuid_generate_v4() defaults, with automatic updated_at timestamp triggers on every entity table.
""",
    },

    # --- Cross-Department Documents ---
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666621"),
        "key": "doc_company_handbook",
        "title": "Company-Wide Employee Handbook",
        "dept_id": None,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555505"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333309"),
        "content": """
ACME CORPORATION — COMPANY-WIDE CODE OF BUSINESS CONDUCT AND ETHICS
Universal Employee Document | Organization-Wide Distribution | Effective: 2024

1. Message from the Executive Committee
Welcome to the Acme Corporation family. Regardless of your department — Human Resources, Finance, Sales, or IT — 
our unified mission is to deliver secure, transparent, and innovative technology solutions to our global enterprise clients. 
This Code of Business Conduct sets forth the foundational principles that guide our everyday decisions.

2. Equal Employment Opportunity and Mutual Respect
Acme is dedicated to providing an inclusive, equitable workplace free from discrimination, harassment, and bias. 
All employment decisions, including hiring, compensation, promotion, and termination, are made strictly on merit, qualifications, and business needs. 
We celebrate diverse perspectives and foster an environment where every individual feels valued and respected.

3. Confidentiality, Data Privacy, and Information Security
Information is one of Acme's most critical assets. Every employee is entrusted with protecting sensitive client data, 
proprietary source code, financial projections, and fellow employee records. 
Never share your login credentials, API keys, or access tokens. Report suspicious emails or security anomalies to IT immediately.

4. Conflicts of Interest and Outside Activities
Employees must avoid any relationship, investment, or commercial commitment that interferes with their ability to act in the best interest of Acme. 
Secondary employment, freelance engagements, or advisory board seats must be submitted for prior written review through the compliance department.

5. Sustainable Practices and Social Responsibility
Acme is committed to minimizing our environmental footprint through cloud energy efficiency, paperless operations, 
and community outreach initiatives. Employees receive two paid volunteer days per calendar year to support nonprofit organizations.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666622"),
        "key": "doc_it_usage_policy",
        "title": "General IT Usage Policy",
        "dept_id": None,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555505"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333309"),
        "content": """
ACME CORPORATION — GENERAL ACCEPTABLE IT USAGE POLICY
Applicable to All Employees, Contractors, and Systems | Ref: IT-USE-ALL-001

1. Purpose and Scope
This policy defines the acceptable use of Acme Corporation computing hardware, mobile devices, communication tools, 
cloud accounts, and local network infrastructure. Compliance is mandatory for all authorized users.

2. Authorized Use of Hardware and Computing Assets
Company-issued laptops and mobile devices are provided for business operations. 
Incidental, personal use is permitted provided it does not interfere with productivity, consume excessive network bandwidth, 
or violate any legal or security regulations. Installing unapproved software, peer-to-peer applications, or browser extensions is strictly prohibited.

3. Email, Messaging, and Electronic Communication
All electronic communications transmitted over company networks or using Acme email addresses are business records. 
Users must not transmit defamatory, offensive, harassing, or confidential commercial information to unauthorized recipients. 
Always verify email recipient addresses when transmitting sensitive documents.

4. Network Access and Password Security
- Never bypass network controls, firewalls, or proxy servers.
- Use only approved corporate VPN connections when accessing internal networks remotely.
- Screen locks must engage automatically after 5 minutes of inactivity on all workstations.
- Workstations must not be left unattended in public areas while logged in.

5. Reporting Lost or Stolen Devices
If any company laptop, tablet, or phone is lost, misplaced, or stolen, the incident must be reported to the IT Helpdesk within 2 hours. 
IT will initiate remote cryptographic wiping of the device to protect enterprise data assets.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666623"),
        "key": "doc_org_structure",
        "title": "Organization Structure",
        "dept_id": None,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555505"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333309"),
        "content": """
ACME CORPORATION — ORGANIZATIONAL STRUCTURE AND GOVERNANCE CHARTER
Corporate Operating Model | Reference: ORG-STR-2024

1. Corporate Governance Overview
Acme Corporation is organized into four core functional departments operating under unified executive leadership:
Human Resources, Finance, Sales, and Information Technology. Each department is headed by experienced leadership 
responsible for strategic execution, departmental compliance, and resource governance.

2. Departmental Mandates and Leadership
- Human Resources Department: Led by Helen Vance, HR Manager. 
  Responsible for talent acquisition, employee relations, compensation policy, learning and development, and workplace culture. 
  Alice Smith serves as HR Analyst focusing on workforce analytics and onboarding logistics.
- Finance Department: Led by Frank Castle, Finance Manager. 
  Responsible for accounting, treasury operations, financial forecasting, quarterly revenue audits, and tax compliance. 
  Bob Miller serves as Finance Analyst managing reporting registers and budget reconciliations.
- Sales Department: Led by Sara Connor, Sales Manager. 
  Oversees global enterprise sales, customer relationships, pipeline acceleration, and commercial strategy. 
  Charlie Davis serves as Senior Sales Executive handling enterprise account acquisition.
- Information Technology Department: Led by Irene Adler, IT Administrator. 
  Manages infrastructure architecture, OpenFGA authorization services, cybersecurity, and server runbooks. 
  David Bowman serves as IT Engineer overseeing database optimization and platform reliability.

3. Inter-Departmental Collaboration and Data Governance
Departments collaborate across cross-functional initiatives while strictly maintaining information barriers. 
Sales cannot access confidential HR or Finance compensation records; HR does not access technical server infrastructure keys; 
Finance audits transactions without exposing raw customer intellectual property. 
All boundary enforcements are mediated programmatically through OpenFGA relationship tuples.
""",
    },
    {
        "id": uuid.UUID("66666666-6666-6666-6666-666666666624"),
        "key": "doc_general_policies",
        "title": "General Company Policies",
        "dept_id": None,
        "folder_id": uuid.UUID("55555555-5555-5555-5555-555555555505"),
        "owner_id": uuid.UUID("33333333-3333-3333-3333-333333333309"),
        "content": """
ACME CORPORATION — GENERAL CORPORATE POLICIES AND COMPLIANCE STANDARDS
Universal Document | Reference: POL-GEN-ALL-004

1. Policy Hierarchy and Governance Principles
This document compiles universal corporate policies governing business travel, expense reimbursement, 
intellectual property protection, workplace visitors, and compliance certifications. 
Every employee must comply with these guidelines.

2. Business Travel and Expense Reimbursement
- Travel Authorization: All business travel must receive supervisor approval prior to booking flights or lodging.
- Reimbursable Expenses: Necessary lodging, economy class airfare, ground transportation, and reasonable meals ($75 daily per diem) are reimbursable.
- Expense Submission: Receipts must be submitted through the corporate expense portal within 30 days of expense incurrence. 
  Alcoholic beverages and personal entertainment expenses are strictly non-reimbursable.

3. Intellectual Property and Invention Assignment
All inventions, software code, algorithmic models, patents, and written documentation developed by employees 
within the scope of their employment or utilizing company equipment are the exclusive property of Acme Corporation. 
Employees execute a standard Proprietary Information and Inventions Agreement upon onboarding.

4. Workplace Visitors and Facility Access
All visitors to corporate facilities must sign in at the reception desk, present government-issued photo identification, 
and wear a visible visitor badge. Visitors must be escorted by an authorized Acme employee at all times. 
Access to server rooms and technical development facilities is restricted strictly to badged IT staff.

5. Compliance and Ethics Certification
All employees must complete an annual compliance recertification affirming their ongoing adherence to company policies, 
anti-bribery guidelines (FCPA), and data privacy regulations.
""",
    },
]


async def seed_database(database_url: str):
    """Populate PostgreSQL governance_db with complete seed data."""
    print("Connecting to PostgreSQL for data seeding...")
    # Clean URL for asyncpg
    clean_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(clean_url)

    try:
        print("1. Seeding Organization (Acme Corp)...")
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at)
            VALUES ($1, 'Acme Corporation', 'acme-corp', true, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING;
            """,
            ORG_ID,
        )

        print("2. Seeding Departments...")
        depts = [
            (DEPT_HR_ID, "Human Resources", "People operations and talent", ORG_ID),
            (DEPT_FIN_ID, "Finance", "Accounting and financial governance", ORG_ID),
            (DEPT_SALES_ID, "Sales", "Enterprise sales and revenue operations", ORG_ID),
            (DEPT_IT_ID, "Information Technology", "Cloud infrastructure and IT security", ORG_ID),
        ]
        for dept_id, name, desc, org_id in depts:
            await conn.execute(
                """
                INSERT INTO departments (id, name, description, organization_id, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, true, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
                """,
                dept_id, name, desc, org_id,
            )

        print("3. Seeding Groups...")
        for g in GROUPS:
            await conn.execute(
                """
                INSERT INTO groups (id, name, description, organization_id, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, true, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
                """,
                g["id"], g["name"], f"Group for {g['name']}", ORG_ID,
            )

        print("4. Seeding Folders...")
        for f in FOLDERS:
            await conn.execute(
                """
                INSERT INTO folders (id, name, organization_id, openfga_resource_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, openfga_resource_id = EXCLUDED.openfga_resource_id;
                """,
                f["id"], f["name"], ORG_ID, f["slug"],
            )

        print("5. Seeding Users...")
        for u in USERS:
            await conn.execute(
                """
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, tenant_id, department_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5::user_role, true, true, $6, $7, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name,
                    department_id = EXCLUDED.department_id;
                """,
                u["id"], u["email"], DEFAULT_PASSWORD_HASH, u["full_name"], u["role"], ORG_ID, u["dept_id"],
            )

        print("6. Seeding UserGroup Memberships...")
        user_group_mappings = [
            ("alice", "hr"),
            ("helen", "hr"),
            ("helen", "hr_managers"),
            ("bob", "finance"),
            ("frank", "finance"),
            ("frank", "finance_managers"),
            ("charlie", "sales"),
            ("sara", "sales"),
            ("sara", "sales_managers"),
            ("david", "it"),
            ("irene", "it"),
            ("irene", "it_admins"),
        ]
        user_map = {u["username"]: u["id"] for u in USERS}
        group_map = {g["name"]: g["id"] for g in GROUPS}

        for uname, gname in user_group_mappings:
            uid = user_map[uname]
            gid = group_map[gname]
            await conn.execute(
                """
                INSERT INTO user_groups (id, user_id, group_id, created_at, updated_at)
                VALUES (uuid_generate_v4(), $1, $2, NOW(), NOW())
                ON CONFLICT (user_id, group_id) DO NOTHING;
                """,
                uid, gid,
            )

        print("7. Seeding Documents, Chunks, and Vector Embeddings...")
        for doc_item in DOCUMENTS_SPEC:
            doc_id = doc_item["id"]
            title = doc_item["title"]
            dept_id = doc_item["dept_id"]
            folder_id = doc_item["folder_id"]
            owner_id = doc_item["owner_id"]
            content = doc_item["content"].strip()
            fga_res_id = f"document:{doc_item['key']}"

            # Insert document
            await conn.execute(
                """
                INSERT INTO documents (
                    id, title, description, file_path, file_type, file_size_bytes,
                    status, tenant_id, department_id, folder_id, owner_id, openfga_resource_id,
                    created_at, updated_at
                )
                VALUES (
                    $1, $2, $3, $4, 'txt', $5,
                    'active'::document_status, $6, $7, $8, $9, $10,
                    NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    openfga_resource_id = EXCLUDED.openfga_resource_id,
                    status = EXCLUDED.status;
                """,
                doc_id, title, f"Governance document: {title}", f"/app/data/uploads/{doc_item['key']}.txt",
                len(content.encode()), ORG_ID, dept_id, folder_id, owner_id, fga_res_id,
            )

            # Split into chunks of ~200-300 words with 40-word overlap
            words = content.split()
            chunk_size = 250
            overlap = 40
            start = 0
            chunk_idx = 0

            while start < len(words):
                end = min(start + chunk_size, len(words))
                chunk_words = words[start:end]
                chunk_text = " ".join(chunk_words)
                chunk_uuid = uuid.uuid4()

                # Insert chunk
                await conn.execute(
                    """
                    INSERT INTO document_chunks (id, document_id, chunk_index, content, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    ON CONFLICT (document_id, chunk_index) DO UPDATE SET content = EXCLUDED.content;
                    """,
                    chunk_uuid, doc_id, chunk_idx, chunk_text,
                )

                # Generate real embedding using MiniLM
                emb = EMBEDDER.encode(chunk_text, normalize_embeddings=True).tolist()
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"

                # Store in document_embeddings
                await conn.execute(
                    """
                    INSERT INTO document_embeddings (id, chunk_id, embedding, model_name, created_at, updated_at)
                    VALUES (uuid_generate_v4(), $1, CAST($2 AS vector), 'sentence-transformers/all-MiniLM-L6-v2', NOW(), NOW())
                    ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding;
                    """,
                    chunk_uuid, emb_str,
                )

                chunk_idx += 1
                if end == len(words):
                    break
                start += (chunk_size - overlap)

            print(f"   Indexed document: '{title}' ({chunk_idx} chunks embedded)")

        print("✓ All 24 documents, chunks, and embeddings successfully seeded into PostgreSQL!")

    finally:
        await conn.close()


async def main():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://governance_user:governance_password@localhost:5433/governance_db",
    )
    await seed_database(database_url)


if __name__ == "__main__":
    asyncio.run(main())

