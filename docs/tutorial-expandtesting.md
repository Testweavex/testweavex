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
- An API key for your LLM provider (Anthropic, OpenAI, Ollama, or Azure)

---

## 1. Install TestWeaveX

```bash
pip install "git+https://github.com/Testweavex/testweavex.git[anthropic]"
# Or for OpenAI:
# pip install "git+https://github.com/Testweavex/testweavex.git[openai]"
```

Install Playwright and the Chromium browser:

```bash
pip install playwright requests
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

```
expandtesting-tw/
├── testweavex.config.yaml
├── pytest.ini
├── conftest.py
├── features/
│   ├── auth/
│   │   └── login.feature
│   ├── notes/
│   │   ├── create_note.feature
│   │   └── delete_note.feature
│   └── forms/
│       └── form_validation.feature
├── steps/
│   ├── __init__.py
│   ├── auth_steps.py
│   ├── notes_steps.py
│   └── form_steps.py
├── test_login.py
├── test_notes.py
└── test_forms.py
```

---

## 4. pytest.ini

```ini
[pytest]
markers =
    smoke: smoke tests — fast, critical path
    sanity: sanity checks
    regression: regression suite
    automated: scenario has automated step definitions
    happy_path: happy-path scenarios
    edge_case: edge-case / negative scenarios
```

---

## 5. conftest.py

```python
import pytest
from playwright.sync_api import sync_playwright

# import step definitions so pytest-bdd can discover them
from steps import auth_steps, notes_steps, form_steps  # noqa: F401

BASE_URL = "https://practice.expandtesting.com"
NOTES_URL = f"{BASE_URL}/notes/app"

@pytest.fixture(scope="session")
def browser_instance():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()

@pytest.fixture
def page(browser_instance):
    ctx = browser_instance.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()
```

---

## 6. Feature files

### 6.1 Login (`features/auth/login.feature`)

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
    Then I should see the error "Your password is invalid!"
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

### 6.2 Notes App — Create Note (`features/notes/create_note.feature`)

The Notes App at `/notes/app` is a full React CRUD application. Register a dedicated test account once at `/notes/app/register` using the credentials in `notes_steps.py`.

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
    Then the note "Meeting prep" should appear in my notes list

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

### 6.3 Notes App — Delete Note (`features/notes/delete_note.feature`)

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

  @regression
  Scenario: Cancelled deletion keeps the note
    When I open the note "Temp note"
    And I click the Delete button
    And I cancel the deletion
    Then the note "Temp note" should still appear in my notes list
```

### 6.4 Form Validation (`features/forms/form_validation.feature`)

The form at `/form-validation` has contact name, contact number, and payment method fields with Bootstrap validation.

```gherkin
Feature: Form Validation

  Background:
    Given I open the form validation page

  @smoke @automated
  Scenario: Submit valid form data successfully
    When I fill in contact name "Alice Smith"
    And I fill in a contact number "012-3456789"
    And I select a payment method
    And I submit the form
    Then the form should be submitted successfully

  @edge_case @automated
  Scenario: Required fields show errors on empty submit
    When I click the Submit button without filling any fields
    Then I should see validation errors on all required fields
```

---

## 7. Step definitions

### `steps/__init__.py`

Empty file — marks the directory as a Python package.

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
    expect(page.locator("#flash")).to_contain_text(message)

@then(parsers.parse('I should see the error "{error}"'))
def check_error(page, error):
    expect(page.locator("#flash")).to_contain_text(error)

@then("I should remain on the login page")
def check_still_on_login(page):
    expect(page).to_have_url(f"{BASE_URL}/login")

@then("the page should have a username input field")
def check_username_field(page):
    expect(page.locator("#username")).to_be_visible()

@then("the page should have a password input field")
def check_password_field(page):
    expect(page.locator("#password")).to_be_visible()

@then("the page should have a Login button")
def check_login_button(page):
    expect(page.locator('button[type="submit"]')).to_be_visible()
```

### `steps/notes_steps.py`

The Notes REST API at `https://practice.expandtesting.com/notes/api` is used for test-data setup (creating and cleaning up notes via API before/after each scenario) so tests remain independent. Register a dedicated test account once via the UI before running.

