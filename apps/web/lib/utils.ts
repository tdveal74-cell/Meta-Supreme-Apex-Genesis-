import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, resolving Tailwind conflicts so the last value wins.
 *
 * `clsx` alone would leave `px-4 px-6` both in the string and let source order
 * in the stylesheet decide, which is not what a caller passing an override
 * means. `twMerge` makes the override actually override.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
