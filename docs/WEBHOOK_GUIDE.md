# Vacation Webhook Integration Guide

This guide explains how to set up and use webhooks for vacation events in the Catcher of the Day application.

## Overview

The application can send webhook notifications when vacation events occur:
- **Vacation Added**: When a user adds a new vacation period
- **Vacation Deleted**: When a user deletes an existing vacation period

## Configuration

### Environment Variables

Add the following optional environment variables to your `.env` file:

```bash
# Vacation Webhooks (optional)
VACATION_ADDED_WEBHOOK_URL=https://hooks.slack.com/workflows/YOUR_WORKFLOW_ID
VACATION_DELETED_WEBHOOK_URL=https://hooks.slack.com/workflows/YOUR_WORKFLOW_ID
```

**Note**: If these variables are not set, the application will continue to work normally without sending webhook notifications.

## Webhook Payload

Both webhooks send a JSON payload with the following structure:

```json
{
  "event": "vacation_added",
  "user_email": "john.doe@company.com",
  "start_date": "2025-08-01",
  "end_date": "2025-08-05",
  "duration_days": "5",
  "timestamp": "2025-07-20T15:30:00.123456",
  "message": "john.doe@company.com added vacation: 2025-08-01 to 2025-08-05 (5 days)"
}
```

### Payload Fields

| Field | Type | Description |
|-------|------|-------------|
| `event` | string | Event type: `"vacation_added"` or `"vacation_deleted"` |
| `user_email` | string | Email address of the user |
| `start_date` | string | Start date in YYYY-MM-DD format |
| `end_date` | string | End date in YYYY-MM-DD format |
| `duration_days` | string | Number of vacation days (including start and end date) |
| `timestamp` | string | ISO timestamp when the event occurred |
| `message` | string | Human-readable message describing the event |

## Slack Integration

### Setting up Slack Workflows

1. **Create a Workflow**:
   - Go to your Slack workspace
   - Navigate to Tools → Workflow Builder
   - Create a new workflow
   - Choose "Webhook" as the trigger

2. **Configure the Webhook**:
   - Slack will provide a webhook URL
   - Copy this URL to your `.env` file
   - Configure the workflow to post messages to desired channels

3. **Example Slack Workflow**:
   - **Trigger**: Webhook
   - **Action**: Send message to channel
   - **Message Template**: 
     ```
     🏖️ Vacation Update: {{message}}
     📅 Dates: {{start_date}} to {{end_date}}
     👤 User: {{user_email}}
     ```

### Slack Message Examples

**Vacation Added**:
```
🏖️ Vacation Update: john.doe@company.com added vacation: 2025-08-01 to 2025-08-05 (5 days)
📅 Dates: 2025-08-01 to 2025-08-05
👤 User: john.doe@company.com
```

**Vacation Deleted**:
```
🗑️ Vacation Update: john.doe@company.com deleted vacation: 2025-08-01 to 2025-08-05 (5 days)
📅 Dates: 2025-08-01 to 2025-08-05
👤 User: john.doe@company.com
```

## Other Webhook Services

The webhooks can be used with any service that accepts HTTP POST requests with JSON payloads:

- **Microsoft Teams**: Use Incoming Webhooks connector
- **Discord**: Use Discord webhooks
- **Custom Applications**: Process the JSON payload as needed
- **Zapier/IFTTT**: Trigger automation workflows

## Error Handling

The webhook system includes robust error handling:

- **Retry Logic**: Failed requests are retried up to 3 times with exponential backoff
- **Timeout Handling**: Requests timeout after 10 seconds
- **Non-blocking**: Webhook failures don't prevent vacation operations
- **Logging**: All webhook attempts are logged for debugging

## Testing Webhooks

Use the provided test script to verify your webhook configuration:

```bash
python test_webhooks.py
```

This script will:
- Check if webhook URLs are configured
- Send test notifications
- Report success/failure status
- Show example payload structure

## Security Considerations

1. **HTTPS Only**: Always use HTTPS webhook URLs
2. **URL Protection**: Keep webhook URLs confidential
3. **Validation**: Implement webhook signature validation if supported by your service
4. **Rate Limiting**: Be aware of rate limits on the receiving service

## Troubleshooting

### Common Issues

1. **Webhook Not Firing**:
   - Check if environment variables are set correctly
   - Verify webhook URL is accessible
   - Check application logs for error messages

2. **Slack Workflow Not Triggering**:
   - Ensure workflow is published and active
   - Verify webhook URL is correct
   - Check Slack workflow execution history

3. **Timeout Errors**:
   - Webhook service may be slow or unavailable
   - Check service status
   - Consider increasing timeout in webhook configuration

### Debug Logging

Enable debug logging to see detailed webhook information:

```bash
LOG_LEVEL=DEBUG
```

This will log all webhook attempts, responses, and errors.

## Implementation Details

The webhook functionality is implemented in `vacation_webhooks.py` and integrated into the main application routes:

- **Add Vacation**: Webhook sent after successful database insertion
- **Delete Vacation**: Webhook sent after successful database deletion
- **Error Isolation**: Webhook failures don't affect core functionality

The implementation follows the same pattern as the existing Slack webhook in `catcher.py`, ensuring consistency and reliability.