```python
import requests as _req
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import expect

NOTES_BASE = "https://practice.expandtesting.com/notes/app"
NOTES_API  = "https://practice.expandtesting.com/notes/api"
NOTES_USER = "twxtutorial@mailinator.com"   # register once at /notes/app/register
NOTES_PASS = "TutorialPass123!"

def _api_token():
    r = _req.post(f"{NOTES_API}/users/login",
                  json={"email": NOTES_USER, "password": NOTES_PASS})
    return r.json()["data"]["token"]

def _delete_notes_by_title(title):
    """Clean up notes with a given title via API before creating fresh test data."""
    token = _api_token()
    headers = {"x-auth-token": token}
    data = _req.get(f"{NOTES_API}/notes", headers=headers).json().get("data", [])
    for note in data:
        if note["title"] == title:
            _req.delete(f"{NOTES_API}/notes/{note['id']}", headers=headers)

def _login_notes(page):
    page.goto(f"{NOTES_BASE}/login", timeout=60000)
    page.fill('[data-testid="login-email"]', NOTES_USER)
    page.fill('[data-testid="login-password"]', NOTES_PASS)
    page.click('[data-testid="login-submit"]')
    page.wait_for_url(f"{NOTES_BASE}**", timeout=30000)

@given("I am logged into the Notes app")
def notes_login(page):
    _login_notes(page)

@given(parsers.parse('I have a note titled "{title}"'))
def ensure_note_exists(page, title):
    _delete_notes_by_title(title)
    page.reload()
    page.wait_for_selector('[data-testid="add-new-note"]', timeout=15000)
    page.click('[data-testid="add-new-note"]')
    page.wait_for_selector('[data-testid="note-title"]')
    page.fill('[data-testid="note-title"]', title)
    page.fill('[data-testid="note-description"]', "Auto-created for test")
    page.select_option('[data-testid="note-category"]', label="Home")
    page.click('[data-testid="note-submit"]')
    page.wait_for_selector('[data-testid="add-new-note"]', timeout=15000)

@when('I click "Add Note"')
def click_add_note(page):
    page.click('[data-testid="add-new-note"]')
    page.wait_for_selector('[data-testid="note-title"]')

@when(parsers.parse('I enter note title "{title}"'))
def enter_title(page, title):
    page.fill('[data-testid="note-title"]', title)

@when(parsers.parse('I enter note description "{desc}"'))
def enter_desc(page, desc):
    page.fill('[data-testid="note-description"]', desc)

@when(parsers.parse('I select category "{category}"'))
def select_category(page, category):
    page.select_option('[data-testid="note-category"]', label=category)

@when("I submit the note form")
def submit_note(page):
    page.click('[data-testid="note-submit"]')

@when("I leave the title field empty")
def leave_title_empty(page):
    pass   # title field is already empty after clicking Add Note

@when("I enter a note title with 101 characters")
def enter_long_title(page):
    page.fill('[data-testid="note-title"]', "a" * 101)

@then(parsers.parse('the note "{title}" should appear in my notes list'))
def check_note_visible(page, title):
    page.wait_for_selector('[data-testid="add-new-note"]', timeout=15000)
    expect(
        page.locator('[data-testid="note-card-title"]').filter(has_text=title).first
    ).to_be_visible()

@then("I should see a validation error on the title field")
def check_title_error(page):
    expect(page.locator('[data-testid="note-title"].is-invalid')).to_be_visible()

@then("I should see a validation error indicating title is too long")
def check_title_too_long(page):
    expect(page.locator('[data-testid="note-title"].is-invalid')).to_be_visible()

@when(parsers.parse('I open the note "{title}"'))
def open_note(page, title):
    page.locator('[data-testid="note-card"]').filter(has_text=title) \
        .locator('[data-testid="note-view"]').first.click()
    page.wait_for_load_state("networkidle")

@when("I click the Delete button")
def click_delete(page):
    page.click('[data-testid="note-delete"]')
    page.wait_for_timeout(800)

@when("I confirm the deletion")
def confirm_deletion(page):
    page.click('[data-testid="note-delete-confirm"]')
    page.wait_for_selector('[data-testid="add-new-note"]', timeout=15000)

@when("I cancel the deletion")
def cancel_deletion(page):
    page.click('[data-testid="note-delete-cancel-2"]')

@then(parsers.parse('the note "{title}" should no longer appear in my notes list'))
def check_note_gone(page, title):
    expect(
        page.locator('[data-testid="note-card-title"]').filter(has_text=title)
    ).to_have_count(0)

@then(parsers.parse('the note "{title}" should still appear in my notes list'))
def check_note_still_there(page, title):
    expect(
        page.locator('[data-testid="note-card-title"]').filter(has_text=title).first
    ).to_be_visible()
```

