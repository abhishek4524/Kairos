/**
 * parameterCalculator.js — Mathematical Parameter Calculator & Neural Dimension Mapper
 *
 * Accurately calculates parameter counts for Transformer architectures:
 * - Embedding parameters (vocabSize * hiddenSize, account for tied embeddings)
 * - Self-Attention / Multi-Head / Grouped-Query Attention (Q, K, V, O projections)
 * - MLP / Feed-Forward Layers (SwiGLU: gate + up + down, or standard: up + down)
 * - Layer Normalization / RMSNorm (pre-attn, pre-mlp, final)
 * - Output Head (hiddenSize * vocabSize if untied)
 *
 * Maps calculated parameters to GPU-safe visual dimensions (radii, layer groups, node counts, density).
 */

export const PRESET_MODELS = {
  'groq/compound': {
    name: 'Groq Compound (Llama 3.3 70B Engine)',
    architecture: 'transformer',
    vocabSize: 128256,
    hiddenSize: 8192,
    numLayers: 80,
    numAttentionHeads: 64,
    numKVHeads: 8,
    intermediateSize: 28672,
    tieWordEmbeddings: false,
    activation: 'swiglu',
    normType: 'rmsnorm',
    contextWindow: 131072,
  },
  'meta/llama-3.1-8b-instruct': {
    name: 'Llama 3.1 8B Instruct',
    architecture: 'transformer',
    vocabSize: 128256,
    hiddenSize: 4096,
    numLayers: 32,
    numAttentionHeads: 32,
    numKVHeads: 8,
    intermediateSize: 14336,
    tieWordEmbeddings: false,
    activation: 'swiglu',
    normType: 'rmsnorm',
    contextWindow: 131072,
  },
  'meta/llama-3.1-70b-instruct': {
    name: 'Llama 3.1 70B Instruct',
    architecture: 'transformer',
    vocabSize: 128256,
    hiddenSize: 8192,
    numLayers: 80,
    numAttentionHeads: 64,
    numKVHeads: 8,
    intermediateSize: 28672,
    tieWordEmbeddings: false,
    activation: 'swiglu',
    normType: 'rmsnorm',
    contextWindow: 131072,
  },
  'llama-1b': {
    name: 'Llama 3.2 1B (Edge)',
    architecture: 'transformer',
    vocabSize: 128256,
    hiddenSize: 2048,
    numLayers: 16,
    numAttentionHeads: 32,
    numKVHeads: 8,
    intermediateSize: 8192,
    tieWordEmbeddings: true,
    activation: 'swiglu',
    normType: 'rmsnorm',
    contextWindow: 131072,
  },
  'frontier-1t-moe': {
    name: 'Frontier 1T MoE System',
    architecture: 'moe-transformer',
    vocabSize: 256000,
    hiddenSize: 12288,
    numLayers: 128,
    numAttentionHeads: 96,
    numKVHeads: 16,
    intermediateSize: 32768,
    tieWordEmbeddings: false,
    activation: 'swiglu',
    normType: 'rmsnorm',
    numExperts: 16,
    activeExperts: 2,
    contextWindow: 1000000,
  }
};

/**
 * Calculates exact parameter breakdown from model hyperparameters.
 */
