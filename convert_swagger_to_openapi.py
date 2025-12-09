#!/usr/bin/env python3
"""
Convert Dell Unity Swagger 2.0 spec to OpenAPI 3.0 JSON format.

This script reads the spec.yml from dell-swagger-page and converts it
to OpenAPI 3.0 format for use with the Unity MCP server.
"""

import json
import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def convert_swagger2_to_openapi3(swagger_spec: dict[str, Any]) -> dict[str, Any]:
    """Convert Swagger 2.0 spec to OpenAPI 3.0 format."""
    
    openapi_spec: dict[str, Any] = {
        'openapi': '3.0.3',
        'info': swagger_spec.get('info', {}),
        'servers': [
            {
                'url': 'https://{host}',
                'description': 'Dell Unity Management Server',
                'variables': {
                    'host': {
                        'default': 'unity.example.com',
                        'description': 'Unity system hostname or IP address'
                    }
                }
            }
        ],
        'tags': swagger_spec.get('tags', []),
        'paths': {},
        'components': {
            'securitySchemes': {
                'basicAuth': {
                    'type': 'http',
                    'scheme': 'basic',
                    'description': 'Basic authentication with Unity username and password'
                }
            },
            'schemas': {},
            'parameters': {},
            'responses': {}
        },
        'security': [{'basicAuth': []}]
    }
    
    # Convert definitions to components/schemas
    if 'definitions' in swagger_spec:
        openapi_spec['components']['schemas'] = swagger_spec['definitions']
    
    # Convert global parameters
    if 'parameters' in swagger_spec:
        for param_name, param_def in swagger_spec['parameters'].items():
            openapi_spec['components']['parameters'][param_name] = convert_parameter(param_def)
    
    # Convert paths
    for path, path_item in swagger_spec.get('paths', {}).items():
        openapi_spec['paths'][path] = convert_path_item(path_item)
    
    return openapi_spec


def convert_parameter(param: dict[str, Any]) -> dict[str, Any]:
    """Convert Swagger 2.0 parameter to OpenAPI 3.0 format."""
    new_param: dict[str, Any] = {
        'name': param.get('name', ''),
        'in': param.get('in', 'query'),
        'description': param.get('description', ''),
        'required': param.get('required', False)
    }
    
    # Handle schema for body parameters
    if param.get('in') == 'body':
        # Body parameters become requestBody in OpenAPI 3.0
        return param
    
    # Convert type to schema
    if 'type' in param:
        new_param['schema'] = {
            'type': param['type']
        }
        if 'format' in param:
            new_param['schema']['format'] = param['format']
        if 'enum' in param:
            new_param['schema']['enum'] = param['enum']
        if 'default' in param:
            new_param['schema']['default'] = param['default']
        if 'items' in param:
            new_param['schema']['items'] = param['items']
    elif 'schema' in param:
        new_param['schema'] = param['schema']
    
    return new_param


def convert_path_item(path_item: dict[str, Any]) -> dict[str, Any]:
    """Convert Swagger 2.0 path item to OpenAPI 3.0 format."""
    new_path_item: dict[str, Any] = {}
    
    for method in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
        if method in path_item:
            new_path_item[method] = convert_operation(path_item[method])
    
    # Copy other properties
    for key in ['summary', 'description', 'servers', 'parameters']:
        if key in path_item:
            if key == 'parameters':
                new_path_item['parameters'] = [
                    convert_parameter(p) for p in path_item['parameters']
                    if p.get('in') != 'body'
                ]
            else:
                new_path_item[key] = path_item[key]
    
    return new_path_item


