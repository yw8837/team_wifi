import { safeReturnPath } from './api';
import { publicReturnPath } from './release-policy';

export function interestOnboardingPath(destination: string): string {
  const target = publicReturnPath(safeReturnPath(destination));
  return '/onboarding?returnTo=' + encodeURIComponent(target.startsWith('/onboarding') ? '/' : target);
}
