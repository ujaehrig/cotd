# Weighted Selection Algorithm for Catcher of the Day

## Overview

The enhanced Catcher of the Day system uses a sophisticated weighted selection algorithm that ensures fair distribution of duties while avoiding consecutive day assignments when possible. This document describes the algorithm's design, implementation, and behavior.

## Algorithm Goals

1. **Fairness**: Distribute catcher duties evenly over time
2. **Avoid Consecutive Working Days**: Prevent the same person being selected on consecutive working days (when alternatives exist)
3. **Balance Workload**: Consider recent selection frequency
4. **Predictable Tie-Breaking**: Handle equal weights deterministically
5. **Flexibility**: Gracefully handle edge cases (vacations, single available user, etc.)

## Working Day Logic

The algorithm now considers **working days** instead of calendar days when avoiding consecutive assignments:

- **Working Days**: Monday through Friday, excluding public holidays
- **Holiday Detection**: Uses German holidays for the configured region (default: Baden-Württemberg)
- **Lookback Period**: Searches up to 7 days back to find the last working day with a selection
- **Weekend Handling**: Automatically skips Saturday and Sunday
- **Holiday Handling**: Automatically skips detected public holidays

This ensures that if someone was selected on Friday, they won't be selected again on the following Monday (assuming alternatives exist).

## Weight Calculation Formula

Each eligible user receives a weight calculated as:

```
weight = BASE_WEIGHT + days_since_last_selection - last_working_day_penalty - frequency_penalty
```

### Components

| Component | Value | Description |
|-----------|-------|-------------|
| `BASE_WEIGHT` | 100 | Starting weight for all users |
| `days_since_last_selection` | +1 per day | Encourages selecting users who haven't been chosen recently |
| `last_working_day_penalty` | -50 | Applied only if user was selected on the last working day AND alternatives exist |
| `frequency_penalty` | -5 per selection | Based on selections in last 30 days |

### Special Cases

- **Never Selected**: Users with no `last_chosen` date get +365 bonus
- **Minimum Weight**: All weights are clamped to minimum value of 1
- **No Alternatives**: Last working day penalty is NOT applied if only one user is available

## Tie-Breaking Logic

When multiple users have the same weight (rounded to 2 decimal places), the algorithm applies intelligent tie-breaking:

### Priority Order
1. **Last Selection Date**: User selected longest ago gets priority
2. **Never Selected**: Users never selected get highest priority (treated as 1900-01-01)
3. **Alphabetical Order**: Email address used as final deterministic tie-breaker

### Implementation
- Users with equal weights are grouped together
- Within each group, users are sorted by tie-breaking criteria
- Small incremental bonuses are added: 0.1, 0.05, 0.033, 0.025, etc.
- This maintains the original weight meaning while establishing clear preference order

## Selection Process

### 1. Eligibility Check
```
Available Users = Users where:
  - Available on current weekday
  - NOT on vacation today
  - NOT already selected for today
```

### 2. Weight Calculation
For each available user:
- Calculate base weight using formula above
- Apply last working day penalty if applicable
- Apply frequency penalty based on recent selections

### 3. Tie-Breaking
- Group users by weight (rounded to 2 decimal places)
- Apply tie-breaking logic within each group
- Add incremental bonuses to establish preference order

### 4. Weighted Random Selection
- Use cumulative probability method (not selection pools)
- Generate random number between 0 and total_weight
- Select user whose cumulative weight range contains the random number

## Examples

### Example 1: Normal Selection

**Users:**
- Alice: Last selected 5 days ago, 2 recent selections
- Bob: Last selected 2 days ago, 1 recent selection  
- Charlie: Never selected, 0 recent selections

**Weight Calculations:**
```
Alice:   100 + 5 + 0 - (2 × 5) = 95
Bob:     100 + 2 + 0 - (1 × 5) = 97
Charlie: 100 + 365 + 0 - (0 × 5) = 465
```

**Result:** Charlie most likely (465/557 ≈ 83%), Bob second (97/557 ≈ 17%), Alice least likely (95/557 ≈ 17%)

### Example 2: Last Working Day Penalty

**Scenario:** Bob was selected on the last working day, alternatives exist

**Weight Calculations:**
```
Alice:   100 + 5 + 0 - (2 × 5) = 95
Bob:     100 + 2 - 50 - (1 × 5) = 47  (last working day penalty applied)
Charlie: 100 + 365 + 0 - (0 × 5) = 465
```

**Result:** Charlie heavily favored, Alice preferred over Bob

### Example 3: Tie-Breaking

**Scenario:** Alice and Bob both have weight 95

**Before Tie-Breaking:**
- Alice: weight=95, last_chosen=2025-08-20
- Bob: weight=95, last_chosen=2025-08-22

**After Tie-Breaking:**
- Alice: weight=95.100 (selected earlier, gets priority)
- Bob: weight=95.050 (selected more recently)

**Result:** Alice slightly more likely to be selected

### Example 4: Edge Case - Only One User Available

**Scenario:** Only Bob available, he was selected on the last working day

**Weight Calculation:**
```
Bob: 100 + 2 + 0 - (1 × 5) = 97  (NO last working day penalty - no alternatives)
```

**Result:** Bob selected (bad luck, but unavoidable)

