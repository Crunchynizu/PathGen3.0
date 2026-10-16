# authentication.md

Authentication and authorization for PathGen 3.0.

---

## Purpose

Covers login, sessions, roles, permissions, and access gates. Server-enforced at every layer.

---

## Identity

`accounts_user` is the custom Django user model.

| Field | Rule |
|---|---|
| username | unique, immutable |
| password | Django hash only |
| role | `admin` / `teacher` / `student` + CHECK |
| is_active | account lifecycle |
| first_name, last_name | editable by owner or permitted admin |
| is_staff, is_superuser | Django flags only — never replace role checks |

Role changes are not an ordinary workflow.

Admin accounts are created only via `bootstrap_admin` command. Never through product UI.

---

## Login

`pages/account/login.html` accepts username + password over HTTPS with CSRF.

Uses:
- Django authentication
- Password hashers
- Constant-time checks
- Session rotation
- Generic invalid-credential message
- Safe `next` URL validation

**Never reveals:** whether a username exists, is inactive, or has a particular role.

### Login flow

```
Valid credentials?
    No  → Generic error
    Yes → Account active?
              No  → Generic invalid-credential message + security audit
              Yes → Student role?
                        No  → Role dashboard
                        Yes → Study Access open?
                                  No  → Access-closed state
                                  Yes → Student dashboard
```

Class membership is never checked at login.

---

## Authorization model

Three layers:

| Layer | What it checks |
|---|---|
| Authentication | Valid active session |
| Role permission | Route/action allowed for the role |
| Object scope | Requested object belongs to the caller's scope |

Views and services filter authorized querysets before object lookup.

| Role | Scope |
|---|---|
| Admin | Global, read-only on evidence |
| Teacher | Assigned classes and their students, read-only |
| Student | Own path, sessions, results, feedback |

Hidden controls are not security.

Unauthorized requests → non-disclosing 403 or 404.

A locked step, zero-class teacher, no-class student, or closed post-test gate is an in-page state — not `error.html`.

---

## Student learning gates

Every student start/resume/submit rechecks:

- Active student account
- Student Study Access open
- Object ownership
- Authoritative `learning_student_path` stage/status
- Session status and issued item
- Submitted choice belongs to current question
- Post-test requires both `posttest_access_enabled=true` and path `posttest_ready`

Access switches never change scores, BKT, Q-Learning decisions, feedback, or path state.

---

## Logout and sessions

| Rule | Detail |
|---|---|
| Logout | CSRF-protected POST via `modals/auth/logout_confirm.html` |
| GET logout | Not allowed |
| Session cookies | Secure (prod), HttpOnly, SameSite, narrow scope |
| Absolute age | Configured, documented as security not engagement |
| Idle age | Configured, same |
| Deactivation | Invalidates all sessions for target account |
| Password change | Rotates or invalidates other sessions; current session preserved after Django hash update |

---

## Account changes

`pages/account/my_account.html` — self-service:

| Change | Allowed |
|---|---|
| Own first/last name | Yes (trimmed, validated) |
| Own password | Yes (current password + validation + confirmation) |
| Username | No |
| Role | No |

Admins may update names/email for teacher/student accounts and deactivate/reactivate through dedicated services. Username and role remain immutable.

Deactivation requires: reason, actor, timestamp, audit event, session invalidation.

Reactivation clears lifecycle fields but does not bypass Study Access.

Permanent deletion only for an already inactive unused mistake with no protected history. Otherwise rejected — anonymization is the alternative.

---

## CSRF, redirects, request safety

- All mutations are POST with CSRF tokens
- Post/Redirect/Get on success
- Allowlisted methods and content types
- Host and origin validation
- HTTPS proxy config in production
- Secure cookies
- Clickjacking protection
- Template escaping
- Safe `next` URL validation
- Cache-control on sensitive responses

Never in URLs: tokens, reasons, usernames, answers, provider keys, student identifiers.

---

## Rate limiting

Applied to:

- Login attempts
- Password changes
- Global override submissions
- Repeated invalid assessment submissions

Privacy-conscious combination of account identifier + source. Progressive delay and temporary window. No permanent lockout that enables DoS.

Stored in PostgreSQL via `core_audit_event` — no Redis or external service.

Limits never change assessment results and never count page refreshes as learning evidence.

---

## Audit events

Write immutable, minimized `core_audit_event` rows for:

| Event | Reason required |
|---|---|
| Successful login (if policy) | No |
| Failed sensitive authentication | No |
| Account create/deactivate/reactivate | Yes for deactivate |
| Anonymization / permitted deletion | Yes |
| Password change | No (never log values) |
| Admin bootstrap | No |
| Role/security change | Yes |
| Global access override | Yes |
| Session reset | Yes |

Fields: stable action code, safe target snapshot, reason (where required), timestamp, actor/system identity.

Append-only. Immutable. Enforced by DB trigger.

---

## Failure and recovery states

| Situation | Behavior |
|---|---|
| Invalid login | Generic message, no enumeration |
| Inactive account | Generic invalid-credential message, no disclosure |
| Closed Study Access (student) | Clear policy state |
| Expired session | Redirect to login, safe continuation |
| Deactivated mid-session | Next request fails closed, session cleared |
| CSRF failure | Standard safe page, no secret echo |
| Permission lost (teacher reassign) | Deny object, return to My Classes |
| Stale override revision | 409, reload current |

All states keyboard-accessible, zoom-safe, announced to assistive tech, never color-only.

---

## Acceptance checks

- Each role reaches only its documented destinations
- Students with no class can log in and learn
- Study Access blocks students only
- Post-test requires both global access and path eligibility
- Admin creation absent from product UI and rejected server-side
- Deactivation and password changes invalidate sessions as configured
- CSRF, safe redirects, password validation, and generic login errors tested
- Protected history prevents destructive deletion
- Every sensitive lifecycle action is audited

---

**End of reference.**
