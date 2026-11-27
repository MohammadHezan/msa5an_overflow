/** Pure helpers for the university-verification screens (kept separate so they can be unit tested). */
import { ApiError } from './api';

export const CODE_DIGITS = 6;

/** Whole seconds left until an ISO 8601 instant, never negative. */
export function secondsUntil(iso: string, nowMs: number = Date.now()): number {
  const at = Date.parse(iso);
  if (Number.isNaN(at)) return 0;
  return Math.max(0, Math.ceil((at - nowMs) / 1000));
}

/** 272 → "04:32". */
export function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/** Keep only digits, at most six. */
export function cleanCode(value: string): string {
  return value.replace(/\D/g, '').slice(0, CODE_DIGITS);
}

/** Client-side shape check before calling the server; the server still checks the exact domain. */
export function looksLikeEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim());
}

/** Plain-language title for a verification failure. */
export function verificationErrorTitle(error: ApiError): string {
  switch (error.code) {
    case 'offline':
    case 'timeout':
      return "You're offline";
    case 'email_not_university':
      return 'Use your university email';
    case 'campus_unavailable':
      return 'Campus not available yet';
    case 'verification_resend_too_soon':
      return 'Please wait a moment';
    case 'verification_code_invalid':
      return 'That code is incorrect';
    case 'verification_code_expired':
      return 'Code expired';
    case 'verification_locked':
      return 'Too many attempts';
    case 'verification_not_started':
      return 'Start again';
    case 'invalid_input':
      return 'Check your details';
    default:
      return "Couldn't verify";
  }
}

/** True when the current code can no longer be used and the student must request a new one. */
export function needsNewCode(error: ApiError): boolean {
  return error.code === 'verification_code_expired' || error.code === 'verification_locked';
}