## Database Maintenance

### Automatic Cleanup
The system includes automatic cleanup of old selection history:

- **Retention Period**: 90 days (3x the lookback period)
- **Cleanup Frequency**: 10% chance each time a selection is made
- **Purpose**: Prevents unlimited database growth while retaining useful history

### Manual Cleanup
You can also run cleanup manually:

```bash
# See what would be cleaned up
python cleanup_selection_history.py --dry-run

# Clean up records older than 90 days (default)
python cleanup_selection_history.py

# Clean up records older than 180 days
python cleanup_selection_history.py --days 180
```

## Database Schema

### New Table: selection_history
```sql
CREATE TABLE selection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    selected_date DATE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE INDEX idx_selection_history_user_date ON selection_history(user_id, selected_date);
CREATE INDEX idx_selection_history_date ON selection_history(selected_date);
```

### Backward Compatibility
- `user.last_chosen` field is still updated for compatibility
- Existing migration scripts handle the transition

## Configuration Parameters

All parameters can be adjusted by modifying constants in the script:

```python
BASE_WEIGHT = 100                    # Starting weight for all users
LAST_WORKING_DAY_PENALTY = 50        # Penalty for consecutive working days
FREQUENCY_PENALTY_MULTIPLIER = 5     # Penalty per recent selection
LOOKBACK_DAYS = 30                   # Days to consider for frequency penalty
```

## Algorithm Properties

### Fairness
- Over time, all users will be selected roughly equally
- Users who haven't been selected recently get higher priority
- Frequency penalty prevents any user from being overloaded

### Predictability
- Same conditions always produce same weight calculations
- Tie-breaking is deterministic
- Debug mode shows exact weight calculations

### Flexibility
- Gracefully handles edge cases (single user, all on vacation, etc.)
- Last working day penalty only applied when alternatives exist
- Minimum weight ensures all users remain selectable

### Performance
- Efficient cumulative probability selection (O(n) time)
- No large memory allocations for selection pools
- Database queries optimized with indexes

## Usage

### Basic Usage
```bash
# Run with current algorithm
python catcher_weighted.py

# Dry run to see who would be selected
python catcher_weighted.py --dry-run

# Show detailed weight calculations
python catcher_weighted.py --dry-run --debug-weights
```

### Migration
```bash
# Migrate from old algorithm
python migrate_weighted_selection.py

# Test the new algorithm
python test_weighted_algorithm.py
```

### Debugging
The `--debug-weights` flag shows detailed information:
```
Weight calculations for all eligible users:
  alice@example.com: weight=95.100, last_chosen=2025-08-20, recent_selections=2, is_last_working_day=False, tie_breaker=+0.100
  bob@example.com: weight=95.050, last_chosen=2025-08-22, recent_selections=1, is_last_working_day=False, tie_breaker=+0.050
  charlie@example.com: weight=465.000, last_chosen=None, recent_selections=0, is_last_working_day=False
```

## Comparison with Previous Algorithm

| Aspect | Old Algorithm | New Weighted Algorithm |
|--------|---------------|------------------------|
| Selection Method | Oldest `last_chosen` first | Weighted random based on multiple factors |
| Consecutive Days | Not prevented | Actively avoided when possible |
| Workload Balance | Only by `last_chosen` date | Considers recent selection frequency |
| Tie Handling | Database order dependent | Intelligent tie-breaking |
| Predictability | Fully deterministic | Weighted random with deterministic tie-breaking |
| Fairness | Good long-term | Excellent short and long-term |

## Future Enhancements

Potential improvements to consider:

1. **Seasonal Adjustments**: Different weights during busy/slow periods
2. **Team Preferences**: Allow users to specify preferred/avoided days
3. **Workload Balancing**: Consider actual workload, not just selection count
4. **Machine Learning**: Learn from historical patterns to optimize weights
5. **Multi-Team Support**: Handle multiple teams with different schedules

## Troubleshooting

### Common Issues

**Issue**: Same person selected multiple days in a row
- **Cause**: Only one person available those days
- **Solution**: Check vacation schedules and weekday availability

**Issue**: Uneven distribution over time
- **Cause**: Different weekday availability patterns
- **Solution**: Adjust `FREQUENCY_PENALTY_MULTIPLIER` or `LOOKBACK_DAYS`

**Issue**: Algorithm seems to favor certain users
- **Cause**: Tie-breaking logic or weight calculation
- **Solution**: Use `--debug-weights` to examine calculations

### Debug Commands
```bash
# See weight calculations
python catcher_weighted.py --dry-run --debug-weights

# Check selection history
sqlite3 user.db "SELECT u.mail, sh.selected_date FROM selection_history sh JOIN user u ON sh.user_id = u.id ORDER BY sh.selected_date DESC LIMIT 10;"

# Check recent selection counts
sqlite3 user.db "SELECT u.mail, COUNT(*) as selections FROM user u LEFT JOIN selection_history sh ON u.id = sh.user_id AND sh.selected_date >= date('now', '-30 days') GROUP BY u.id, u.mail ORDER BY selections;"
```

---

*This algorithm ensures fair, balanced, and intelligent selection of daily catchers while maintaining flexibility for real-world constraints and edge cases.*
