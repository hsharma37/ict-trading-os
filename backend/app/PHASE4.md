"""
Phase 4: Execution Hardening + Automation

This module implements the fail-safe and automation layer
for the ICT Trading OS.

Key features:
- Event bus (Redis pub/sub) for cross-service communication
- Immutable audit log for every state change
- Order state machine with pre-trade validation
- Daily risk lockout and max drawdown halt
- Semi-automation: signal → suggestion → approval → execution
- Real-time alert delivery via WebSocket
- Comprehensive health checks

## Safety Contract

1. AI never executes trades autonomously
2. Daily loss limits are hardcoded and immutable
3. All execution changes are logged in the audit trail
4. Pre-trade validation runs before every order
5. Paper trading mode is available for testing

## Quick Start

```python
from app.services.suggestion_service import create_suggestion, approve_suggestion, execute_approved_suggestion
from app.services.fail_safe_service import validate_daily_risk
from app.core.event_bus import event_bus
```
