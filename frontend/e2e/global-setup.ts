import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Ensure admin@prosohm.com / Password@123 exists in the API database
 * (same credentials as scripts/create_admin_user.py and API smoke tests).
 *
 * Skip with E2E_SKIP_ADMIN_ENSURE=1 when using custom E2E_EMAIL / E2E_PASSWORD.
 */
export default function globalSetup(): void {
  if (process.env.E2E_SKIP_ADMIN_ENSURE === '1') {
    return;
  }

  const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
  const script = path.join(rootDir, 'scripts', 'create_admin_user.py');
  execFileSync('python', [script], {
    cwd: rootDir,
    stdio: 'inherit',
    env: process.env,
  });
}