export function calculateModelParameters(config) {
  if (!config) return null;

  const vocabSize = config.vocabSize ?? 128256;
  const hiddenSize = config.hiddenSize ?? 4096;
  const numLayers = config.numLayers ?? 32;
  const numAttentionHeads = config.numAttentionHeads ?? 32;
  const numKVHeads = config.numKVHeads ?? numAttentionHeads;
  const intermediateSize = config.intermediateSize ?? Math.round((8 / 3) * hiddenSize);
  const tieWordEmbeddings = config.tieWordEmbeddings ?? false;
  const isSwiGLU = (config.activation ?? 'swiglu').toLowerCase().includes('swiglu');
  const numExperts = config.numExperts ?? 1;

  const headDim = Math.floor(hiddenSize / numAttentionHeads);

  // 1. Embeddings: Token embeddings
  const embeddingParams = vocabSize * hiddenSize;

  // 2. Attention Projections per layer:
  // Q: hiddenSize * (numAttentionHeads * headDim) = hiddenSize * hiddenSize
  // K: hiddenSize * (numKVHeads * headDim)
  // V: hiddenSize * (numKVHeads * headDim)
  // O: (numAttentionHeads * headDim) * hiddenSize = hiddenSize * hiddenSize
  const qProj = hiddenSize * (numAttentionHeads * headDim);
  const kProj = hiddenSize * (numKVHeads * headDim);
  const vProj = hiddenSize * (numKVHeads * headDim);
  const oProj = (numAttentionHeads * headDim) * hiddenSize;
  const attentionPerLayer = qProj + kProj + vProj + oProj;
  const totalAttentionParams = numLayers * attentionPerLayer;

  // 3. MLP / Feedforward per layer:
  // SwiGLU uses 3 matrices (gate_proj, up_proj, down_proj)
  // Standard MLP uses 2 matrices (up_proj, down_proj)
  const mlpMatricesCount = isSwiGLU ? 3 : 2;
  const mlpPerLayerPerExpert = mlpMatricesCount * hiddenSize * intermediateSize;
  const totalMlpParams = numLayers * (mlpPerLayerPerExpert * numExperts);

  // 4. Layer Normalizations (RMSNorm: 1 parameter per dimension per norm)
  // 2 per layer (input_norm, post_attention_norm) + 1 final norm
  const normParams = (numLayers * 2 + 1) * hiddenSize;

  // 5. Output LM Head (if untied from embeddings)
  const outputParams = tieWordEmbeddings ? 0 : (hiddenSize * vocabSize);

  // Total Parameters
  const totalParams = embeddingParams + totalAttentionParams + totalMlpParams + normParams + outputParams;

  return {
    totalParams,
    formattedTotal: formatParameterCount(totalParams),
    breakdown: {
      embedding: embeddingParams,
      attention: totalAttentionParams,
      mlp: totalMlpParams,
      normalization: normParams,
      outputHead: outputParams,
    },
    percentages: {
      embedding: ((embeddingParams / totalParams) * 100).toFixed(1),
      attention: ((totalAttentionParams / totalParams) * 100).toFixed(1),
      mlp: ((totalMlpParams / totalParams) * 100).toFixed(1),
      normalization: ((normParams / totalParams) * 100).toFixed(1),
      outputHead: ((outputParams / totalParams) * 100).toFixed(1),
    },
    config: {
      ...config,
      vocabSize,
      hiddenSize,
      numLayers,
      numAttentionHeads,
      numKVHeads,
      intermediateSize,
      tieWordEmbeddings,
    }
  };
}

export function formatParameterCount(params) {
  if (params >= 1e12) return `${(params / 1e12).toFixed(2)}T`;
  if (params >= 1e9)  return `${(params / 1e9).toFixed(2)}B`;
  if (params >= 1e6)  return `${(params / 1e6).toFixed(2)}M`;
  if (params >= 1e3)  return `${(params / 1e3).toFixed(2)}K`;
  return params.toString();
}

/**
 * Maps calculated parameters nonlinearly (logarithmic scale) to GPU-safe 3D visual parameters.
 * Ensures smooth 60fps rendering across 1B, 7B, 70B, 1T models without blowing up geometry.
 */
export function mapParametersToVisualSpecs(calculatedParams, qualityTier = 'high') {
  const total = calculatedParams?.totalParams ?? 7e9;
  const numLayers = calculatedParams?.config?.numLayers ?? 32;

  // Quality multiplier for device scaling
  const qMult = qualityTier === 'low' ? 0.45 : (qualityTier === 'medium' ? 0.75 : 1.0);

  // Log scale: 1B = ~9.0, 7B = ~9.84, 70B = ~10.84, 1T = ~12.0
  const logVal = Math.log10(Math.max(1e8, total));
  // Normalized 0 (100M) to 1 (1T)
  const normT = Math.min(1.0, Math.max(0.0, (logVal - 8.0) / 4.0));

  // 1. Overall outer radius (visual scale in Three.js world units)
  const baseRadius = 2.4 + normT * 1.8; // 2.4 to 4.2 units
  const coreRadius = 0.6 + normT * 0.4; // 0.6 to 1.0 units

  // 2. Visual Layer Groups (compressing actual e.g. 32-128 layers into 6-14 visible shells)
  const visualLayersCount = Math.min(14, Math.max(6, Math.round(6 + normT * 8)));

  // 3. Node budget (capped for performance: 800 for 1B up to 3600 for 1T on high quality)
  const maxNodes = Math.round((750 + normT * 2600) * qMult);

  // 4. Connection budget (lines)
  const maxConnections = Math.round((1200 + normT * 3800) * qMult);

  // 5. Signal pulse particle budget
  const particleCount = Math.round((180 + normT * 420) * qMult);

  // 6. Cluster count (attention/mlp representation hubs)
  const clusterCount = Math.min(18, Math.max(6, Math.round(6 + normT * 12)));

  // 7. Activity capacity (how many simultaneous energy flows can trigger)
  const activityCapacity = Math.round(4 + normT * 12);

  return {
    baseRadius,
    coreRadius,
    visualLayersCount,
    nodeCount: maxNodes,
    connectionCount: maxConnections,
    particleCount,
    clusterCount,
    activityCapacity,
    normT,
    qualityTier,
  };
}