def convert_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Convert Swagger 2.0 operation to OpenAPI 3.0 format."""
    new_operation: dict[str, Any] = {}
    
    # Copy simple properties
    for key in ['tags', 'summary', 'description', 'operationId', 'deprecated']:
        if key in operation:
            new_operation[key] = operation[key]
    
    # Convert parameters (excluding body)
    if 'parameters' in operation:
        new_params = []
        body_param = None
        
        for param in operation['parameters']:
            if param.get('in') == 'body':
                body_param = param
            else:
                new_params.append(convert_parameter(param))
        
        if new_params:
            new_operation['parameters'] = new_params
        
        # Convert body parameter to requestBody
        if body_param:
            new_operation['requestBody'] = {
                'description': body_param.get('description', ''),
                'required': body_param.get('required', False),
                'content': {
                    'application/json': {
                        'schema': body_param.get('schema', {'type': 'object'})
                    }
                }
            }
    
    # Convert responses
    if 'responses' in operation:
        new_operation['responses'] = {}
        for status_code, response in operation['responses'].items():
            new_response: dict[str, Any] = {
                'description': response.get('description', '')
            }
            
            # Convert schema to content
            if 'schema' in response:
                new_response['content'] = {
                    'application/json': {
                        'schema': response['schema']
                    }
                }
            
            # Copy headers
            if 'headers' in response:
                new_response['headers'] = response['headers']
            
            new_operation['responses'][str(status_code)] = new_response
    
    # Convert produces/consumes (these are now part of content types)
    # This is handled implicitly in the content type above
    
    return new_operation


def clean_html_in_descriptions(obj: Any) -> Any:
    """Recursively clean HTML tags from descriptions."""
    if isinstance(obj, dict):
        return {k: clean_html_in_descriptions(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_html_in_descriptions(item) for item in obj]
    elif isinstance(obj, str):
        # Remove HTML tags but keep the text
        cleaned = re.sub(r'<[^>]+>', ' ', obj)
        # Clean up whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    return obj


def fix_schema_refs(obj: Any) -> Any:
    """Fix $ref paths from Swagger 2.0 to OpenAPI 3.0 format."""
    if isinstance(obj, dict):
        if '$ref' in obj:
            ref = obj['$ref']
            # Convert #/definitions/X to #/components/schemas/X
            if ref.startswith('#/definitions/'):
                obj['$ref'] = ref.replace('#/definitions/', '#/components/schemas/')
        return {k: fix_schema_refs(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_schema_refs(item) for item in obj]
    return obj


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    
    swagger_path = script_dir / 'dell-swagger-page' / 'spec.yml'
    output_path = script_dir / 'unity_openapi.json'
    
    print(f"Reading Swagger 2.0 spec from {swagger_path}...")
    
    # Use ruamel.yaml with permissive settings for special characters
    yaml = YAML()
    yaml.preserve_quotes = True
    
    # Read and clean the file first
    with open(swagger_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Remove problematic special characters
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)
    
    # Parse the cleaned content
    from io import StringIO
    swagger_spec = yaml.load(StringIO(content))
    
    print(f"  Swagger version: {swagger_spec.get('swagger', 'unknown')}")
    print(f"  API version: {swagger_spec.get('info', {}).get('version', 'unknown')}")
    print(f"  Paths: {len(swagger_spec.get('paths', {}))}")
    print(f"  Tags: {len(swagger_spec.get('tags', []))}")
    print(f"  Definitions: {len(swagger_spec.get('definitions', {}))}")
    
    print("\nConverting to OpenAPI 3.0...")
    openapi_spec = convert_swagger2_to_openapi3(swagger_spec)
    
    print("Fixing schema references...")
    openapi_spec = fix_schema_refs(openapi_spec)
    
    print(f"\nWriting OpenAPI 3.0 spec to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(openapi_spec, f, indent=2)
    
    # Get stats
    total_operations = 0
    for path_item in openapi_spec['paths'].values():
        for method in ['get', 'post', 'put', 'delete', 'patch']:
            if method in path_item:
                total_operations += 1
    
    print("\nConversion complete!")
    print(f"  OpenAPI version: {openapi_spec['openapi']}")
    print(f"  Paths: {len(openapi_spec['paths'])}")
    print(f"  Operations: {total_operations}")
    print(f"  Schemas: {len(openapi_spec['components']['schemas'])}")
    print(f"  Output: {output_path}")


if __name__ == '__main__':
    main()
