import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Editor from '@monaco-editor/react';
import { 
  Play, Square, Terminal, Download, Copy, Check, RefreshCw, 
  X, Code, Clock, CheckCircle2, AlertCircle, FileCode, Sparkles
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_SNIPPETS = {
  python: `# Kairos Code Sandbox — Python 3
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Test execution
nums = [2, 7, 11, 15]
target = 9
result = two_sum(nums, target)
print(f"Input: nums={nums}, target={target}")
print(f"Result indices: {result} (values: {[nums[i] for i in result]})")
`,
  javascript: `// Kairos Code Sandbox — Node.js
function twoSum(nums, target) {
  const map = new Map();
  for (let i = 0; i < nums.length; i++) {
    const complement = target - nums[i];
    if (map.has(complement)) {
      return [map.get(complement), i];
    }
    map.set(nums[i], i);
  }
  return [];
}

const nums = [2, 7, 11, 15];
const target = 9;
console.log("Input:", nums, "target:", target);
console.log("Result indices:", twoSum(nums, target));
`
};

export default function CodeSandbox({ 
  onClose, 
  initialCode = '', 
  initialLanguage = 'python', 
  initialFilename = 'main.py',
  autoRun = false,
  theme = 'dark' 
}) {
  const [language, setLanguage] = useState(initialLanguage);
  const [code, setCode] = useState(initialCode || DEFAULT_SNIPPETS[initialLanguage] || DEFAULT_SNIPPETS.python);
  const [filename, setFilename] = useState(initialFilename);
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (initialCode) {
      setCode(initialCode);
      if (initialLanguage) setLanguage(initialLanguage);
      if (initialFilename) setFilename(initialFilename);
      if (autoRun) {
        handleRunCode(initialCode, initialLanguage);
      }
    }
  }, [initialCode, initialLanguage, initialFilename, autoRun]);

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    if (!code || code === DEFAULT_SNIPPETS.python || code === DEFAULT_SNIPPETS.javascript) {
      setCode(DEFAULT_SNIPPETS[newLang] || '');
    }
    setFilename(newLang === 'python' ? 'main.py' : 'main.js');
  };

  const handleRunCode = async (codeToRun = code, langToRun = language) => {
    if (isRunning) return;
    setIsRunning(true);
    setOutput({ status: 'running', stdout: '', stderr: '', execution_time_ms: 0 });

    try {
      const response = await fetch(`${API_BASE}/api/sandbox/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: codeToRun,
          language: langToRun,
          timeout: 10
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      setOutput(result);
    } catch (err) {
      setOutput({
        status: 'error',
        stdout: '',
        stderr: `Failed to execute in sandbox: ${err.message}\nMake sure backend is running.`,
        exit_code: -1,
        execution_time_ms: 0
      });
    } finally {
      setIsRunning(false);
    }
  };

  const handleSaveFile = async () => {
    // Check if inside Electron for direct workspace write
    if (typeof window !== 'undefined' && window.kavya?.writeFile) {
      const res = await window.kavya.writeFile(filename, code);
      if (res.ok) {
        alert(`File saved to workspace: ${res.path}`);
        return;
      }
    }

    // Web browser fallback: trigger download
    const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`fixed inset-0 z-50 flex flex-col bg-[var(--background)]/95 backdrop-blur-2xl p-3 md:p-6 ${theme}`}
    >
      <div className="animated-grid-bg" />

      {/* Main Container Card */}
      <div className="relative z-10 flex-1 flex flex-col glass-panel-warm rounded-3xl border border-[var(--border-gold-glow)] shadow-2xl overflow-hidden">
        
        {/* ── Top Header Toolbar ─────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-[var(--border-gold-glow)] bg-[var(--surface)] shrink-0">
          
          {/* Left: Brand & File Tag */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-400 to-rose-400 flex items-center justify-center text-slate-950 shadow-md">
              <Code size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold tracking-wider uppercase text-amber-300">
                  CODE SANDBOX // MONACO
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-300 border border-amber-400/30">
                  ISOLATED SUBPROCESS
                </span>
              </div>
              <input
                type="text"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                className="bg-transparent text-xs font-mono text-[var(--text-main)] outline-none border-b border-transparent focus:border-amber-400 transition-all w-32"
                title="Edit Filename"
              />
            </div>
          </div>

          {/* Right: Controls & Actions */}
          <div className="flex items-center gap-2">
            
            {/* Language Selector */}
            <select
              value={language}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="bg-[var(--surface-hover)] border border-[var(--border-gold-glow)] text-[var(--text-main)] text-xs font-mono font-semibold rounded-xl px-3 py-1.5 outline-none cursor-pointer hover:border-amber-400 transition-all"
            >
              <option value="python">Python 3</option>
              <option value="javascript">JavaScript (Node)</option>
            </select>

            {/* Run Button */}
            <button
              onClick={() => handleRunCode()}
              disabled={isRunning}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-xl font-mono text-xs font-bold transition-all shadow-md cursor-pointer ${
                isRunning
                  ? 'bg-amber-500/30 text-amber-300 border border-amber-400/40 animate-pulse'
                  : 'bg-gradient-to-r from-amber-400 to-amber-500 hover:brightness-110 text-slate-950'
              }`}
            >
              {isRunning ? <RefreshCw size={13} className="animate-spin" /> : <Play size={13} fill="currentColor" />}
              <span>{isRunning ? 'Running...' : 'Run Code'}</span>
            </button>

            {/* Save / Export Button */}
            <button
              onClick={handleSaveFile}
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-[var(--border-gold-glow)] cursor-pointer"
              title="Save / Export File"
            >
              <Download size={15} />
            </button>

            {/* Copy Button */}
            <button
              onClick={handleCopyCode}
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-amber-500/20 hover:text-amber-300 text-[var(--text-main)] transition-all border border-[var(--border-gold-glow)] cursor-pointer"
              title="Copy Code"
            >
              {copied ? <Check size={15} className="text-emerald-400" /> : <Copy size={15} />}
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-[var(--surface-hover)] hover:bg-rose-500/20 hover:text-rose-300 text-[var(--text-main)] transition-all border border-[var(--border-gold-glow)] cursor-pointer"
              title="Close Sandbox"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Editor & Terminal Dual Pane ───────────────────────────── */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          
          {/* Left: Monaco Editor */}
          <div className="flex-1 h-[55%] md:h-full relative overflow-hidden border-b md:border-b-0 md:border-r border-[var(--border-gold-glow)]">
            <Editor
              height="100%"
              language={language}
              value={code}
              onChange={(value) => setCode(value || '')}
              theme="vs-dark"
              options={{
                fontSize: 13,
                fontFamily: "'Fira Code', 'Courier New', monospace",
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                lineNumbers: 'on',
                automaticLayout: true,
                padding: { top: 12, bottom: 12 },
                renderLineHighlight: 'all',
                cursorBlinking: 'smooth',
                smoothScrolling: true,
                tabSize: language === 'python' ? 4 : 2
              }}
            />
          </div>

          {/* Right: Live Terminal & Output Console */}
          <div className="w-full md:w-[380px] lg:w-[440px] h-[45%] md:h-full flex flex-col bg-slate-950/90 text-slate-100 shrink-0 font-mono">
            
            {/* Terminal Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-slate-900/90 border-b border-slate-800 text-xs">
              <div className="flex items-center gap-2 text-slate-400">
                <Terminal size={14} className="text-amber-400" />
                <span className="font-bold tracking-wider">TERMINAL OUTPUT</span>
              </div>

              {output && output.status !== 'running' && (
                <div className="flex items-center gap-3 text-[11px]">
                  <span className="flex items-center gap-1 text-slate-400">
                    <Clock size={11} /> {output.execution_time_ms}ms
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    output.status === 'success' 
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                      : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  }`}>
                    {output.status === 'success' ? 'EXIT 0' : `ERR ${output.exit_code}`}
                  </span>
                </div>
              )}
            </div>

            {/* Terminal Output Body */}
            <div className="flex-1 p-4 overflow-y-auto text-xs leading-relaxed font-mono whitespace-pre-wrap selection:bg-amber-400 selection:text-slate-950">
              {isRunning ? (
                <div className="flex items-center gap-2 text-amber-300 animate-pulse py-4">
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Executing {language} script in isolated subprocess sandbox...</span>
                </div>
              ) : output ? (
                <div>
                  {output.stdout && (
                    <div className="text-emerald-300">
                      {output.stdout}
                    </div>
                  )}
                  {output.stderr && (
                    <div className="text-rose-400 mt-2 border-t border-rose-900/40 pt-2">
                      {output.stderr}
                    </div>
                  )}
                  {!output.stdout && !output.stderr && (
                    <div className="text-slate-500 italic">
                      [Process finished with no console output]
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-slate-500 flex flex-col items-center justify-center h-full text-center space-y-2">
                  <Terminal size={32} className="opacity-30" />
                  <p>Click "Run Code" or ask Kairos to test algorithms.</p>
                  <p className="text-[10px] opacity-70">Code executes safely in a sandboxed temporary environment.</p>
                </div>
              )}
            </div>

          </div>

        </div>

      </div>
    </motion.div>
  );
}