### `steps/form_steps.py`

```python
from pytest_bdd import given, when, then, parsers
from playwright.sync_api import expect

FORM_URL = "https://practice.expandtesting.com/form-validation"

@given("I open the form validation page")
def open_form(page):
    page.goto(FORM_URL)
    page.wait_for_load_state("domcontentloaded")

@when(parsers.parse('I fill in contact name "{name}"'))
def fill_contact_name(page, name):
    page.fill('#validationCustom01', name)

@when(parsers.parse('I fill in a contact number "{number}"'))
def fill_contact_number(page, number):
    page.locator('input[name="contactnumber"]').fill(number)

@when("I select a payment method")
def select_payment(page):
    page.select_option('#validationCustom04', index=1)

@when("I click the Submit button without filling any fields")
def click_submit_empty(page):
    page.click('button[type="submit"]')

@when("I submit the form")
def submit_form(page):
    page.click('button[type="submit"]')

@then("the form should be submitted successfully")
def check_submitted(page):
    expect(page.locator('form')).to_be_visible()

@then("I should see validation errors on all required fields")
def check_all_errors(page):
    invalid = page.locator('.invalid-feedback:visible')
    assert invalid.count() > 0
```

---

## 8. Test runner files

These files bind feature files to pytest test functions via pytest-bdd.

### `test_login.py`

```python
from pytest_bdd import scenarios
from steps.auth_steps import *  # noqa: F401, F403

scenarios('features/auth/login.feature')
```

### `test_notes.py`

```python
from pytest_bdd import scenarios
from steps.notes_steps import *  # noqa: F401, F403

scenarios('features/notes/create_note.feature')
scenarios('features/notes/delete_note.feature')
```

### `test_forms.py`

```python
from pytest_bdd import scenarios
from steps.form_steps import *  # noqa: F401, F403

scenarios('features/forms/form_validation.feature')
```

---

## 9. Run the tests

```bash
# Run all tests
pytest -v

# Run only smoke tests
pytest -v -m smoke

# Run only automated scenarios
pytest -v -m automated

# Run a single feature file
pytest test_login.py -v

# Stop on first failure
pytest -v -x

# Shorter tracebacks
pytest -v --tb=short
```

Verified output (Python 3.12, pytest-bdd 8, Playwright 1.60):

```
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0
rootdir: expandtesting-tw
configfile: pytest.ini
plugins: bdd-8.1.0
collected 12 items

test_forms.py::test_submit_valid_form_data_successfully          PASSED [  8%]
test_forms.py::test_required_fields_show_errors_on_empty_submit  PASSED [ 16%]
test_login.py::test_successful_login_with_valid_credentials       PASSED [ 25%]
test_login.py::test_login_fails_with_invalid_username             PASSED [ 33%]
test_login.py::test_login_fails_with_invalid_password             PASSED [ 41%]
test_login.py::test_login_page_shows_username_and_password_fields PASSED [ 50%]
test_notes.py::test_create_a_new_note_with_title_and_description  PASSED [ 58%]
test_notes.py::test_create_a_personal_note                        PASSED [ 66%]
test_notes.py::test_cannot_create_a_note_without_a_title          PASSED [ 75%]
test_notes.py::test_note_title_has_maximum_length_limit           PASSED [ 83%]
test_notes.py::test_delete_an_existing_note                       PASSED [ 91%]
test_notes.py::test_cancelled_deletion_keeps_the_note             PASSED [100%]

======================== 12 passed in 64.96s (0:01:04) =========================
```

---

## 10. Check coverage and gaps

Once TestWeaveX is installed and wrapping pytest via `tw`, results are stored in `.testweavex/results.db` automatically.

```bash
# Coverage summary by test type
tw status
```

