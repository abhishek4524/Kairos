# Offline Voice Engine Specification (Piper TTS)

## 1. Selected Voice Model
- **Model**: `en_US-lessac-medium` (`.onnx` + `.onnx.json`)
- **Sample Rate**: 22,050 Hz (16-bit Mono PCM)
- **Model Size**: ~63 MB
- **Inference Engine**: ONNX Runtime (CPU & DirectML / CUDA compatible)

## 2. Hardware Rationale (RTX 3050 6GB / 16GB RAM)
1. **Low VRAM Overhead**: In offline mode, the RTX 3050 6GB GPU is primarily allocated to `qwen2.5:7b` (requiring ~4.5GB VRAM at 4-bit quant with 8192 context). Running Piper TTS via CPU ONNX threads avoids VRAM contention entirely while delivering sub-150ms synthesis latency on modern multi-core Intel i5 processors.
2. **Natural Prosody & Tone**: `en_US-lessac-medium` delivers crisp, articulate, non-robotic pronunciation suitable for a high-intelligence personal assistant.
3. **Emotional Cadence**: Pitch and speaking rate adjustments are mapped dynamically to Piper's `--length_scale` parameter (e.g. `urgent` / `excited` = 0.85x duration, `calm` / `reassuring` = 1.15x duration).

## 3. Directory Layout & Setup
```
backend/
├── tools/
│   └── piper.exe (or system piper binary)
└── models/
    └── piper/
        ├── en_US-lessac-medium.onnx
        └── en_US-lessac-medium.onnx.json
```

## 4. Operational Fallback Chain
1. **ONLINE state**: Synthesizes speech via Microsoft `edge-tts` (`en-US-ChristopherNeural` / `hi-IN-MadhurNeural`).
2. **OFFLINE state** (or Edge-TTS failure): Seamlessly switches to local Piper TTS without latency or user disruption.
