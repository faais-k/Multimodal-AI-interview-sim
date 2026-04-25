import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { 
  FileText, 
  Mic, 
  Activity, 
  BrainCircuit, 
  MessageSquare, 
  BarChart, 
  ArrowRight,
  User,
  Github
} from 'lucide-react';
import { cn } from '@/lib/utils';

const FEATURES = [
  {
    icon: FileText,
    title: "Resume-Aware Questions",
    desc: "Parses your resume to generate questions tailored to your actual skills and projects — no generic templates."
  },
  {
    icon: Mic,
    title: "Voice Recognition",
    desc: "Speak your answers naturally. Whisper ASR provides precise transcription, filler word detection, and fluency scoring."
  },
  {
    icon: Activity,
    title: "Posture Monitoring",
    desc: "Real-time webcam posture analysis keeps you interview-ready with live feedback and post-interview trends."
  },
  {
    icon: BrainCircuit,
    title: "LLM Scoring",
    desc: "Evaluates answer quality, depth and relevance — moving far beyond simple keyword matching."
  },
  {
    icon: MessageSquare,
    title: "Adaptive Follow-ups",
    desc: "AI dynamically generates contextual follow-up questions based on the gaps in your previous answer."
  },
  {
    icon: BarChart,
    title: "Difficulty by Level",
    desc: "Fresher, intermediate, or experienced — question difficulty and depth calibrate automatically."
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
      transition: { staggerChildren: 0.1, delayChildren: 0.2 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0e] text-white selection:bg-veridian/30 overflow-hidden font-sans">
      {/* Background Gradients */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-veridian/10 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-900/10 blur-[150px]" />
        <div className="absolute top-[40%] right-[20%] w-[30%] h-[30%] rounded-full bg-indigo-900/10 blur-[100px]" />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 border-b border-white/5 backdrop-blur-md bg-[#0a0a0e]/60">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-veridian to-teal-600 rounded-xl flex items-center justify-center shadow-lg shadow-veridian/20">
              <svg width="24" height="24" viewBox="0 0 36 36" fill="none">
                <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" fill="none"/>
              </svg>
            </div>
            <span className="font-bold text-xl tracking-tight text-white">Ascent</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-white/60">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#features" className="hover:text-white transition-colors">How it works</a>
            <button onClick={handleGuest} className="hover:text-white transition-colors">Guest Login</button>
          </div>
          <div className="flex items-center gap-4">
            <Button 
              onClick={onStart}
              className="bg-white text-black hover:bg-white/90 rounded-full px-6 shadow-xl shadow-white/10 hidden sm:flex"
            >
              Start Free <ArrowRight size={16} className="ml-2" />
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-32 pb-24 lg:pt-40 lg:pb-32">
        <motion.div 
          className="max-w-4xl mx-auto text-center"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.div variants={itemVariants} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-white/80 mb-8 backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-veridian animate-pulse" />
            Open Source • AI-Powered Interview Sandbox
          </motion.div>
          
          <motion.h1 variants={itemVariants} className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-8 leading-[1.1]">
            Interview practice that <br className="hidden sm:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-veridian via-teal-400 to-blue-500">
              actually prepares you
            </span>
          </motion.h1>
          
          <motion.p variants={itemVariants} className="text-lg sm:text-xl text-white/60 mb-12 max-w-2xl mx-auto leading-relaxed">
            Multimodal AI simulator with resume-aware questions, real-time posture feedback, semantic scoring, and adaptive follow-ups — tailored to your career level.
          </motion.p>
          
          <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button 
              size="lg" 
              onClick={onStart}
              className="w-full sm:w-auto bg-gradient-to-r from-veridian to-teal-500 hover:from-veridian/90 hover:to-teal-500/90 text-white rounded-full px-8 h-14 text-base shadow-lg shadow-veridian/25 hover:scale-105 transition-transform duration-300"
            >
              Start Mock Interview <ArrowRight size={18} className="ml-2" />
            </Button>
            <Button 
              size="lg" 
              variant="outline" 
              onClick={handleGuest}
              className="w-full sm:w-auto rounded-full px-8 h-14 text-base border-white/10 hover:bg-white/5 text-white backdrop-blur-sm hover:scale-105 transition-transform duration-300"
            >
              <User size={18} className="mr-2 opacity-70" /> Continue as Guest
            </Button>
          </motion.div>

          <motion.div variants={itemVariants} className="mt-20 pt-10 border-t border-white/5 flex flex-wrap justify-center gap-8 sm:gap-16 opacity-60 grayscale hover:grayscale-0 transition-all duration-500">
            <div className="flex items-center gap-2"><span className="font-bold text-xl">Gemini API</span></div>
            <div className="flex items-center gap-2"><span className="font-bold text-xl">MediaPipe</span></div>
            <div className="flex items-center gap-2"><span className="font-bold text-xl">Whisper ASR</span></div>
            <div className="flex items-center gap-2"><span className="font-bold text-xl">React Flow</span></div>
          </motion.div>
        </motion.div>
      </main>

      {/* Features Section */}
      <section id="features" className="relative z-10 py-24 bg-black/40 border-y border-white/5 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-20">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-4">Everything for a real interview experience</h2>
            <p className="text-white/50 max-w-2xl mx-auto">Advanced multimodal capabilities that simulate a rigorous technical screen.</p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, idx) => (
              <motion.div 
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1, duration: 0.5 }}
                className="group relative p-8 rounded-3xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] hover:border-white/10 transition-colors overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-veridian/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-6 text-veridian group-hover:scale-110 group-hover:bg-veridian/20 transition-all duration-300">
                    <feature.icon size={24} strokeWidth={1.5} />
                  </div>
                  <h3 className="text-xl font-semibold mb-3 text-white">{feature.title}</h3>
                  <p className="text-white/50 leading-relaxed text-sm">
                    {feature.desc}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 py-32 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-veridian/10" />
        <div className="max-w-4xl mx-auto px-6 text-center relative z-10">
          <h2 className="text-4xl sm:text-5xl font-bold mb-8">Ready to sharpen your edge?</h2>
          <Button 
            size="lg" 
            onClick={onStart}
            className="bg-white text-black hover:bg-white/90 rounded-full px-10 h-14 text-lg font-medium shadow-2xl shadow-white/20 hover:scale-105 transition-transform duration-300"
          >
            Start Your Interview <ArrowRight size={20} className="ml-2" />
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 py-12 text-center text-sm text-white/40">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 36 36" fill="none">
              <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" fill="none"/>
            </svg>
            <span className="font-semibold text-white/80">Ascent</span>
          </div>
          <p>Open source • MIT License</p>
        </div>
      </footer>
    </div>
  );
}
