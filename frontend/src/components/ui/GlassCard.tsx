/**
 * Kept as a re-export so the redesign did not have to touch 420 call sites.
 *
 * The component was already glass-free -- tokens and a radius -- so the name
 * was the only thing tying it to the old aesthetic. Consumers migrate to
 * `Card` opportunistically, slice by slice, and nothing breaks in between.
 */
export { Card as GlassCard, Card, SectionLabel } from "./Card";
