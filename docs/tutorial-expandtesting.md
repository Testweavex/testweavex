# TestWeaveX Tutorial — Testing practice.expandtesting.com

This tutorial walks through a complete TestWeaveX workflow against **[practice.expandtesting.com](https://practice.expandtesting.com/)** — a free, purpose-built QA practice site with 70+ pages covering login flows, forms, dynamic content, file handling, and a full React Notes application.

By the end you will have:
- A working TestWeaveX project with Gherkin feature files
- Test results stored in the built-in TCM
- A gap analysis report showing what is not yet automated
- LLM-generated test suggestions for the highest-priority gaps

---

## Prerequisites

- Python 3.11+
- Node.js 18+ (only if you want to run the Web UI in dev mode)
- An API key for your LLM provider (Anthropic, OpenAI, Ollama, or Azure)

---

## 1. Install TestWeaveX

```bash
pip install "git+https://github.com/Testweavex/testweavex.git[anthropic]"
# Or for OpenAI:
# pip install "git+https://github.com/Testweavex/testweavex.git[openai]"
```

Install Playwright browsers:

```bash
playwright install chromium
```

---

## 2. Create the project

```bash
mkdir expandtesting-tw && cd expandtesting-tw
tw init --llm-provider anthropic
```

This creates `testweavex.config.yaml`. Edit it to add your API key:

```yaml
# testweavex.config.yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key: ${ANTHROPIC_API_KEY}   # or paste key directly (don't commit it)
  temperature: 0.3
  max_retries: 3
  timeout_seconds: 30

gap_analysis:
  scoring_weights:
    priority:  0.30
    test_type: 0.25
    defects:   0.20
    frequency: 0.15
    staleness: 0.10
  match_threshold: 0.65
  top_gaps_default: 10
```

---

## 3. Project structure

Create the following layout:

```
expandtesting-tw/
├── testweavex.config.yaml
├── features/
│   ├── auth/
│   │   └── login.feature
│   ├── notes/
│   │   ├── create_note.feature
│   │   └── delete_note.feature
│   └── forms/
│       └── form_validation.feature
├── steps/
│   ├── auth_steps.py
│   ├── notes_steps.py
│   └── form_steps.py
└── conftest.py
```

---

## 4. Write feature files

### 4.1 Login (`features/auth/login.feature`)

The login page at `/login` accepts username `practice` and password `SuperSecretPassword!`. On success it redirects to `/secure`.

```gherkin
Feature: Login

  Background:
    Given I open the login page

  @smoke @automated
  Scenario: Successful login with valid credentials
    When I enter username "practice" and password "SuperSecretPassword!"
    And I click the Login button
    Then I should be redirected to the secure area
    And I should see "You logged into a secure area!"

  @smoke @automated
  Scenario: Login fails with invalid username
    When I enter username "wronguser" and password "SuperSecretPassword!"
    And I click the Login button
    Then I should see the error "Your username is invalid!"
    And I should remain on the login page

  @regression @automated
  Scenario: Login fails with invalid password
    When I enter username "practice" and password "wrongpassword"
    And I click the Login button
    Then I should see the error "Your password is invalid!"

  @regression
  Scenario: Login page shows username and password fields
    Then the page should have a username input field
    And the page should have a password input field
    And the page should have a Login button
```

### 4.2 Notes App — Create Note (`features/notes/create_note.feature`)

The Notes App at `/notes/app` is a full React CRUD application.

```gherkin
Feature: Create Note

  Background:
    Given I am logged into the Notes app

  @happy_path @automated
  Scenario: Create a new note with title and description
    When I click "Add Note"
    And I enter note title "Meeting prep"
    And I enter note description "Prepare agenda for Monday standup"
    And I select category "Work"
    And I submit the note form
    Then I should see "Note created successfully!" 
    And the note "Meeting prep" should appear in my notes list

  @happy_path @automated
  Scenario: Create a personal note
    When I click "Add Note"
    And I enter note title "Grocery list"
    And I enter note description "Milk, eggs, bread"
    And I select category "Personal"
    And I submit the note form
    Then the note "Grocery list" should appear in my notes list

  @edge_case
  Scenario: Cannot create a note without a title
    When I click "Add Note"
    And I leave the title field empty
    And I enter note description "Some description"
    And I submit the note form
    Then I should see a validation error on the title field

  @edge_case
  Scenario: Note title has maximum length limit
    When I click "Add Note"
    And I enter a note title with 101 characters
    And I submit the note form
    Then I should see a validation error indicating title is too long
```

### 4.3 Notes App — Delete Note (`features/notes/delete_note.feature`)

```gherkin
Feature: Delete Note

  Background:
    Given I am logged into the Notes app
    And I have a note titled "Temp note"

  @happy_path @automated
  Scenario: Delete an existing note
    When I open the note "Temp note"
    And I click the Delete button
    And I confirm the deletion
    Then the note "Temp note" should no longer appear in my notes list
    And I should see "Note deleted successfully!"

  @regression
  Scenario: Cancelled deletion keeps the note
    When I open the note "Temp note"
    And I click the Delete button
    And I cancel the deletion
    Then the note "Temp note" should still appear in my notes list
```

### 4.4 Form Validation (`features/forms/form_validation.feature`)

The form at `/form-validation` uses Bootstrap validation.

```gherkin
Feature: Form Validation

  Background:
    Given I open the form validation page

  @smoke @automated
  Scenario: Submit valid form data successfully
    When I fill in first name "Alice"
    And I fill in last name "Smith"
    And I fill in a valid email "alice@example.com"
    And I select a country from the dropdown
    And I agree to the terms
    And I submit the form
    Then the form should be submitted successfully

  @edge_case @automated
  Scenario: Required fields show errors on empty submit
    When I click the Submit button without filling any fields
    Then I should see validation errors on all required fields

  @edge_case
  Scenario: Invalid email format is rejected
    When I fill in first name "Bob"
    And I fill in last name "Jones"
    And I fill in an invalid email "not-an-email"
    And I submit the form
    Then I should see an email validation error

  @edge_case
  Scenario: Form clears all fields on reset
    When I fill in first name "Test"
    And I click the Reset button
    Then all form fields should be empty
```

---

## 5. Write step definitions

### `conftest.py`

```python
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "https://practice.expandtesting.com"
NOTES_URL = f"{BASE_URL}/notes/app"

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()

@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()
```

### `steps/auth_steps.py`

```python
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import expect

BASE_URL = "https://practice.expandtesting.com"

@given("I open the login page")
def open_login(page):
    page.goto(f"{BASE_URL}/login")

@when(parsers.parse('I enter username "{username}" and password "{password}"'))
def enter_credentials(page, username, password):
    page.fill("#username", username)
    page.fill("#password", password)

@when("I click the Login button")
def click_login(page):
    page.click('button[type="submit"]')

@then("I should be redirected to the secure area")
def check_redirect(page):
    expect(page).to_have_url(f"{BASE_URL}/secure")

@then(parsers.parse('I should see "{message}"'))
def check_message(page, message):
    expect(page.locator(".flash")).to_contain_text(message)

@then(parsers.parse('I should see the error "{error}"'))
def check_error(page, error):
    expect(page.locator(".flash.error, .flash-error")).to_contain_text(error)

@then("I should remain on the login page")
def check_still_on_login(page):
    expect(page).to_have_url(f"{BASE_URL}/login")
```

### `steps/notes_steps.py`

```python
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import expect

NOTES_URL = "https://practice.expandtesting.com/notes/app"

NOTES_USER = "testuser@example.com"
NOTES_PASS = "TestPass123!"   # register this user once manually

@given("I am logged into the Notes app")
def notes_login(page):
    page.goto(f"{NOTES_URL}/login")
    page.fill('input[name="email"]', NOTES_USER)
    page.fill('input[name="password"]', NOTES_PASS)
    page.click('button[type="submit"]')
    expect(page.locator("h1")).to_contain_text("Notes")

@when('I click "Add Note"')
def click_add_note(page):
    page.click('text=Add Note')

@when(parsers.parse('I enter note title "{title}"'))
def enter_title(page, title):
    page.fill('input[name="title"]', title)

@when(parsers.parse('I enter note description "{desc}"'))
def enter_desc(page, desc):
    page.fill('textarea[name="description"]', desc)

@when(parsers.parse('I select category "{category}"'))
def select_category(page, category):
    page.select_option('select[name="category"]', label=category)

@when("I submit the note form")
def submit_note(page):
    page.click('button[type="submit"]')

@then(parsers.parse('the note "{title}" should appear in my notes list'))
def check_note_visible(page, title):
    expect(page.locator(f'text="{title}"')).to_be_visible()
```

### `steps/form_steps.py`

```python
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import expect

FORM_URL = "https://practice.expandtesting.com/form-validation"

@given("I open the form validation page")
def open_form(page):
    page.goto(FORM_URL)

@when(parsers.parse('I fill in first name "{name}"'))
def fill_first_name(page, name):
    page.fill('#validationCustom01', name)

@when(parsers.parse('I fill in last name "{name}"'))
def fill_last_name(page, name):
    page.fill('#validationCustom02', name)

@when(parsers.parse('I fill in a valid email "{email}"'))
def fill_email(page, email):
    page.fill('#validationCustomUsername', email)

@when("I select a country from the dropdown")
def select_country(page):
    page.select_option('#validationCustom04', index=1)

@when("I agree to the terms")
def agree_terms(page):
    page.check('#invalidCheck')

@when("I click the Submit button without filling any fields")
def click_submit_empty(page):
    page.click('button[type="submit"]')

@when("I submit the form")
def submit_form(page):
    page.click('button[type="submit"]')

@then("the form should be submitted successfully")
def check_submitted(page):
    # Bootstrap validation resets on success
    expect(page.locator('form')).to_be_visible()

@then("I should see validation errors on all required fields")
def check_all_errors(page):
    invalid = page.locator('.invalid-feedback:visible')
    assert invalid.count() > 0
```

---

## 6. Run the tests

```bash
# Run all tests
tw

# Run only smoke tests
tw -k smoke

# Run only automated scenarios (by tag)
tw -k "automated"

# Verbose output
tw -v

# Stop on first failure
tw -x

# Run in parallel (4 workers)
tw -n 4
```

After running, TestWeaveX stores results in `.testweavex/results.db` automatically.

Expected output:

```
========================= test session starts =========================
platform linux -- Python 3.12.0
collected 14 items

features/auth/login.feature::Successful login with valid credentials PASSED
features/auth/login.feature::Login fails with invalid username PASSED
features/auth/login.feature::Login fails with invalid password PASSED
features/notes/create_note.feature::Create a new note with title and description PASSED
features/notes/create_note.feature::Create a personal note PASSED
features/notes/delete_note.feature::Delete an existing note PASSED
features/forms/form_validation.feature::Submit valid form data successfully PASSED
features/forms/form_validation.feature::Required fields show errors on empty submit PASSED
...

========================= 8 passed, 6 not yet automated =========================
```

---

## 7. Check coverage and gaps

```bash
# Coverage summary by test type
tw status
```

```
TestWeaveX Status — Coverage: 57.1%
┌───────────────┬───────┬───────────┬─────┐
│ Test Type     │ Total │ Automated │ Gap │
├───────────────┼───────┼───────────┼─────┤
│ smoke         │   4   │     3     │  1  │
│ happy_path    │   4   │     3     │  1  │
│ edge_case     │   6   │     2     │  4  │
│ regression    │   4   │     0     │  4  │
└───────────────┴───────┴───────────┴─────┘
```

```bash
# Show the top 10 highest-priority automation gaps
tw gaps --limit 10
```

```
Top 10 Automation Gaps
┌───────┬──────────────────────────────────────────────┬──────────────────┐
│ Score │ Reason                                       │ Test Case ID     │
├───────┼──────────────────────────────────────────────┼──────────────────┤
│ 0.872 │ smoke test — not run in last 7 days          │ a1b2c3d4e5f6g7h8 │
│ 0.841 │ edge_case — P1 priority, never automated     │ b2c3d4e5f6g7h8i9 │
│ 0.803 │ regression — linked to 2 past defects        │ c3d4e5f6g7h8i9j0 │
│ 0.791 │ happy_path — high execution frequency        │ d4e5f6g7h8i9j0k1 │
│ ...   │ ...                                          │ ...              │
└───────┴──────────────────────────────────────────────┴──────────────────┘
```

---

## 8. Open the Web UI

```bash
tw serve
```

Open **http://localhost:8080** in your browser.

The Web UI shows three screens:

### Dashboard
Four KPI cards update in real time from the SQLite database:
- **Total Tests** — 14 test cases
- **Automated %** — 57.1%
- **Open Gaps** — 10
- **Last Run** — the run ID of your most recent `tw` invocation

### Test Cases
A filterable table of all test cases. Filter by:
- **Test type** — smoke, happy_path, edge_case, regression, e2e, etc.
- **Automation status** — All / Automated / Manual

### Gap Report
A ranked table of unautomated tests ordered by priority score (0–1). Each row shows:
- **Score** — weighted priority (higher = automate first)
- **Reason** — why this gap scored high
- **Test Case** — linked to the feature/scenario

Click **Generate** on any gap row to call the LLM and get Gherkin scenario suggestions:

```gherkin
# LLM suggestion for "Login fails with empty fields" gap:
Scenario: Login fails when fields are left empty
  Given I open the login page
  When I click the Login button without entering any credentials
  Then I should see validation messages for both username and password fields
  And I should remain on the login page
```

Review the suggestion, then paste it into your feature file. TestWeaveX never writes to your repo without your approval.

---

## 9. Practice site scenarios by test type

Use these as a backlog of test cases to build coverage over time.

### Smoke tests (automate first)

| Scenario | URL |
|----------|-----|
| Login with valid credentials | `/login` |
| Load the Notes app home page | `/notes/app` |
| HTTP health check returns 200 | `/api/health-check` |
| Home page loads without JS errors | `/javascript-error` |

### Happy path

| Scenario | URL |
|----------|-----|
| Register a new Notes account | `/notes/app/register` |
| Create, edit, and delete a note | `/notes/app` |
| Submit valid contact form | `/contact` |
| Upload a file and verify it appears | `/upload` |
| Download a file and verify content | `/download` |
| BMI calculator returns correct result | `/bmi` |

### Edge cases

| Scenario | URL |
|----------|-----|
| Login with empty username | `/login` |
| Login with empty password | `/login` |
| Form submit with all required fields empty | `/form-validation` |
| Note title exceeds maximum length | `/notes/app` |
| File upload with unsupported format | `/upload` |
| Slider set to minimum and maximum values | `/horizontal-slider` |
| Dynamic table content changes on reload | `/dynamic-table` |
| Disappearing element is absent after reload | `/disappearing-elements` |

### Integration / E2E

| Scenario | URL |
|----------|-----|
| Full Notes CRUD: register → login → create → edit → delete | `/notes/app` |
| Secure file download after authentication | `/download-secure` |
| OTP login flow end-to-end | `/otp-login` |
| Password reset request and confirmation | `/forgot-password` |

### Accessibility

| Scenario | URL |
|----------|-----|
| Login form is keyboard navigable | `/login` |
| Form validation errors are screen-reader accessible | `/form-validation` |
| Notes app passes basic WCAG colour contrast | `/notes/app` |

---

## 10. Generate tests for uncovered scenarios

For any gap in the report, use the Web UI Generate button or run from the CLI once the engine is wired:

```bash
tw gaps --generate --limit 5
```

This calls the LLM (using the skill file matching each test case's type) and returns Gherkin suggestions. You review and approve; nothing is written to disk without your action.

Example LLM output for the "Dynamic table content changes on reload" gap:

```gherkin
Scenario Outline: Dynamic table shows different values on each load
  Given I open the dynamic table page
  When I record the value in column "<column>"
  And I reload the page
  Then the value in column "<column>" should be different from the recorded value

  Examples:
    | column  |
    | Company |
    | Contact |
    | Country |
```

---

## 11. Next steps

| Goal | Command |
|------|---------|
| View run history | `tw history --last-n 20` |
| Sync from external TCM (TestRail) | `tw migrate --source testrail` |
| Analyse gaps after each CI run | Add `tw gaps` to your CI pipeline |
| Share results with your team | Deploy with `DATABASE_URL` pointing to PostgreSQL |

For team deployment (shared dashboard across developers and CI), see the [Team & Cloud Deployment](https://github.com/Testweavex/testweavex#team--cloud-deployment) section of the README.

---

## Appendix: Useful `tw` flags for this project

```bash
tw --co -q                             # list collected tests without running
tw -k "smoke and not edge_case"        # combine tag filters
tw --tb=short                          # shorter traceback on failure
tw -n auto                             # auto-detect CPU count for parallelism
tw --ignore=features/notes             # skip notes tests (requires live account)
tw features/auth/login.feature         # run a single feature file
```
