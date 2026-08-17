/**
 * RoomEnvironment.js — Stylized 3D Room Environment for Kavya
 * 
 * Contains:
 *  - Floor plane & minimalist architectural backdrop
 *  - Wooden desk/table with sleek metal legs
 *  - Stylized chair
 *  - Bookshelf with multi-colored books
 *  - Interactive Desk Lamp with toggleable PointLight & Emissive Bulb mesh
 * 
 * Highly optimized: reuses materials, low polygon counts, 0 per-frame allocations.
 */

import * as THREE from 'three';

export class RoomEnvironment {
  constructor(scene, isDark = true) {
    this.scene = scene;
    this.isDark = isDark;
    this.group = new THREE.Group();
    this.isLampOn = true;

    this.materials = {};
    this.geometries = [];
    this.lampBulbMesh = null;
    this.lampPointLight = null;
    this.lampGlowMesh = null;

    this.initMaterials();
    this.buildRoom();
    this.scene.add(this.group);
  }

  initMaterials() {
    // Shared materials for low draw calls & high performance
    this.materials.floor = new THREE.MeshStandardMaterial({
      color: this.isDark ? 0x12131c : 0xe8e2d8,
      roughness: 0.85,
      metalness: 0.1,
    });

    this.materials.wood = new THREE.MeshStandardMaterial({
      color: this.isDark ? 0x422a1d : 0x8a6042,
      roughness: 0.65,
      metalness: 0.05,
    });

    this.materials.darkMetal = new THREE.MeshStandardMaterial({
      color: 0x22252e,
      roughness: 0.4,
      metalness: 0.8,
    });

    this.materials.goldMetal = new THREE.MeshStandardMaterial({
      color: 0xd4af37,
      roughness: 0.3,
      metalness: 0.9,
    });

    this.materials.chairSeat = new THREE.MeshStandardMaterial({
      color: this.isDark ? 0x1e2230 : 0xd1c7b7,
      roughness: 0.7,
      metalness: 0.1,
    });

    this.materials.bookColors = [
      new THREE.MeshStandardMaterial({ color: 0x06b6d4, roughness: 0.6 }), // Cyan
      new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.6 }), // Amber
      new THREE.MeshStandardMaterial({ color: 0xec4899, roughness: 0.6 }), // Rose
      new THREE.MeshStandardMaterial({ color: 0x8b5cf6, roughness: 0.6 }), // Violet
      new THREE.MeshStandardMaterial({ color: 0x10b981, roughness: 0.6 }), // Emerald
    ];

    // Lamp Bulb Material (Emissive when ON)
    this.materials.bulbOn = new THREE.MeshStandardMaterial({
      color: 0xfff0d0,
      emissive: 0xffb84d,
      emissiveIntensity: 2.2,
      roughness: 0.2,
    });

    this.materials.bulbOff = new THREE.MeshStandardMaterial({
      color: 0x555555,
      emissive: 0x000000,
      emissiveIntensity: 0,
      roughness: 0.8,
    });

    this.materials.lampShade = new THREE.MeshStandardMaterial({
      color: 0x181a24,
      roughness: 0.5,
      metalness: 0.6,
    });
  }

  buildRoom() {
    // ── 1. Floor Plane ──────────────────────────────────────────────────────────
    const floorGeo = new THREE.PlaneGeometry(16, 16);
    this.geometries.push(floorGeo);
    const floor = new THREE.Mesh(floorGeo, this.materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, 0, 0);
    floor.receiveShadow = true;
    this.group.add(floor);

    // ── 2. Minimalist Desk / Table (Placed slightly to the right of Kavya) ───────
    // Desk Top (width: 1.4m, depth: 0.65m, height: 0.04m, table height: 0.72m)
    const tableX = 0.85;
    const tableZ = 0.05;
    const tableTopY = 0.72;

    const deskTopGeo = new THREE.BoxGeometry(1.3, 0.04, 0.65);
    this.geometries.push(deskTopGeo);
    const deskTop = new THREE.Mesh(deskTopGeo, this.materials.wood);
    deskTop.position.set(tableX, tableTopY, tableZ);
    this.group.add(deskTop);

    // Desk Legs (4 sleek metal legs)
    const legGeo = new THREE.CylinderGeometry(0.02, 0.02, tableTopY, 12);
    this.geometries.push(legGeo);
    const legPositions = [
      [tableX - 0.58, tableTopY / 2, tableZ - 0.26],
      [tableX + 0.58, tableTopY / 2, tableZ - 0.26],
      [tableX - 0.58, tableTopY / 2, tableZ + 0.26],
      [tableX + 0.58, tableTopY / 2, tableZ + 0.26],
    ];
    legPositions.forEach(([lx, ly, lz]) => {
      const leg = new THREE.Mesh(legGeo, this.materials.darkMetal);
      leg.position.set(lx, ly, lz);
      this.group.add(leg);
    });

    // ── 3. Stylized Minimalist Chair (Placed near desk) ─────────────────────────
    const chairX = 0.85;
    const chairZ = -0.50;
    const seatY = 0.45;

    // Chair Seat
    const seatGeo = new THREE.BoxGeometry(0.44, 0.04, 0.44);
    this.geometries.push(seatGeo);
    const seat = new THREE.Mesh(seatGeo, this.materials.chairSeat);
    seat.position.set(chairX, seatY, chairZ);
    this.group.add(seat);

    // Chair Backrest
    const backGeo = new THREE.BoxGeometry(0.42, 0.38, 0.03);
    this.geometries.push(backGeo);
    const backrest = new THREE.Mesh(backGeo, this.materials.chairSeat);
    backrest.position.set(chairX, seatY + 0.24, chairZ - 0.20);
    this.group.add(backrest);

    // Chair Legs
    const chairLegGeo = new THREE.CylinderGeometry(0.015, 0.015, seatY, 8);
    this.geometries.push(chairLegGeo);
    const chairLegOffsets = [
      [-0.18, -0.18],
      [ 0.18, -0.18],
      [-0.18,  0.18],
      [ 0.18,  0.18],
    ];
    chairLegOffsets.forEach(([ox, oz]) => {
      const leg = new THREE.Mesh(chairLegGeo, this.materials.darkMetal);
      leg.position.set(chairX + ox, seatY / 2, chairZ + oz);
      this.group.add(leg);
    });

    // ── 4. Stylized Bookshelf (Placed to the left-rear of Kavya) ─────────────────
    const shelfX = -1.25;
    const shelfZ = -0.65;
    const shelfW = 0.85;
    const shelfH = 1.45;
    const shelfD = 0.32;

    // Shelf frame (outer box structure)
    const shelfFrameMat = this.materials.wood;
    
    // Left & Right uprights
    const uprightGeo = new THREE.BoxGeometry(0.04, shelfH, shelfD);
    this.geometries.push(uprightGeo);
    const leftUpright = new THREE.Mesh(uprightGeo, shelfFrameMat);
    leftUpright.position.set(shelfX - shelfW / 2, shelfH / 2, shelfZ);
    const rightUpright = new THREE.Mesh(uprightGeo, shelfFrameMat);
    rightUpright.position.set(shelfX + shelfW / 2, shelfH / 2, shelfZ);
    this.group.add(leftUpright, rightUpright);

    // 4 Horizontal Shelves
    const boardGeo = new THREE.BoxGeometry(shelfW, 0.03, shelfD);
    this.geometries.push(boardGeo);
    const shelfHeights = [0.05, 0.48, 0.92, 1.40];
    shelfHeights.forEach(shY => {
      const board = new THREE.Mesh(boardGeo, shelfFrameMat);
      board.position.set(shelfX, shY, shelfZ);
      this.group.add(board);
    });

    // Decorative Stylized Books on shelves
    const bookGeo = new THREE.BoxGeometry(0.045, 0.22, 0.20);
    this.geometries.push(bookGeo);

    // Shelf 2 books
    for (let i = 0; i < 7; i++) {
      const colorMat = this.materials.bookColors[i % this.materials.bookColors.length];
      const book = new THREE.Mesh(bookGeo, colorMat);
      const bX = shelfX - 0.28 + i * 0.055;
      const bY = 0.48 + 0.11;
      const bZ = shelfZ + (Math.sin(i) * 0.01);
      book.position.set(bX, bY, bZ);
      // Slight random tilt on the last book
      if (i === 6) book.rotation.z = -0.18;
      this.group.add(book);
    }

    // Shelf 3 books
    for (let i = 0; i < 5; i++) {
      const colorMat = this.materials.bookColors[(i + 2) % this.materials.bookColors.length];
      const book = new THREE.Mesh(bookGeo, colorMat);
      const bX = shelfX + 0.05 + i * 0.055;
      const bY = 0.92 + 0.11;
      book.position.set(bX, bY, shelfZ);
      this.group.add(book);
    }

    // ── 5. Interactive Desk Lamp with Bulb ───────────────────────────────────────
    const lampBaseX = tableX + 0.35;
    const lampBaseZ = tableZ - 0.08;
    const lampBaseY = tableTopY + 0.02;

    // Lamp Base (Brass/Gold disk)
    const lampBaseGeo = new THREE.CylinderGeometry(0.07, 0.08, 0.02, 16);
    this.geometries.push(lampBaseGeo);
    const lampBase = new THREE.Mesh(lampBaseGeo, this.materials.goldMetal);
    lampBase.position.set(lampBaseX, lampBaseY, lampBaseZ);
    this.group.add(lampBase);

    // Lamp Stem (Arching neck)
    const stemGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.32, 12);
    this.geometries.push(stemGeo);
    const stem = new THREE.Mesh(stemGeo, this.materials.goldMetal);
    stem.position.set(lampBaseX, lampBaseY + 0.16, lampBaseZ);
    this.group.add(stem);

    // Lamp Shade (Cone hood)
    const shadeGeo = new THREE.ConeGeometry(0.09, 0.12, 16, 1, true);
    this.geometries.push(shadeGeo);
    const shade = new THREE.Mesh(shadeGeo, this.materials.lampShade);
    shade.position.set(lampBaseX, lampBaseY + 0.32, lampBaseZ);
    shade.rotation.x = Math.PI; // Opening facing down towards desk
    this.group.add(shade);

    // Lamp Bulb Mesh (Sphere with emissive material)
    const bulbGeo = new THREE.SphereGeometry(0.035, 16, 16);
    this.geometries.push(bulbGeo);
    this.lampBulbMesh = new THREE.Mesh(bulbGeo, this.materials.bulbOn);
    this.lampBulbMesh.position.set(lampBaseX, lampBaseY + 0.29, lampBaseZ);
    this.group.add(this.lampBulbMesh);

    // Real PointLight inside the lamp bulb
    this.lampPointLight = new THREE.PointLight(0xffb84d, 2.6, 3.8, 1.8);
    this.lampPointLight.position.set(lampBaseX, lampBaseY + 0.27, lampBaseZ);
    this.lampPointLight.castShadow = false; // keep fast & performant
    this.group.add(this.lampPointLight);

    // ── 6. Handheld Open Book Mesh (For Reading Interaction) ──────────────
    this.heldBookGroup = new THREE.Group();
    this.heldBookGroup.visible = false;

    const pageMat = new THREE.MeshStandardMaterial({ color: 0xfffcf2, roughness: 0.8 });
    const coverMat = new THREE.MeshStandardMaterial({ color: 0x9333ea, roughness: 0.5 }); // Stylish violet cover
    this.materials.heldBookPages = pageMat;
    this.materials.heldBookCover = coverMat;

    // Left Page
    const pageGeo = new THREE.BoxGeometry(0.12, 0.008, 0.17);
    this.geometries.push(pageGeo);
    const leftPage = new THREE.Mesh(pageGeo, pageMat);
    leftPage.position.set(-0.06, 0, 0);
    leftPage.rotation.z = 0.22; // angled upwards
    this.heldBookGroup.add(leftPage);

    // Right Page
    const rightPage = new THREE.Mesh(pageGeo, pageMat);
    rightPage.position.set(0.06, 0, 0);
    rightPage.rotation.z = -0.22; // angled upwards
    this.heldBookGroup.add(rightPage);

    // Book Cover / Spine
    const spineGeo = new THREE.BoxGeometry(0.25, 0.006, 0.175);
    this.geometries.push(spineGeo);
    const spine = new THREE.Mesh(spineGeo, coverMat);
    spine.position.set(0, -0.006, 0);
    this.heldBookGroup.add(spine);

    this.group.add(this.heldBookGroup);
  }

  setHeldBookVisible(visible, x = 0, y = 0, z = 0, rotY = 0) {
    if (this.heldBookGroup) {
      this.heldBookGroup.visible = Boolean(visible);
      if (visible) {
        this.heldBookGroup.position.set(x, y, z);
        this.heldBookGroup.rotation.set(0.25, rotY, 0);
      }
    }
  }

  updateHeldBookPose(x, y, z, rotY = 0) {
    if (this.heldBookGroup && this.heldBookGroup.visible) {
      this.heldBookGroup.position.set(x, y, z);
      this.heldBookGroup.rotation.set(0.25, rotY, 0);
    }
  }

  setLampState(isOn) {
    this.isLampOn = Boolean(isOn);
    if (this.lampBulbMesh) {
      this.lampBulbMesh.material = this.isLampOn ? this.materials.bulbOn : this.materials.bulbOff;
    }
    if (this.lampPointLight) {
      this.lampPointLight.intensity = this.isLampOn ? 2.6 : 0.0;
    }
  }

  toggleLamp() {
    this.setLampState(!this.isLampOn);
    return this.isLampOn;
  }

  updateTheme(isDark) {
    this.isDark = isDark;
    if (this.materials.floor) {
      this.materials.floor.color.setHex(isDark ? 0x12131c : 0xe8e2d8);
    }
    if (this.materials.wood) {
      this.materials.wood.color.setHex(isDark ? 0x422a1d : 0x8a6042);
    }
    if (this.materials.chairSeat) {
      this.materials.chairSeat.color.setHex(isDark ? 0x1e2230 : 0xd1c7b7);
    }
  }

  dispose() {
    if (this.group && this.scene) {
      this.scene.remove(this.group);
    }
    this.geometries.forEach(geo => geo.dispose());
    Object.values(this.materials).forEach(mat => {
      if (Array.isArray(mat)) {
        mat.forEach(m => m.dispose());
      } else if (mat) {
        mat.dispose();
      }
    });
  }
}
