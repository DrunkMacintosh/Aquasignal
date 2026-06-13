// Client-side mirror of the backend's password policy (RegisterRequest in
// backend/models/schemas.py): 12+ characters, at most 72 BYTES (bcrypt cap).
// The backend re-validates everything — this only exists for instant feedback.

export const PASSWORD_MIN_CHARS = 12;
export const PASSWORD_MAX_BYTES = 72;

/** Returns a user-facing problem description, or null when the pair is fine. */
export function passwordIssue(password, confirm) {
  if (password.length < PASSWORD_MIN_CHARS) {
    return `Password must be at least ${PASSWORD_MIN_CHARS} characters.`;
  }
  if (new TextEncoder().encode(password).length > PASSWORD_MAX_BYTES) {
    return `Password is too long (${PASSWORD_MAX_BYTES}-byte limit).`;
  }
  if (password !== confirm) {
    return 'Passwords do not match.';
  }
  return null;
}
