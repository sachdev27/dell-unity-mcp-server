# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do NOT create a public GitHub issue** for security vulnerabilities
2. **Email**: Send details to the repository maintainers
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Resolution Timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium: 2-4 weeks
  - Low: Next release

### Disclosure Policy

- We follow responsible disclosure practices
- Security fixes will be released before public disclosure
- Credit will be given to reporters (unless anonymity is requested)

## Security Best Practices

### Credential Management

```bash
# NEVER commit credentials to version control
# Use environment variables instead

export UNITY_HOST=your-unity-system.example.com
export UNITY_USERNAME=admin
export UNITY_PASSWORD=your-secure-password

# Or use a .env file (make sure it's in .gitignore)
```

### Environment Variables

All sensitive configuration should use environment variables:

| Variable | Description |
|----------|-------------|
| `UNITY_HOST` | Unity system hostname |
| `UNITY_USERNAME` | Unity admin username |
| `UNITY_PASSWORD` | Unity admin password |
| `UNITY_SSL_VERIFY` | SSL certificate verification (default: true) |

### Network Security

- **Use HTTPS**: Always use HTTPS when connecting to Unity
- **SSL Verification**: Enable SSL certificate verification in production
- **Network Isolation**: Run the MCP server in a trusted network zone
- **Firewall Rules**: Restrict access to port 8000 (default SSE port)

### Container Security

When running in Docker/Kubernetes:

```yaml
# Use non-root user
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false

# Limit resources
resources:
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### API Security

- Use read-only Unity accounts when possible
- Implement rate limiting for production deployments
- Monitor and log all API access
- Rotate credentials regularly

## Known Security Considerations

### SSL Certificate Verification

Setting `UNITY_SSL_VERIFY=false` disables SSL verification. This should ONLY be used:
- In development environments
- When using self-signed certificates in isolated networks

**Production Recommendation**: Always use proper SSL certificates and verification.

### Credential Exposure

The MCP server logs may contain URLs. Ensure:
- Logs are stored securely
- Log files have appropriate permissions
- Credentials are never logged

## Security Updates

Security updates are released as patch versions (e.g., 1.0.1, 1.0.2) and are announced:
- In GitHub Releases
- In CHANGELOG.md

## Audit and Compliance

This project:
- Uses dependency scanning via GitHub Dependabot
- Runs security linting in CI/CD pipeline
- Follows secure coding practices

## Contact

For security concerns, please contact the repository maintainers through GitHub.
