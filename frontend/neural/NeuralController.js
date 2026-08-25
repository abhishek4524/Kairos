/**
 * NeuralController.js — Three.js Scene Architecture & Controller for Living AI Core
 *
 * Manages:
 * - Instanced node hierarchy (Embedding -> Attention/MLP Shells -> Deep Core)
 * - Synaptic connection line geometry
 * - Signal pulse particle systems
 * - External Memory Clusters (ChromaDB facts/documents)
 * - RAG Retrieval Beam Pathways & Ingestion Vortex
 * - Audio-reactive energy pulse modulation
 */

import * as THREE from 'three';
import { AI_STATES, STATE_VISUAL_PROFILES } from './neuralStateMachine';

export class NeuralController {
  constructor(scene, camera, visualSpecs) {
    this.scene = scene;
    this.camera = camera;
    this.specs = visualSpecs;

    this.group = new THREE.Group();
    this.scene.add(this.group);

    this.currentState = AI_STATES.IDLE;
    this.profile = STATE_VISUAL_PROFILES.IDLE;
    this.stateData = {};
    this.stateTime = 0;

    this.nodesData = [];
    this.connections = [];
    this.signalParticles = [];
    this.memoryClusters = [];
    this.retrievalBeams = [];
    this.ingestionParticles = [];

    this.audioVolume = 0;
    this.targetCoreScale = 1.0;
    this.currentCoreScale = 1.0;

    this.colorLerp = {
      primary: new THREE.Color(this.profile.primaryColor),
      secondary: new THREE.Color(this.profile.secondaryColor),
    };

    this._initCore();
    this._initNodes();
    this._initConnections();
    this._initSignalParticles();
    this._initMemoryClusters();
    this._initDustMotes();
  }

