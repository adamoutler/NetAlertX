# Ticket: Notification for Idle Processes
## Description
Send a notification when all processes are idle.

## Tasks
- Determine how to monitor the state of all running background and foreground processes.
- Implement logic to trigger a notification when the system determines that there are no active/running jobs.
- Hook the trigger into the existing `write_notification` or similar event system.
