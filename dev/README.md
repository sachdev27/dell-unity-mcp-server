# Development Files

This folder contains development and reference files that are not part of the main package distribution.

## Contents

| File | Description |
|------|-------------|
| `ARCHITECTURE.md` | Detailed architecture documentation for Unity MCP server internals |
| `spec.yml` | Original Swagger/OpenAPI 2.0 specification from Unity |
| `convert_swagger_to_openapi.py` | Script to convert Swagger 2.0 to OpenAPI 3.0 format |

## Usage

### Converting Swagger to OpenAPI 3.0

If you need to regenerate `openapi.json` from a new Unity Swagger spec:

```bash
cd dev
python convert_swagger_to_openapi.py
```

This will read `spec.yml` and output `../openapi.json`.

## Note

These files are excluded from PyPI distribution but kept for reference and development purposes.