  // ── 1. Core Nucleus — clean wireframe icosahedron, no blinding glow ─────────
  _initCore() {
    // Outer wireframe shell — crisp, low detail for clear visible edges
    const coreGeo = new THREE.IcosahedronGeometry(this.specs.coreRadius, 2);
    const coreMat = new THREE.MeshBasicMaterial({
      color: this.profile.primaryColor,
      wireframe: true,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
    });
    this.coreMesh = new THREE.Mesh(coreGeo, coreMat);
    this.group.add(this.coreMesh);

    // Second inner wireframe shell — slightly smaller, rotates opposite direction
    const innerShellGeo = new THREE.OctahedronGeometry(this.specs.coreRadius * 0.65, 2);
    const innerShellMat = new THREE.MeshBasicMaterial({
      color: this.profile.secondaryColor,
      wireframe: true,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
    });
    this.innerShellMesh = new THREE.Mesh(innerShellGeo, innerShellMat);
    this.group.add(this.innerShellMesh);

    // Nucleus core — very small solid point, colored not white
    const nucleusGeo = new THREE.SphereGeometry(this.specs.coreRadius * 0.22, 10, 10);
    const nucleusMat = new THREE.MeshBasicMaterial({
      color: this.profile.primaryColor,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
    });
    this.innerCoreMesh = new THREE.Mesh(nucleusGeo, nucleusMat);
    this.group.add(this.innerCoreMesh);

    // Subtle glow halo — much lower opacity, not white, colored to match theme
    const haloGeo = new THREE.PlaneGeometry(this.specs.coreRadius * 3.5, this.specs.coreRadius * 3.5);
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    // Deep navy blue glow — not white, not cyan-blinding
    grad.addColorStop(0, 'rgba(30, 58, 95, 0.55)');
    grad.addColorStop(0.35, 'rgba(29, 78, 216, 0.2)');
    grad.addColorStop(0.7, 'rgba(15, 23, 42, 0.08)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 128, 128);

    const haloTex = new THREE.CanvasTexture(canvas);
    const haloMat = new THREE.MeshBasicMaterial({
      map: haloTex,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.haloMesh = new THREE.Mesh(haloGeo, haloMat);
    this.group.add(this.haloMesh);
  }

  // ── 2. Multi-Shell Instanced Neural Nodes ─────────────────────────────────
  _initNodes() {
    const { nodeCount, visualLayersCount, baseRadius, coreRadius, clusterCount } = this.specs;

    // Smaller node spheres — less visual noise, clearer structure
    const nodeGeo = new THREE.SphereGeometry(0.022, 6, 6);
    const nodeMat = new THREE.MeshBasicMaterial({
      color: this.profile.primaryColor,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    });

    this.nodesInstancedMesh = new THREE.InstancedMesh(nodeGeo, nodeMat, nodeCount);
    this.nodesInstancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    // Create cluster centers
    const clusters = [];
    for (let c = 0; c < clusterCount; c++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      const r = coreRadius + Math.random() * (baseRadius - coreRadius);
      clusters.push(new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
      ));
    }

    const dummy = new THREE.Object3D();
    this.nodesData = [];

    for (let i = 0; i < nodeCount; i++) {
      const layerIdx = i % visualLayersCount;
      const layerT = layerIdx / (visualLayersCount - 1); // 0 (inner) to 1 (outer)
      const shellRadius = coreRadius + layerT * (baseRadius - coreRadius);

      // Distribute on shell with organic noise and cluster attraction
      const cluster = clusters[i % clusterCount];
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);

      let pos = new THREE.Vector3(
        shellRadius * Math.sin(phi) * Math.cos(theta),
        shellRadius * Math.sin(phi) * Math.sin(theta),
        shellRadius * Math.cos(phi)
      );

      // 40% bias toward nearest cluster center for organic brain-like grouping
      pos.lerp(cluster, 0.35 + Math.random() * 0.2);

      dummy.position.copy(pos);
      const scale = 0.6 + (1.0 - layerT * 0.4) * (0.8 + Math.random() * 0.6);
      dummy.scale.set(scale, scale, scale);
      dummy.updateMatrix();

      this.nodesInstancedMesh.setMatrixAt(i, dummy.matrix);

      // Node individual color
      const color = new THREE.Color().lerpColors(
        new THREE.Color(this.profile.primaryColor),
        new THREE.Color(this.profile.secondaryColor),
        layerT
      );
      this.nodesInstancedMesh.setColorAt(i, color);

      this.nodesData.push({
        basePos: pos.clone(),
        currentPos: pos.clone(),
        layerIndex: layerIdx,
        layerT,
        clusterIndex: i % clusterCount,
        activity: Math.random() * 0.2,
        pulsePhase: Math.random() * Math.PI * 2,
        scale,
        color,
      });
    }

    this.nodesInstancedMesh.instanceMatrix.needsUpdate = true;
    if (this.nodesInstancedMesh.instanceColor) {
      this.nodesInstancedMesh.instanceColor.needsUpdate = true;
    }
    this.group.add(this.nodesInstancedMesh);
  }

  // ── 3. Synaptic Connection Lines ──────────────────────────────────────────
  _initConnections() {
    const { connectionCount, nodeCount } = this.specs;
    const positions = new Float32Array(connectionCount * 2 * 3);
    const colors = new Float32Array(connectionCount * 2 * 3);

    this.connections = [];
    const colorA = new THREE.Color(this.profile.primaryColor);
    const colorB = new THREE.Color(this.profile.secondaryColor);

    let created = 0;
    const maxAttempts = connectionCount * 6;
    let attempts = 0;

    while (created < connectionCount && attempts < maxAttempts) {
      attempts++;
      const idxA = Math.floor(Math.random() * nodeCount);
      const idxB = Math.floor(Math.random() * nodeCount);
      if (idxA === idxB) continue;

      const nodeA = this.nodesData[idxA];
      const nodeB = this.nodesData[idxB];
      const dist = nodeA.basePos.distanceTo(nodeB.basePos);

      // Connect mostly nearby nodes or intra-cluster nodes
      if (dist < 1.35 || (nodeA.clusterIndex === nodeB.clusterIndex && dist < 2.0)) {
        this.connections.push({
          idxA,
          idxB,
          activity: 0.1,
          flowPhase: Math.random() * Math.PI * 2,
        });

        const i6 = created * 6;
        positions[i6 + 0] = nodeA.basePos.x;
        positions[i6 + 1] = nodeA.basePos.y;
        positions[i6 + 2] = nodeA.basePos.z;
        positions[i6 + 3] = nodeB.basePos.x;
        positions[i6 + 4] = nodeB.basePos.y;
        positions[i6 + 5] = nodeB.basePos.z;

        colors[i6 + 0] = colorA.r * 0.3;
        colors[i6 + 1] = colorA.g * 0.3;
        colors[i6 + 2] = colorA.b * 0.3;
        colors[i6 + 3] = colorB.r * 0.3;
        colors[i6 + 4] = colorB.g * 0.3;
        colors[i6 + 5] = colorB.b * 0.3;

        created++;
      }
    }

    this.connGeometry = new THREE.BufferGeometry();
    this.connGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.connGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    this.connMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.connLines = new THREE.LineSegments(this.connGeometry, this.connMaterial);
    this.group.add(this.connLines);
  }

  // ── 4. Signal Pulse Particles ─────────────────────────────────────────────
  _initSignalParticles() {
    const { particleCount } = this.specs;
    const pGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);

    this.signalParticles = [];

    for (let i = 0; i < particleCount; i++) {
      const conn = this.connections[i % Math.max(1, this.connections.length)];
      this.signalParticles.push({
        connIndex: i % Math.max(1, this.connections.length),
        t: Math.random(),
        speed: 0.4 + Math.random() * 0.8,
        active: true,
      });

      positions[i * 3 + 0] = 0;
      positions[i * 3 + 1] = 0;
      positions[i * 3 + 2] = 0;

      colors[i * 3 + 0] = 1.0;
      colors[i * 3 + 1] = 1.0;
      colors[i * 3 + 2] = 1.0;

      sizes[i] = 0.08 + Math.random() * 0.06;
    }

    pGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    pGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const pMat = new THREE.PointsMaterial({
      size: 0.08,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.particlePoints = new THREE.Points(pGeo, pMat);
    this.group.add(this.particlePoints);
  }

  // ── 5. External Memory & Knowledge Clusters ───────────────────────────────
  _initMemoryClusters() {
    this.memoryGroup = new THREE.Group();
    this.group.add(this.memoryGroup);
    this.updateMemoryCount(12, 4); // Initial default memory + doc chunks
  }

  updateMemoryCount(factCount = 0, docChunkCount = 0) {
    // Clear old memory cluster meshes
    while (this.memoryGroup.children.length > 0) {
      const obj = this.memoryGroup.children[0];
      this.memoryGroup.remove(obj);
      obj.geometry?.dispose();
      obj.material?.dispose();
    }

    this.memoryClusters = [];
    const totalMem = Math.max(3, factCount + docChunkCount);
    const clusterOrbs = Math.min(16, Math.max(4, Math.round(totalMem / 3)));
    const orbRadius = this.specs.baseRadius * 1.35;

    for (let c = 0; c < clusterOrbs; c++) {
      const theta = (c / clusterOrbs) * Math.PI * 2 + Math.random() * 0.3;
      const phi = Math.PI * 0.3 + (c % 3) * 0.2;
      const pos = new THREE.Vector3(
        orbRadius * Math.sin(phi) * Math.cos(theta),
        orbRadius * Math.cos(phi) * 0.6,
        orbRadius * Math.sin(phi) * Math.sin(theta)
      );

      const isDoc = c % 2 === 0;
      const color = isDoc ? 0x155e75 : 0x064e3b; // Deep Teal for docs, Deep Emerald for facts

      const geo = new THREE.DodecahedronGeometry(0.12 + Math.random() * 0.08, 1);
      const mat = new THREE.MeshBasicMaterial({
        color,
        wireframe: true,
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending,
      });

      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(pos);
      this.memoryGroup.add(mesh);

      this.memoryClusters.push({
        id: `cluster_${c}`,
        mesh,
        pos,
        isDoc,
        baseOpacity: 0.65,
        targetOpacity: 0.65,
        pulse: 0,
        relevance: 0.2,
      });
    }
  }

  // ── 6. Ambient Volumetric Dust Motes — very subtle, barely visible ─────────
  _initDustMotes() {
    const moteCount = 150;
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(moteCount * 3);
    const col = new Float32Array(moteCount * 3);

    for (let i = 0; i < moteCount; i++) {
      const r = 1.0 + Math.random() * (this.specs.baseRadius * 2.2);
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);

      pos[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);

      // Very dark steel-blue dust — barely perceptible, no bright blue
      col[i * 3 + 0] = 0.06 + Math.random() * 0.08;
      col[i * 3 + 1] = 0.10 + Math.random() * 0.10;
      col[i * 3 + 2] = 0.18 + Math.random() * 0.14;
    }

    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.03,
      vertexColors: true,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.dustPoints = new THREE.Points(geo, mat);
    this.group.add(this.dustPoints);
  }

  // ── State Transition Handler ──────────────────────────────────────────────
  setState(newState, stateData = {}, profile = null) {
    this.currentState = newState;
    this.stateData = stateData;
    this.profile = profile || STATE_VISUAL_PROFILES[newState] || STATE_VISUAL_PROFILES.IDLE;
    this.stateTime = 0;

    // Trigger state-specific dynamic behaviors
    if (newState === AI_STATES.RAG_RETRIEVAL) {
      this._triggerRagRetrieval(stateData.results || []);
    } else if (newState === AI_STATES.RAG_INGESTION) {
      this._triggerRagIngestion(stateData.chunkCount || 8);
    } else if (newState === AI_STATES.TOOL_EXECUTION) {
      this._triggerToolDeformation(stateData.toolName || 'tool');
    }
  }

  _triggerRagRetrieval(results = []) {
    // Highlight relevant memory clusters with a subtle deep amber
    for (let i = 0; i < this.memoryClusters.length; i++) {
      const cl = this.memoryClusters[i];
      const match = results[i % Math.max(1, results.length)];
      const score = match?.score ?? 0.85;
      cl.targetOpacity = 0.85;
      cl.relevance = score;
      cl.mesh.material.color.setHex(0x78350f); // Deep amber (not blinding)
    }
  }

  _triggerRagIngestion(chunkCount = 6) {
    for (const cl of this.memoryClusters) {
      cl.targetOpacity = 0.9;
      cl.mesh.material.color.setHex(0x064e3b); // Deep emerald pulse
    }
  }

  _triggerToolDeformation(toolName) {
    // Subtle dark orange/crimson — no neon
    this.colorLerp.primary.set(0x7c2d12);
    this.colorLerp.secondary.set(0x881337);
  }

  setAudioVolume(vol) {
    this.audioVolume = vol;
  }

  // ── Master Render Loop Update ─────────────────────────────────────────────
  update(dt, totalTime) {
    this.stateTime += dt;
    const { primaryColor, secondaryColor, coreGlow, pulseSpeed, rotationSpeed, particleSpeed } = this.profile;

    // Lerp colors smoothly
    this.colorLerp.primary.lerp(new THREE.Color(primaryColor), dt * 3.5);
    this.colorLerp.secondary.lerp(new THREE.Color(secondaryColor), dt * 3.5);

    // 1. Group Organic Rotation
    this.group.rotation.y += dt * rotationSpeed * 0.25;
    this.group.rotation.x = Math.sin(totalTime * 0.2) * 0.08;

    // 2. Core Breathing + Audio Reactivity
    const isSpeakingAudio = this.audioVolume > 0.02;
    const audioBoost = (this.currentState === AI_STATES.GENERATING || this.currentState === AI_STATES.LISTENING || isSpeakingAudio)
      ? this.audioVolume * 0.65 : 0;
    const breath = Math.sin(totalTime * pulseSpeed) * 0.06 + audioBoost;
    this.currentCoreScale = THREE.MathUtils.lerp(this.currentCoreScale, 1.0 + breath + (coreGlow - 0.5) * 0.2, dt * 6.0);

    if (this.coreMesh) {
      this.coreMesh.scale.setScalar(this.currentCoreScale);
      this.coreMesh.rotation.y += dt * 0.45;
      this.coreMesh.rotation.z += dt * 0.25;
      this.coreMesh.material.color.copy(this.colorLerp.primary);
      this.coreMesh.material.opacity = 0.38 + Math.sin(totalTime * 2.5) * 0.12 + audioBoost * 0.25;
    }

    // Counter-rotating inner octahedron shell for clear geometric layering
    if (this.innerShellMesh) {
      this.innerShellMesh.scale.setScalar(this.currentCoreScale * 0.92);
      this.innerShellMesh.rotation.y -= dt * 0.6;
      this.innerShellMesh.rotation.x -= dt * 0.4;
      this.innerShellMesh.material.color.copy(this.colorLerp.secondary);
      this.innerShellMesh.material.opacity = 0.28 + Math.sin(totalTime * 3.5) * 0.1;
    }

    if (this.innerCoreMesh) {
      this.innerCoreMesh.scale.setScalar(this.currentCoreScale * 0.9);
      this.innerCoreMesh.material.color.copy(this.colorLerp.primary);
      this.innerCoreMesh.material.opacity = 0.45 + audioBoost * 0.3;
    }

    if (this.haloMesh && this.camera) {
      this.haloMesh.lookAt(this.camera.position);
      this.haloMesh.scale.setScalar(this.currentCoreScale);
      this.haloMesh.material.opacity = (0.25 + coreGlow * 0.18 + audioBoost * 0.2);
    }

    // 3. Update Instanced Nodes
    const dummy = new THREE.Object3D();
    const dummyColor = new THREE.Color();
    const isThinking = this.currentState === AI_STATES.THINKING;
    const isGenerating = this.currentState === AI_STATES.GENERATING || isSpeakingAudio;

    for (let i = 0; i < this.nodesData.length; i++) {
      const node = this.nodesData[i];
      node.pulsePhase += dt * pulseSpeed * (1.0 + node.layerT * 0.5);

      // Calculate radial pulsation
      let pulseAmp = 0.025;
      if (isThinking) pulseAmp = 0.06 * Math.sin(totalTime * 5.0 + node.clusterIndex);
      if (isGenerating) pulseAmp = 0.045 * Math.sin(totalTime * 3.5 - node.layerT * 3.5) + audioBoost * 0.08;

      const radialDisplacement = Math.sin(node.pulsePhase) * pulseAmp;
      dummy.position.copy(node.basePos).multiplyScalar(1.0 + radialDisplacement);

      const dynamicScale = node.scale * (1.0 + Math.sin(node.pulsePhase) * 0.2 + (isGenerating ? audioBoost * 0.35 : 0));
      dummy.scale.set(dynamicScale, dynamicScale, dynamicScale);
      dummy.updateMatrix();

      this.nodesInstancedMesh.setMatrixAt(i, dummy.matrix);

      // Node dynamic color — stays in theme palette, no white spark
      dummyColor.lerpColors(this.colorLerp.primary, this.colorLerp.secondary, node.layerT);
      if (isThinking && Math.sin(totalTime * 8.0 + node.clusterIndex) > 0.75) {
        // Subtle bright pulse within theme — not pure white
        dummyColor.lerp(new THREE.Color(0x93c5fd), 0.5); // Soft light blue instead of white
      }
      this.nodesInstancedMesh.setColorAt(i, dummyColor);
    }
    this.nodesInstancedMesh.instanceMatrix.needsUpdate = true;
    if (this.nodesInstancedMesh.instanceColor) {
      this.nodesInstancedMesh.instanceColor.needsUpdate = true;
    }

    // 4. Update Synaptic Connection Colors & Opacity
    if (this.connLines && this.connGeometry) {
      this.connMaterial.opacity = 0.25 + (this.profile.activityLevel * 0.35) + audioBoost * 0.25;
      const colors = this.connGeometry.attributes.color.array;

      for (let c = 0; c < this.connections.length; c++) {
        const conn = this.connections[c];
        conn.flowPhase += dt * particleSpeed * 2.0;
        const glow = 0.3 + Math.sin(conn.flowPhase) * 0.4;

        const i6 = c * 6;
        colors[i6 + 0] = this.colorLerp.primary.r * glow;
        colors[i6 + 1] = this.colorLerp.primary.g * glow;
        colors[i6 + 2] = this.colorLerp.primary.b * glow;
        colors[i6 + 3] = this.colorLerp.secondary.r * glow;
        colors[i6 + 4] = this.colorLerp.secondary.g * glow;
        colors[i6 + 5] = this.colorLerp.secondary.b * glow;
      }
      this.connGeometry.attributes.color.needsUpdate = true;
    }

    // 5. Update Signal Flow Particles
    if (this.particlePoints && this.particlePoints.geometry) {
      const posAttr = this.particlePoints.geometry.attributes.position.array;
      const colAttr = this.particlePoints.geometry.attributes.color.array;

      for (let p = 0; p < this.signalParticles.length; p++) {
        const sp = this.signalParticles[p];
        const conn = this.connections[sp.connIndex];
        if (!conn) continue;

        const nodeA = this.nodesData[conn.idxA];
        const nodeB = this.nodesData[conn.idxB];
        if (!nodeA || !nodeB) continue;

        // Flow direction logic based on AI state & audio speech
        if (this.profile.flowDirection === 'outward_radiant' || (this.audioVolume > 0.02)) {
          // Inner to outer
          const fromNode = nodeA.layerT < nodeB.layerT ? nodeA : nodeB;
          const toNode = nodeA.layerT < nodeB.layerT ? nodeB : nodeA;
          sp.t += dt * sp.speed * particleSpeed;
          if (sp.t > 1.0) sp.t = 0;

          const pPos = new THREE.Vector3().lerpVectors(fromNode.basePos, toNode.basePos, sp.t);
          posAttr[p * 3 + 0] = pPos.x;
          posAttr[p * 3 + 1] = pPos.y;
          posAttr[p * 3 + 2] = pPos.z;
        } else {
          // Standard / inward flow
          sp.t += dt * sp.speed * particleSpeed;
          if (sp.t > 1.0) sp.t = 0;

          const pPos = new THREE.Vector3().lerpVectors(nodeA.basePos, nodeB.basePos, sp.t);
          posAttr[p * 3 + 0] = pPos.x;
          posAttr[p * 3 + 1] = pPos.y;
          posAttr[p * 3 + 2] = pPos.z;
        }

        colAttr[p * 3 + 0] = this.colorLerp.primary.r;
        colAttr[p * 3 + 1] = this.colorLerp.primary.g;
        colAttr[p * 3 + 2] = this.colorLerp.primary.b;
      }
      this.particlePoints.geometry.attributes.position.needsUpdate = true;
      this.particlePoints.geometry.attributes.color.needsUpdate = true;
    }

    // 6. Update Memory Clusters
    if (this.memoryClusters) {
      for (const cl of this.memoryClusters) {
        cl.mesh.rotation.y += dt * 0.4;
        cl.mesh.rotation.x += dt * 0.2;
        cl.mesh.material.opacity = THREE.MathUtils.lerp(cl.mesh.material.opacity, cl.targetOpacity, dt * 4.0);

        if (this.currentState === AI_STATES.IDLE) {
          cl.targetOpacity = cl.baseOpacity;
        }
      }
    }
  }

  // ── Cleanup & Memory Disposal ─────────────────────────────────────────────
  dispose() {
    if (this.group) {
      this.scene.remove(this.group);
      this.group.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
          else obj.material.dispose();
        }
      });
    }
  }
}
