<!--
Sync Impact Report:
- Version change: Initial → 1.0.0
- Modified principles: N/A (initial creation)
- Added sections: All core principles, technical standards, development workflow
- Removed sections: N/A (initial creation)
- Templates requiring updates:
  ✅ plan-template.md - Reviewed for constitution alignment
  ✅ spec-template.md - Reviewed for constitution alignment
  ✅ tasks-template.md - Reviewed for constitution alignment
- Follow-up TODOs: None
-->

# StockValueFinder Constitution

## Core Principles

### I. Type Safety (NON-NEGOTIABLE)

All Python code MUST enforce strict type safety using Python type hints. This is a backend-only system where financial calculations require absolute precision.

**Requirements:**
- Every function MUST have explicit parameter and return type annotations
- Use `typing` module for complex types (List, Dict, Optional, Union, etc.)
- Use Pydantic models for all data structures exchanged between modules
- Run `mypy` in strict mode: `mypy --strict`
- No `Any` types except in exceptional cases with documented justification

**Rationale:** Financial systems cannot tolerate type-related runtime errors. Type hints serve as executable documentation and catch errors at development time rather than in production where incorrect calculations could result in financial loss.

### II. Deterministic Calculations

LLMs MUST NEVER perform arithmetic or financial calculations directly. All numerical computations MUST be executed by deterministic Python code.

**Requirements:**
- LLMs extract parameters and structure problems
- Python functions perform all calculations
- All calculation functions MUST be pure (no side effects)
- Results MUST include audit trail (input parameters, formula used, intermediate steps)
- Isolate calculation execution in Docker containers for security

**Rationale:** LLMs are prone to hallucination in mathematical operations. In financial contexts, a calculation error can lead to incorrect investment decisions. Deterministic code ensures reproducibility and verifiability.

### III. Separation of Concerns

Architecture MUST maintain strict separation between data models, business logic, and API/interface layers.

**Requirements:**
- Data models: Pydantic schemas defining structures
- Business logic: Pure functions operating on typed data
- API layer: FastAPI endpoints with request/response validation
- No database logic in business functions
- No business logic in API endpoints

**Rationale:** A backend-only system must be maintainable and testable. Clear separation enables independent testing of business logic without API overhead, and allows swapping API frameworks without touching core logic.

### IV. Test-Driven Development (TDD)

TDD is mandatory for all new functionality. Tests MUST be written before implementation code.

**Requirements:**
- Red-Green-Refactor cycle strictly enforced
- Test coverage MUST exceed 80% (measured by pytest-cov)
- Unit tests for pure business logic functions
- Integration tests for database operations
- Property-based testing (Hypothesis) for financial calculations
- All tests MUST be deterministic (no random data without fixed seeds)

**Rationale:** Financial systems require correctness guarantees. TDD ensures code is designed for testability from the start, and property-based tests catch edge cases that example-based tests miss.

### V. Immutability

Data structures MUST be treated as immutable. Functions MUST return new objects rather than modifying inputs.

**Requirements:**
- Use `@dataclass(frozen=True)` or Pydantic `frozen=True` for models
- List comprehensions over `.append()` loops
- Dictionary unpacking `{**d, 'key': value}` over in-place updates
- Never mutate function parameters

**Rationale:** Immutability prevents hidden side effects, makes debugging easier, and enables safe concurrency. In financial calculations, immutability ensures audit trails remain intact.

## Technical Standards

### Technology Stack

**Backend Framework:**
- FastAPI for API endpoints (async/await support)
- Pydantic v2 for data validation
- SQLAlchemy with async session for database
- Alembic for database migrations

**Data Processing:**
- pandas for structured data manipulation
- numpy for numerical computations
- LangChain/LangGraph for agent orchestration

**Testing:**
- pytest for test framework
- pytest-cov for coverage
- pytest-asyncio for async tests
- Hypothesis for property-based testing

**Code Quality:**
- mypy for type checking (strict mode)
- ruff for linting and formatting
- pre-commit hooks for quality gates

### Dependency Management

- Use `uv` as package manager
- All dependencies MUST be pinned in `pyproject.toml`
- Separate dev dependencies (test, lint, typecheck)
- Regular dependency updates for security patches

### Data Validation

- All inputs MUST be validated at system boundaries
- Pydantic models for API requests/responses
- Custom validators for business rules (e.g., positive interest rates)
- Never trust external data sources (APIs, user input, files)

## Development Workflow

### Quality Gates

All code MUST pass the following checks before merging:

1. **Type Check:** `uv run mypy --strict .` (zero errors)
2. **Lint:** `uv run ruff check .` (zero warnings)
3. **Format:** `uv run ruff format .` (auto-applied)
4. **Tests:** `uv run pytest --cov` (>80% coverage)
5. **Security:** `uv run bandit -r .` (no high-severity issues)

### Git Workflow

- Feature branches: `feature/<ticket>-<description>`
- Commit messages: Conventional Commits format
  - `feat:` new feature
  - `fix:` bug fix
  - `refactor:` code restructuring without behavior change
  - `test:` adding/updating tests
  - `docs:` documentation updates
- Pull requests require approval
- CI/CD pipeline runs all quality gates automatically

### Documentation Requirements

- All modules MUST have docstrings (Google style)
- Complex algorithms MUST include mathematical formulas in docstrings
- API endpoints MUST include OpenAPI documentation
- Architecture decisions recorded in `doc/` folder

## Error Handling

### Comprehensive Error Handling

- Every function that can fail MUST handle errors explicitly
- Use typed exceptions for domain-specific errors
- Server-side: Log detailed error context with structured logging
- API responses: User-friendly error messages without sensitive details

**Never:**
- Silence exceptions with bare `except:`
- Return `None` on error (raise exception instead)
- Expose stack traces to API clients

## Security Requirements

### Secret Management

- NEVER hardcode secrets in source code
- Use environment variables via `python-dotenv`
- Validate required secrets at startup
- Document required environment variables in `.env.example`

### Calculation Security

- Python code execution MUST be isolated in Docker containers
- Timeout limits on all calculation executions
- Resource limits (CPU, memory) on sandbox containers
- No network access from calculation containers

### API Security

- Rate limiting on all endpoints
- Input validation and sanitization
- SQL injection prevention (parameterized queries only)
- Authentication/authorization for protected endpoints

## Governance

This constitution governs all development activity for StockValueFinder. It supersedes conflicting practices or conventions not explicitly documented herein.

### Amendment Process

Constitution amendments require:
1. Written proposal with rationale
2. Team review and approval
3. Migration plan for existing code
4. Version bump following semantic versioning

### Compliance Verification

- All pull requests MUST reference constitution principles they implement
- Code reviews MUST verify constitution compliance
- Non-compliance requires explicit justification and approval

### Complexity Management

Complexity MUST be justified:
- Prefer simple solutions over clever ones
- Additional abstraction layers require documented benefit
- YAGNI (You Aren't Gonna Need It) principle for features

**Version**: 1.0.0 | **Ratified**: 2026-02-26 | **Last Amended**: 2026-02-26
