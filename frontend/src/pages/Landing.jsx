import { motion } from "framer-motion";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Mic,
  Activity,
  BrainCircuit,
  MessageSquare,
  BarChart,
  ArrowRight,
  User,
} from "lucide-react";

const FEATURES = [
  {
    icon: FileText,
    title: "Resume-Aware Questions",
    desc: "Parses your resume to generate questions tailored to your actual skills and projects.",
  },
  {
    icon: Mic,
    title: "Voice Recognition",
    desc: "Speak naturally with Whisper transcription, filler word detection, and fluency scoring.",
  },
  {
    icon: Activity,
    title: "Posture Monitoring",
    desc: "Webcam posture analysis gives live feedback and post-interview trends.",
  },
  {
    icon: BrainCircuit,
    title: "LLM Scoring",
    desc: "Evaluates answer quality, depth, and relevance beyond simple keyword matching.",
  },
  {
    icon: MessageSquare,
    title: "Adaptive Follow-ups",
    desc: "Generates contextual follow-up questions based on gaps in your previous answer.",
  },
  {
    icon: BarChart,
    title: "Difficulty by Level",
    desc: "Fresher, intermediate, or experienced: question depth calibrates automatically.",
  },
];

export default function Landing({ onStart, onGuestLogin }) {
  const { loginAsGuest } = useAuth();

  const handleGuest = () => {
    loginAsGuest();
    onGuestLogin();
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.08, delayChildren: 0.12 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 14 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } },
  };

  return (
    <div className="app-page selection:bg-veridian/20 overflow-hidden font-sans">
      <nav className="app-header">
        <div className="app-header-inner justify-between">
          <div className="app-brand">
            <span className="app-brand-mark">
              <svg width="18" height="18" viewBox="0 0 36 36" fill="none">
                <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="3" strokeLinejoin="round" fill="none" />
              </svg>
            </span>
            <span>Ascent</span>
          </div>

          <div className="hidden md:flex items-center gap-6 text-sm font-medium text-text-secondary">
            <a href="#features" className="hover:text-text-primary transition-colors">Features</a>
            <a href="#features" className="hover:text-text-primary transition-colors">How it works</a>
            <button onClick={handleGuest} className="hover:text-text-primary transition-colors">Guest Login</button>
          </div>

          <Button onClick={onStart} className="hidden sm:inline-flex">
            Start Free <ArrowRight size={16} />
          </Button>
        </div>
      </nav>

      <main className="app-container pt-20 pb-16 lg:pt-24 lg:pb-20">
        <motion.div
          className="max-w-4xl mx-auto text-center"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.div variants={itemVariants} className="app-kicker mb-8">
            <span className="w-2 h-2 rounded-full bg-veridian animate-pulse" />
            AI-powered interview sandbox
          </motion.div>

          <motion.h1 variants={itemVariants} className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-normal mb-8 leading-[1.08] text-text-primary">
            Interview practice that <br className="hidden sm:block" />
            <span className="text-veridian">actually prepares you</span>
          </motion.h1>

          <motion.p variants={itemVariants} className="text-base sm:text-lg text-text-secondary mb-12 max-w-2xl mx-auto leading-relaxed">
            Multimodal AI simulator with resume-aware questions, posture feedback, semantic scoring, and adaptive follow-ups tailored to your career level.
          </motion.p>

          <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="lg" onClick={onStart} className="w-full sm:w-auto">
              Start Mock Interview <ArrowRight size={18} />
            </Button>
            <Button size="lg" variant="outline" onClick={handleGuest} className="w-full sm:w-auto">
              <User size={18} /> Continue as Guest
            </Button>
          </motion.div>

          <motion.div variants={itemVariants} className="mt-16 pt-8 border-t border-border flex flex-wrap justify-center gap-4 sm:gap-6 text-sm text-text-muted">
            <span>Gemini API</span>
            <span>MediaPipe</span>
            <span>Whisper ASR</span>
            <span>React</span>
          </motion.div>
        </motion.div>
      </main>

      <section id="features" className="py-16 border-y border-border bg-surface-overlay/35">
        <div className="app-container py-0">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-normal mb-4">Everything for a real interview experience</h2>
            <p className="text-text-secondary max-w-2xl mx-auto">A focused multimodal workflow that feels like one coherent interview system.</p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, idx) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.06, duration: 0.4 }}
                className="app-card p-6 transition-colors hover:border-border-strong"
              >
                <div className="w-10 h-10 rounded-sm bg-veridian-subtle border border-veridian/20 flex items-center justify-center mb-5 text-veridian">
                  <feature.icon size={22} strokeWidth={1.7} />
                </div>
                <h3 className="text-lg font-semibold mb-2 text-text-primary">{feature.title}</h3>
                <p className="text-text-secondary leading-relaxed text-sm">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="app-container py-0 text-center">
          <h2 className="text-2xl sm:text-3xl font-semibold mb-8">Ready to sharpen your edge?</h2>
          <Button size="lg" onClick={onStart} className="px-10">
            Start Your Interview <ArrowRight size={20} />
          </Button>
        </div>
      </section>

      <footer className="border-t border-border py-8 text-sm text-text-muted">
        <div className="app-header-inner justify-between flex-col sm:flex-row">
          <div className="app-brand">
            <svg width="20" height="20" viewBox="0 0 36 36" fill="none">
              <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" fill="none" />
            </svg>
            <span>Ascent</span>
          </div>
          <p>Open source. MIT License.</p>
        </div>
      </footer>
    </div>
  );
}
