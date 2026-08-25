import pytest
import sys
import os

# Ensure backend and laptop are on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

TEST_README_CONTENT = """# Test Project

A sample repository used for unit and grounding tests.

## Installation

Run the following command to install:

```bash
pip install test-project
```

## Configuration

Set the secret token in your environment:

```text
API_KEY=abc123
```

## Usage

Start the main application:

```bash
python app.py
```
"""


@pytest.fixture
def sample_readme_text():
    return TEST_README_CONTENT
