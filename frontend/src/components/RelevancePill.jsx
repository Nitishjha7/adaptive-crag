/**
 * Grader ka verdict, transparently.
 *
 * Ise chhupana aasan hota, par yahi wo faisla hai jispe poora route depend
 * karta hai. Dikhane se "kyun web pe gaya" ka jawab screen pe hi mil jaata hai.
 */
export default function RelevancePill({ score }) {
  if (!score) return null;

  const relevant = score === "yes";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${
        relevant
          ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
          : "bg-amber-500/10 text-amber-300 ring-amber-500/30"
      }`}
      title={
        relevant
          ? "Grader ne local context ko relevant maana — web call nahi hua"
          : "Grader ne local context ko insufficient maana — web fallback trigger hua"
      }
    >
      grade: {score}
    </span>
  );
}
