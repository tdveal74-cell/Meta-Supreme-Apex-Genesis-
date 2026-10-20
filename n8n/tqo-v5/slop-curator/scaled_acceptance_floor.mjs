/**
 * Numeric quality acceptance crosswalk (not a release decision).
 *
 * Use only for a score explicitly defined as acceptance quality, never
 * confidence, similarity, word count, canon timing or other quantitative
 * measures. Canon, evidence, approval and release gates still apply.
 */
export const UNIVERSAL_NUMERIC_FLOOR = Object.freeze({
  policyVersion: "ecosystem-quality-90-v1",
  percent: 90,
});

export function checkScaledAcceptance({ earned, maximum, scorePurpose }) {
  const base = {
    thresholdPercent: 90,
    humanApprovalRequired: true,
    releaseAuthorized: false,
  };
  if (scorePurpose !== "acceptance" || typeof earned !== "number" ||
      typeof maximum !== "number" || !Number.isSafeInteger(earned) ||
      !Number.isSafeInteger(maximum) || maximum <= 0 ||
      earned < 0 || earned > maximum) {
    return { ...base, state: "HOLD", reason: "invalid or non-acceptance score" };
  }
  // Exact integer arithmetic avoids the 89/90 boundary rounding upward.
  // Example: 18 total -> ceil(16.2) = 17.
  const required = Number((90n * BigInt(maximum) + 99n) / 100n);
  const meetsNumericFloor = earned >= required;
  return {
    ...base,
    state: meetsNumericFloor ? "MEETS_NUMERIC_FLOOR_ONLY" : "HOLD",
    earned, maximum, required, meetsNumericFloor,
    reason: meetsNumericFloor
      ? "must still pass canon, evidence, safety and human review"
      : "quality score below ecosystem-wide 90 percent minimum",
  };
}
