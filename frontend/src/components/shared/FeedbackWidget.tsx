import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Star, X, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";

const categoryOptions = [
  { value: "general", label: "General" },
  { value: "bug", label: "Bug Report" },
  { value: "feature", label: "Feature Request" },
  { value: "ui", label: "UI/UX" },
  { value: "performance", label: "Performance" },
];

export default function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoveredStar, setHoveredStar] = useState(0);
  const [category, setCategory] = useState("");
  const [feedback, setFeedback] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit() {
    // In production this would call an API
    setSubmitted(true);
    setTimeout(() => {
      setOpen(false);
      // Reset after close animation
      setTimeout(() => {
        setRating(0);
        setCategory("");
        setFeedback("");
        setSubmitted(false);
      }, 300);
    }, 1500);
  }

  function handleClose() {
    setOpen(false);
    setTimeout(() => {
      setRating(0);
      setCategory("");
      setFeedback("");
      setSubmitted(false);
    }, 300);
  }

  const isValid = rating > 0 && category && feedback.trim().length > 0;

  return (
    <>
      {/* Floating button */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-purple-600 to-blue-600 text-white shadow-lg shadow-purple-500/30 transition-shadow hover:shadow-xl hover:shadow-purple-500/40"
        aria-label="Share feedback"
      >
        <MessageSquare className="h-6 w-6" />
      </motion.button>

      {/* Modal overlay */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-end justify-end p-6 sm:items-center sm:justify-center"
            onClick={handleClose}
          >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

            {/* Modal content */}
            <motion.div
              initial={{ opacity: 0, y: 40, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 40, scale: 0.95 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              className="relative z-10 w-full max-w-md"
            >
              <GlassCard padding="lg" glow className="relative">
                {/* Close button */}
                <button
                  onClick={handleClose}
                  className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>

                {submitted ? (
                  /* Success state */
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="flex flex-col items-center py-8 text-center"
                  >
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10">
                      <Send className="h-8 w-8 text-emerald-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white">Thank you!</h3>
                    <p className="mt-1 text-sm text-slate-400">
                      Your feedback helps us improve.
                    </p>
                  </motion.div>
                ) : (
                  /* Feedback form */
                  <div className="space-y-5">
                    <div>
                      <h2 className="text-lg font-bold text-white">
                        Share Your Feedback
                      </h2>
                      <p className="mt-0.5 text-sm text-slate-400">
                        We'd love to hear what you think
                      </p>
                    </div>

                    {/* Star rating */}
                    <div>
                      <label className="mb-2 block text-xs font-medium text-slate-400">
                        Rating
                      </label>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((star) => {
                          const filled = star <= (hoveredStar || rating);
                          return (
                            <button
                              key={star}
                              onClick={() => setRating(star)}
                              onMouseEnter={() => setHoveredStar(star)}
                              onMouseLeave={() => setHoveredStar(0)}
                              className="rounded-lg p-1 transition-transform hover:scale-110"
                            >
                              <Star
                                className={cn(
                                  "h-7 w-7 transition-colors",
                                  filled
                                    ? "fill-amber-400 text-amber-400"
                                    : "fill-transparent text-slate-600"
                                )}
                              />
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Category select */}
                    <Select
                      label="Category"
                      options={categoryOptions}
                      value={category}
                      onChange={setCategory}
                      placeholder="Select a category"
                    />

                    {/* Feedback textarea */}
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-slate-400 pl-1">
                        Feedback
                      </label>
                      <textarea
                        value={feedback}
                        onChange={(e) => setFeedback(e.target.value)}
                        placeholder="Tell us what's on your mind..."
                        rows={4}
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none backdrop-blur-sm transition-all duration-200 placeholder:text-slate-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 resize-none"
                      />
                    </div>

                    {/* Submit */}
                    <Button
                      fullWidth
                      disabled={!isValid}
                      onClick={handleSubmit}
                      icon={<Send className="h-4 w-4" />}
                    >
                      Submit Feedback
                    </Button>
                  </div>
                )}
              </GlassCard>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
