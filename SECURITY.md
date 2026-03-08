# Security Policy

## Supported Versions

The following language versions are actively tested in CI and receive security
attention:

| Language | Versions              |
|----------|-----------------------|
| Python   | 3.10, 3.11, 3.12      |
| Julia    | 1.10, latest stable   |

Older versions are not supported. Please upgrade to a supported version before
reporting a vulnerability.

---

## Scope

Solar Flare Detection is an educational and computational research tool. A few
points are relevant to its security surface:

- **No credentials or sensitive user data are stored.** The project does not
  handle authentication tokens, passwords, or personally identifiable
  information.
- **External API usage.** `shared/data_loader.py` fetches observational data
  at runtime from the [NOAA Space Weather Prediction Center (SWPC)](https://services.swpc.noaa.gov/json/)
  over HTTPS. No API keys are required or used.
- **No network-accessible service.** The project is a local analysis library;
  it does not expose any web server, database, or listening socket.

Vulnerabilities that could still be in scope include, but are not limited to:

- Unsafe deserialization or code execution triggered by maliciously crafted
  data returned from the NOAA SWPC API.
- Dependency vulnerabilities in packages listed in `requirements.txt` or in
  the Julia `Project.toml` manifests under `tools/`.
- Path-traversal or arbitrary-write issues in file-caching logic inside
  `shared/data_loader.py`.

---

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use one of the following private channels:

1. **GitHub Security Advisories (preferred)** — Open a draft security advisory
   directly in this repository:
   <https://github.com/dfeen87/Solar-Flare-Detection/security/advisories/new>

2. **Private e-mail** — Contact the repository owner at the GitHub username
   **dfeen87**. You can find the contact address on the
   [dfeen87 GitHub profile](https://github.com/dfeen87).

Please include as much of the following information as possible to help
reproduce and assess the issue:

- A description of the vulnerability and its potential impact.
- The affected file(s) and line numbers (if known).
- Steps to reproduce or a proof-of-concept.
- The Python or Julia version and operating system you used.
- Any suggested fix or mitigation, if you have one.

---

## Response Timeline

| Milestone                              | Target          |
|----------------------------------------|-----------------|
| Acknowledgement of report              | Within 3 days   |
| Initial assessment and severity rating | Within 7 days   |
| Fix or mitigation published            | Within 30 days  |

These are best-effort targets for a small open-source project. Critical issues
will be prioritized accordingly.

---

## Disclosure Policy

This project follows a **coordinated disclosure** model. Please allow
reasonable time for a fix to be prepared and released before any public
disclosure. We will credit reporters (with their permission) in the release
notes.
