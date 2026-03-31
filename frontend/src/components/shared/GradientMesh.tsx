import { motion } from "framer-motion";

export default function GradientMesh() {
  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
      {/* Purple blob */}
      <motion.div
        animate={{
          x: [0, 80, -40, 60, 0],
          y: [0, -60, 40, -30, 0],
          scale: [1, 1.1, 0.95, 1.05, 1],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="absolute -left-32 -top-32 h-[500px] w-[500px] rounded-full bg-purple-600/[0.07] blur-[120px]"
      />

      {/* Blue blob */}
      <motion.div
        animate={{
          x: [0, -60, 50, -40, 0],
          y: [0, 50, -30, 60, 0],
          scale: [1, 0.95, 1.1, 0.98, 1],
        }}
        transition={{
          duration: 30,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="absolute -right-32 top-1/4 h-[500px] w-[500px] rounded-full bg-blue-600/[0.07] blur-[120px]"
      />

      {/* Pink blob */}
      <motion.div
        animate={{
          x: [0, 50, -60, 30, 0],
          y: [0, -40, 50, -60, 0],
          scale: [1, 1.05, 0.9, 1.08, 1],
        }}
        transition={{
          duration: 35,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="absolute -bottom-32 left-1/3 h-[500px] w-[500px] rounded-full bg-pink-600/[0.05] blur-[120px]"
      />
    </div>
  );
}
