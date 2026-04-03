# Coding Agent

An AI-powered code editing assistant with clean architecture.

## Architecture

This project follows **Clean Architecture** / **Ports & Adapters** principles with clear separation of concerns:

```
coding_agent/
├── domain/              # Enterprise business rules (no external deps)
│   └── models.py        # Domain entities (Symbol, Edit, FileInfo, etc.)
│
├── application/         # Use cases and orchestration
│   ├── ports/           # Abstract interfaces
│   ├── services/        # Application services
│   └── dto/             # Request/Response DTOs
│
├── infrastructure/      # External concerns (implements ports)
│   ├── llm/            # LLM providers (OpenAI)
│   ├── parsers/        # Code parsers
│   ├── storage/        # File storage
│   └── edit_formats/   # Edit format implementations
│
├── config/             # Configuration and DI
│   ├── settings.py     # Pydantic settings
│   └── container.py    # DI container
│
├── cli/                # User interface
│   └── main.py         # Entry point
│
└── utils/              # Shared utilities
    └── errors.py       # Custom exceptions
```

## Key Principles

1. **Domain-Driven**: Core business logic in `domain/` is pure Python with no external dependencies
2. **Dependency Inversion**: Application layer defines ports (interfaces), infrastructure implements them
3. **Testability**: Easy to mock ports for unit testing
4. **Extensibility**: New LLM providers or parsers just implement existing ports
5. **Type Safety**: Full type hints throughout

## Installation

```bash
pip install -e .
```

## Usage

### Interactive Mode
```bash
coding-agent file1.py file2.py
```

### Single Message Mode
```bash
coding-agent -m "Add error handling to the function" file.py
```

### Specify Model
```bash
coding-agent --model gpt-4o-mini -m "Refactor this" file.py
```

### Run as Module
```bash
python -m coding_agent file.py
```

## Configuration

Create a `.env` file:

```env
OPENAI_API_KEY=your_key_here
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2000
```

Or use environment variables directly.

## Adding New LLM Providers

1. Implement `LLMPort` interface:

```python
from coding_agent.application.ports.llm_port import LLMPort, Message, Response

class ClaudeClient(LLMPort):
    async def complete(self, messages: List[Message]) -> Response:
        # Implementation
        pass

    def count_tokens(self, text: str) -> int:
        # Implementation
        pass

    async def health_check(self) -> bool:
        # Implementation
        pass
```

2. Register in `config/container.py`

## Domain Models

### Symbol
Represents code symbols (functions, classes, variables):
```python
Symbol(
    name="my_function",
    line=42,
    symbol_type=SymbolType.FUNCTION,
    signature="my_function(arg1, arg2)",
    file_path=Path("module.py")
)
```

### Edit
Represents a code change:
```python
Edit(
    file_path=Path("module.py"),
    operation=OperationType.SEARCH_REPLACE,
    search="old_code",
    replace="new_code"
)
```

## Development

### Running Tests
```bash
pytest
```

### Type Checking
```bash
mypy coding_agent
```

### Linting
```bash
ruff check coding_agent
```

## Architecture Benefits

- **Extensibility**: New LLM providers implement `LLMPort` without touching business logic
- **Testability**: Mock ports for unit testing - no real API calls or filesystem needed
- **Maintainability**: Clear layer boundaries, focused modules (~80 lines average)
- **Type Safety**: Full type hints throughout with Pydantic validation
- **Configuration**: Centralized settings with environment variable support
