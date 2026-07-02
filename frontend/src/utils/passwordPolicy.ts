export const PASSWORD_REQUIREMENTS_MESSAGE =
  'Password must be at least 8 characters and include uppercase, lowercase, number, and special character.';

const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$/;

export function validatePasswordStrength(password: string): string | null {
  if (!PASSWORD_PATTERN.test(password)) {
    return PASSWORD_REQUIREMENTS_MESSAGE;
  }
  return null;
}
