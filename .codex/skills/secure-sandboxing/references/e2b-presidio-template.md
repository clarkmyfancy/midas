# E2B and Presidio Template

## Host-Side Sequence

1. Read the source file locally.
2. Run Presidio analysis and anonymization on the content stream.
3. Write the sanitized artifact to a temporary local path.
4. Upload only the sanitized artifact to the sandbox.
5. Execute the requested analysis inside the sandbox.
6. Return only the derived result to the host.

## Python Skeleton

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def scrub_text(text: str) -> str:
    findings = analyzer.analyze(text=text, language="en")
    return anonymizer.anonymize(text=text, analyzer_results=findings).text
```

```python
from e2b_code_interpreter import Sandbox

with Sandbox() as sandbox:
    sandbox.files.write("/home/user/input.csv", sanitized_csv)
    result = sandbox.run_code("import pandas as pd\n...")
```

## Regex Fallbacks

Use these only when Presidio is unavailable and note the reduced confidence.

- Email: `\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b`
- Phone: `\\b(?:\\+?1[-.\\s]?)?(?:\\(?\\d{3}\\)?[-.\\s]?)\\d{3}[-.\\s]?\\d{4}\\b`
- SSN-like: `\\b\\d{3}-\\d{2}-\\d{4}\\b`
- Credit-card-like: `\\b(?:\\d[ -]*?){13,16}\\b`

Compile with case-insensitive matching for email detection.

## Review Questions

- Was the payload sanitized before upload?
- Does the sandbox receive only the minimum required columns or text?
- Are secrets and re-identification maps kept outside the sandbox?
- Is sandbox teardown explicit?
