# Create Git Tags for Phantom Releases
# This script creates annotated tags for v1.0.0 and v1.1.0
# Run this after git becomes available in your PATH

Write-Host "Creating Git Tags for Phantom Releases..." -ForegroundColor Cyan

# Check if we're in a git repository
if (-not (Test-Path ".git")) {
    Write-Host "Error: Not in a git repository root. Please run from phantom/ directory." -ForegroundColor Red
    exit 1
}

# Get current commit
$currentCommit = git rev-parse HEAD

# Create v1.0.0 tag (for the unified distribution release)
# You may want to specify a specific commit hash if you know when v1.0.0 was completed
Write-Host "`nCreating v1.0.0 tag..." -ForegroundColor Yellow
Write-Host "This will tag the current commit. Press Ctrl+C to abort, or Enter to continue..."
Read-Host

git tag -a v1.0.0 -m "Release v1.0.0 - Initial Unified Distribution

- Unified Repository: Assimilated phantom_ptr, redblue-private, rm-phantom
- Swappable UI Framework with WebSocket/HTTP protocol adapters
- RedBlue Matrix UI (web and Android)
- Enhanced Installer/Uninstaller for Windows and Linux
- LLM Taskmaster with AI-powered task routing
- Execution Modes: Safe/Moderate/Full
- Comprehensive governance documentation
- MIT + Commercial dual-licensing

Released: 2026-02-23"

Write-Host "✓ Created v1.0.0 tag" -ForegroundColor Green

# Create v1.1.0 tag for the current state
Write-Host "`nCreating v1.1.0 tag for current commit..." -ForegroundColor Yellow
git tag -a v1.1.0 -m "Release v1.1.0 - Constitutional Pipeline (ADR-0010)

- Constitutional Pipeline with 5 discrete stages
- MemoryGuard: Pre-check RAM/VRAM/swap before routing
- ModeGate: Execution mode enforcement (AUTO/HYBRID/MANUAL)
- ModelRouter: Hardware-agnostic worker scoring
- ContextBuilder: Immutable governance prompt injection
- ApprovalGate: Final authority with audit logging
- LLM Task Master pipeline integration
- Full governance alignment with Phantom Doctrine

Released: 2026-03-02"

Write-Host "✓ Created v1.1.0 tag" -ForegroundColor Green

# List all tags
Write-Host "`nAll tags:" -ForegroundColor Cyan
git tag -l

Write-Host "`nTo push tags to remote, run:" -ForegroundColor Yellow
Write-Host "  git push origin v1.0.0" -ForegroundColor White
Write-Host "  git push origin v1.1.0" -ForegroundColor White
Write-Host "Or push all tags:" -ForegroundColor Yellow
Write-Host "  git push --tags" -ForegroundColor White