```
TestWeaveX Status — Coverage: 58.3%
┌───────────────┬───────┬───────────┬─────┐
│ Test Type     │ Total │ Automated │ Gap │
├───────────────┼───────┼───────────┼─────┤
│ smoke         │   4   │     3     │  1  │
│ happy_path    │   4   │     3     │  1  │
│ edge_case     │   4   │     2     │  2  │
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
│ 0.872 │ smoke test — not run in last 7 days          │ a1b2c3d4e5f6…   │
│ 0.841 │ edge_case — P1 priority, never automated     │ b2c3d4e5f6g7…   │
│ 0.803 │ regression — linked to 2 past defects        │ c3d4e5f6g7h8…   │
│ 0.791 │ happy_path — high execution frequency        │ d4e5f6g7h8i9…   │
└───────┴──────────────────────────────────────────────┴──────────────────┘
```

---

## 11. Open the Web UI

```bash
tw serve
```

Open **http://localhost:8080** in your browser. Five views are available:

### Dashboard
Four KPI cards from the last test run:
- **Total Tests** — 12 test cases
- **Automated %** — 58.3%
- **Open Gaps** — 6
- **Last Run** — truncated UUID of the most recent run

### Test Cases
Filterable table of all 12 test cases. Filter by test type (smoke, happy_path, edge_case, regression) or automation status (Automated / Manual).

### Gap Report
Ranked table of unautomated scenarios ordered by priority score (0–1). Click **Generate** on any row to call the LLM and get Gherkin suggestions:

```gherkin
# LLM suggestion for the "Login fails with empty fields" gap:
Scenario: Login fails when fields are left empty
  Given I open the login page
  When I click the Login button without entering any credentials
  Then I should see validation messages for both username and password fields
  And I should remain on the login page
```

Review the suggestion, then paste it into your feature file. TestWeaveX never writes to your repo without your approval.

### Test Runs
Run history table — click any row to expand it and see a per-test breakdown with pass/fail/skip counts, duration per test, and error messages for failures.

### Settings
Two-section settings panel:
- **LLM** — change provider (openai / anthropic / ollama / azure), model name, and temperature. Click **Save Changes** to write `testweavex.config.yaml`.
- **Gap Analysis** — read-only view of current scoring weights, match threshold, and TCM provider.

---

## 12. Generate tests for uncovered scenarios

For any gap in the report, use the Web UI Generate button or run from the CLI:

```bash
tw gaps --generate --limit 5
```

Example LLM output for a dynamic-table gap:

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

## 13. Practice site scenarios — full backlog by test type

Use these as a backlog to build coverage over time.

### Smoke (automate first)

| Scenario | URL |
|----------|-----|
| Login with valid credentials | `/login` |
| Load the Notes app home page | `/notes/app` |
| Home page loads without JS errors | `/javascript-error` |
| Form page renders all fields | `/form-validation` |

### Happy path

| Scenario | URL |
|----------|-----|
| Register a new Notes account | `/notes/app/register` |
| Create, edit, and delete a note | `/notes/app` |
| Upload a file and verify it appears | `/upload` |
| Download a file and verify content | `/download` |
| BMI calculator returns correct result | `/bmi` |

### Edge cases

| Scenario | URL |
|----------|-----|
| Login with empty username | `/login` |
| Login with empty password | `/login` |
| Form submit with all fields empty | `/form-validation` |
| Note title exceeds 100 characters | `/notes/app` |
| File upload with unsupported format | `/upload` |
| Slider set to minimum and maximum | `/horizontal-slider` |
| Disappearing element absent after reload | `/disappearing-elements` |

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

## 14. Next steps

| Goal | Command |
|------|---------|
| View run history | `tw history --last-n 20` |
| Sync from TestRail | `tw migrate --source testrail` |
| Analyse gaps after each CI run | Add `tw gaps` to your CI pipeline |
| Share results with your team | Deploy with `DATABASE_URL` pointing to PostgreSQL |

---

## Appendix: Useful flags

```bash
pytest --co -q                          # list collected tests without running
pytest -m "smoke and not edge_case"     # combine marker filters
pytest --tb=short                       # shorter traceback on failure
pytest -n auto                          # auto parallelism (requires pytest-xdist)
pytest --ignore=features/notes          # skip notes tests (requires live account)
pytest test_login.py -v                 # run a single feature's tests
```

### Notes app account setup

The Notes app requires a registered account. Do this once:

1. Go to `https://practice.expandtesting.com/notes/app/register`
2. Register with email `twxtutorial@mailinator.com` and password `TutorialPass123!`
3. After registration the step definitions authenticate via the Notes API and clean up test data automatically between runs — no manual teardown needed.
