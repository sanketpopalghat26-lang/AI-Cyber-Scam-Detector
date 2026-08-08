# ER Diagram

Entities:
- Users(id, email, hashed_password, is_admin, created_at)
- Scans(id, user_id, input_text, result, confidence, source, created_at)
- Reports(id, user_id, scan_id, title, content, created_at)
- Logs(id, user_id, level, message, created_at)
- Feedback(id, user_id, message, created_at)

Relationships:
- Users 1:N Scans
- Users 1:N Reports
- Users 1:N Logs
- Users 1:N Feedback
