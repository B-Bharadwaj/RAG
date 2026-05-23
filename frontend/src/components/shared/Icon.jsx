import { motion } from "motion/react";

export function RAGBotIcon({ size = 50, className = "" }) {
    return (
        <motion.div
            className={`relative ${className}`}
            style={{ width: size, height: size + 20 }}
            whileHover={{ scale: 1.05 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
        >
            {/* Glow effect */}
            {/* <motion.div
                className="absolute inset-0 rounded-3xl blur-2xl opacity-30"
                style={{
                    background: "radial-gradient(circle, #6366f1 0%, transparent 70%)",
                }}
                animate={{
                    opacity: [0.2, 0.4, 0.2],
                }}
                transition={{
                    duration: 3,
                    repeat: Infinity,
                    ease: "easeInOut",
                }}
            /> */}

            <svg
                width={size}
                height={size}
                viewBox="0 0 120 120"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="relative z-10"
            >
                {/* Bot head shadow */}
                <motion.rect
                    x="22"
                    y="32"
                    width="80"
                    height="70"
                    rx="16"
                    fill="#0f172a"
                    opacity="0.1"
                    initial={{ y: 32 }}
                    animate={{ y: [32, 34, 32] }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                />

                {/* Bot head background */}
                <motion.rect
                    x="20"
                    y="30"
                    width="80"
                    height="70"
                    rx="16"
                    fill="url(#botGradient)"
                    style={{
                        filter: "drop-shadow(0 4px 12px rgba(99, 102, 241, 0.2))",
                    }}
                    initial={{ y: 30 }}
                    animate={{ y: [30, 32, 30] }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                />

                {/* Antenna */}
                {/* <motion.line
                    x1="60"
                    y1="16"
                    x2="60"
                    y2="30"
                    stroke="url(#antennaGradient)"
                    strokeWidth="3"
                    strokeLinecap="round"
                    initial={{ y1: 16, y2: 30 }}
                    animate={{ y1: [16, 14, 16], y2: [30, 28, 30] }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                /> */}
                {/* <motion.circle
                    cx="60"
                    cy="12"
                    r="5"
                    fill="#6366f1"
                    style={{
                        filter: "drop-shadow(0 0 8px rgba(99, 102, 241, 0.6))",
                    }}
                    animate={{
                        scale: [1, 1.2, 1],
                        opacity: [0.8, 1, 0.8],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                /> */}

                {/* Eyes background */}
                <motion.circle
                    cx="42"
                    cy="52"
                    r="10"
                    fill="url(#eyeGradient)"
                    style={{
                        filter: "drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1))",
                    }}
                />
                <motion.circle
                    cx="78"
                    cy="52"
                    r="10"
                    fill="url(#eyeGradient)"
                    style={{
                        filter: "drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1))",
                    }}
                />

                {/* Pupils */}
                <motion.circle
                    cx="43"
                    cy="52"
                    r="4"
                    fill="#0f172a"
                    animate={{ scale: [1, 0.8, 1] }}
                    transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                />
                <motion.circle
                    cx="79"
                    cy="52"
                    r="4"
                    fill="#0f172a"
                    animate={{ scale: [1, 0.8, 1] }}
                    transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                />

                {/* Knowledge retrieval symbol (database stacks in left eye) */}
                <motion.g
                    initial={{ opacity: 0.6 }}
                    animate={{ opacity: [0.6, 1, 0.6] }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                        delay: 0.5,
                    }}
                >
                    <rect x="33" y="44" width="5" height="2.5" rx="1" fill="#6366f1" />
                    <rect x="33" y="48" width="5" height="2.5" rx="1" fill="#818cf8" />
                    <rect x="33" y="52" width="5" height="2.5" rx="1" fill="#a5b4fc" />
                </motion.g>

                {/* AI generation symbol (sparkle in right eye) */}
                <motion.path
                    d="M86 46l1.5 4.5 4.5 1.5-4.5 1.5-1.5 4.5-1.5-4.5-4.5-1.5 4.5-1.5z"
                    fill="url(#sparkleGradient)"
                    animate={{
                        rotate: [0, 90, 0],
                        scale: [1, 1.2, 1],
                    }}
                    transition={{
                        duration: 4,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                    style={{
                        transformOrigin: "86px 52px",
                        filter: "drop-shadow(0 0 4px rgba(251, 191, 36, 0.6))",
                    }}
                />

                {/* Mouth/Display panel */}
                <rect
                    x="32"
                    y="70"
                    width="56"
                    height="20"
                    rx="6"
                    fill="url(#displayGradient)"
                    style={{
                        filter: "drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1))",
                    }}
                />

                {/* Inner display glow */}
                <rect
                    x="34"
                    y="72"
                    width="52"
                    height="16"
                    rx="4"
                    fill="rgba(99, 102, 241, 0.05)"
                />

                {/* Text lines in display */}
                <motion.line
                    x1="40"
                    y1="77"
                    x2="68"
                    y2="77"
                    stroke="#6366f1"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: [0, 1, 0] }}
                    transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                />
                <motion.line
                    x1="40"
                    y1="83"
                    x2="78"
                    y2="83"
                    stroke="#818cf8"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: [0, 1, 0] }}
                    transition={{
                        duration: 3,
                        repeat: Infinity,
                        ease: "easeInOut",
                        delay: 0.3,
                    }}
                />

                {/* RAG flow arrow */}
                <motion.g
                    animate={{
                        x: [0, 3, 0],
                        opacity: [0.6, 1, 0.6],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                >
                    <path
                        d="M 72 77 Q 77 80 72 83"
                        stroke="#6366f1"
                        strokeWidth="2.5"
                        fill="none"
                        strokeLinecap="round"
                    />
                    <polygon points="72,83 75,81 72,79" fill="#6366f1" />
                </motion.g>

                {/* Gradient definitions */}
                <defs>
                    <linearGradient id="botGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="50%" stopColor="#8b5cf6" />
                        <stop offset="100%" stopColor="#6366f1" />
                    </linearGradient>

                    <linearGradient id="antennaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="100%" stopColor="#8b5cf6" />
                    </linearGradient>

                    <radialGradient id="eyeGradient">
                        <stop offset="0%" stopColor="#ffffff" />
                        <stop offset="100%" stopColor="#f1f5f9" />
                    </radialGradient>

                    <linearGradient id="sparkleGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#fbbf24" />
                        <stop offset="50%" stopColor="#fcd34d" />
                        <stop offset="100%" stopColor="#fbbf24" />
                    </linearGradient>

                    <linearGradient id="displayGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#1e293b" />
                        <stop offset="100%" stopColor="#0f172a" />
                    </linearGradient>
                </defs>
            </svg>
        </motion.div>
    );
}