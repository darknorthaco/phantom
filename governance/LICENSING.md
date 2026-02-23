# Phantom Licensing

## Dual-License Model

Phantom is released under a dual-license model that balances open-source accessibility with commercial viability:

### Open-Source License (MIT)
```
MIT License

Copyright (c) 2026 Dark North Co.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Commercial License
For commercial use, redistribution, or deployment in commercial products, a commercial license is required. Contact the maintainers for commercial licensing terms.

## Component Licensing

### Core Components
- **phantom_core/**: MIT + Commercial dual-license
- **installer/**: MIT + Commercial dual-license
- **ui/ui_framework/**: MIT + Commercial dual-license

### Assimilated Components
- **ui/redblue_matrix/**: Assimilated from redblue-private under dual-license terms
- **installer/modules/process_cleanup.py**: Assimilated from rm-phantom under dual-license terms
- **installer/modules/port_verifier.py**: Assimilated from rm-phantom under dual-license terms

### External Integrations

Phantom integrates with the following external tools but does **not** embed their
source code. These tools are separate projects with their own licenses.

| Tool | Repository | License | Integration |
|------|-----------|---------|-------------|
| rm-phantom | https://github.com/darknorthaco/rm-phantom | See project repository | Official Linux uninstaller — detected and invoked by `installer/phantom_uninstaller.sh` when present on PATH. Must be installed separately (e.g. `pip install rm-phantom`). |

### Example and Template Code
- **ui/examples/**: MIT license (educational and demonstration purposes)
- **docs/**: MIT license (documentation and guides)

## SPDX Headers

New source files should include SPDX license headers where practical:

```python
# SPDX-License-Identifier: MIT OR LicenseRef-Commercial
```

> **Note:** SPDX header adoption is in progress. Not all existing source files contain headers yet.

## Contributing Under Dual License

Contributors must agree to license their contributions under the dual-license terms. See CONTRIBUTING.md for details.

## Commercial Licensing

For commercial licensing inquiries:
- Enterprise deployment
- Commercial redistribution
- Support and maintenance contracts
- Custom development

Contact: [commercial licensing contact information]

## Compliance

This dual-license model ensures:
- **Open-source accessibility** for individual users and research
- **Commercial viability** for enterprise adoption
- **Legal protection** for maintainers and contributors
- **Clear licensing terms** for all use cases