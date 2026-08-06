import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

// --- Global State ---
let sceneData = null;
let currentFrame = 0;
let isPlaying = false;
let isLocked = false;
let mannequins = {}; // id -> Group
let customProps = [];

// --- DOM Elements ---
const viewport = document.getElementById('viewport');
const loadingOverlay = document.getElementById('loading-overlay');
const playBtn = document.getElementById('play-btn');
const slider = document.getElementById('timeline-slider');
const frameDisplay = document.getElementById('current-frame');
const totalFramesDisplay = document.getElementById('total-frames');
const lockCheckbox = document.getElementById('lock-frame');
const propColorInput = document.getElementById('prop-color');
const propertiesPanel = document.getElementById('properties-panel');

// --- Three.js Setup ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1e1e1e);
scene.fog = new THREE.Fog(0x1e1e1e, 20, 100);

const camera = new THREE.PerspectiveCamera(45, viewport.clientWidth / viewport.clientHeight, 0.1, 1000);
camera.position.set(0, 5, 10);

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(viewport.clientWidth, viewport.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
viewport.appendChild(renderer.domElement);

// Controls
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true;
orbit.dampingFactor = 0.05;

const transformControl = new TransformControls(camera, renderer.domElement);
transformControl.addEventListener('dragging-changed', (event) => {
    orbit.enabled = !event.value;
});
scene.add(transformControl);

// Lighting
const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(5, 10, 5);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 2048;
dirLight.shadow.mapSize.height = 2048;
dirLight.shadow.camera.near = 0.5;
dirLight.shadow.camera.far = 50;
scene.add(dirLight);

const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.4);
hemiLight.position.set(0, 20, 0);
scene.add(hemiLight);

// Floor
const gridHelper = new THREE.GridHelper(40, 40, 0x444444, 0x222222);
scene.add(gridHelper);

const planeGeo = new THREE.PlaneGeometry(40, 40);
const planeMat = new THREE.MeshStandardMaterial({ color: 0x111111, depthWrite: false });
const plane = new THREE.Mesh(planeGeo, planeMat);
plane.rotation.x = -Math.PI / 2;
plane.receiveShadow = true;
scene.add(plane);


// --- Mannequin Generator ---
const PERSON_COLORS = [
    0x00ff80, 0xff8000, 0x0080ff, 0xff0080, 
    0x80ff00, 0x00ffff, 0xff00ff, 0x8000ff
];

const SKELETON_CONNECTIONS = [
    [0, 1], [0, 2], [1, 3], [2, 4], // Head
    [5, 6], [5, 7], [7, 9], [6, 8], [8, 10], // Arms
    [5, 11], [6, 12], [11, 12], // Torso
    [11, 13], [13, 15], [12, 14], [14, 16] // Legs
];

function createMannequin(id) {
    const group = new THREE.Group();
    const color = PERSON_COLORS[id % PERSON_COLORS.length];
    
    const jointMat = new THREE.MeshStandardMaterial({ color: color, roughness: 0.2, metalness: 0.1 });
    const boneMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.5 });
    
    // 17 joints
    const joints = [];
    for (let i = 0; i < 17; i++) {
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.05, 16, 16), jointMat);
        mesh.castShadow = true;
        group.add(mesh);
        joints.push(mesh);
    }
    
    // Bones
    const bones = [];
    for (let i = 0; i < SKELETON_CONNECTIONS.length; i++) {
        const mesh = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1, 8), boneMat);
        mesh.castShadow = true;
        group.add(mesh);
        bones.push(mesh);
    }
    
    group.userData = { isMannequin: true, joints, bones, id };
    scene.add(group);
    return group;
}

function updateMannequin(group, charData) {
    if (isLocked) return; // Don't animate if locked

    const { joints, bones } = group.userData;
    const kpts = charData.keypoints;
    const zPos = -charData.depth_z * 10; // Scale depth
    
    // Scale X/Y from video pixels to 3D space (-5 to 5 approx)
    const vw = sceneData.scene_width;
    const vh = sceneData.scene_height;
    
    // Update joints
    for (let i = 0; i < 17; i++) {
        if (kpts[i] && kpts[i][2] > 0.2) {
            const x = (kpts[i][0] / vw - 0.5) * 10;
            const y = -(kpts[i][1] / vh - 0.5) * 10;
            joints[i].position.set(x, y, zPos);
            joints[i].visible = true;
        } else {
            joints[i].visible = false;
        }
    }
    
    // Update bones
    for (let i = 0; i < SKELETON_CONNECTIONS.length; i++) {
        const [j1, j2] = SKELETON_CONNECTIONS[i];
        const p1 = joints[j1].position;
        const p2 = joints[j2].position;
        
        if (joints[j1].visible && joints[j2].visible) {
            const distance = p1.distanceTo(p2);
            bones[i].position.copy(p1).lerp(p2, 0.5);
            bones[i].scale.set(1, distance, 1);
            bones[i].quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p2.clone().sub(p1).normalize());
            bones[i].visible = true;
        } else {
            bones[i].visible = false;
        }
    }
}

// --- Interaction & Tools ---
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let selectedObject = null;

function onPointerDown(event) {
    if (transformControl.dragging) return;
    
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);
    
    let found = null;
    for (let hit of intersects) {
        if (hit.object.parent && hit.object.parent.userData.isMannequin) {
            found = hit.object.parent;
            break;
        }
        if (hit.object.userData.isProp) {
            found = hit.object;
            break;
        }
    }
    
    if (found) {
        selectObject(found);
    } else {
        // Only deselect if we didn't click on the transform control
        const isGizmo = intersects.find(hit => hit.object.parent && hit.object.parent.isTransformControls);
        if (!isGizmo) selectObject(null);
    }
}
renderer.domElement.addEventListener('pointerdown', onPointerDown);

function selectObject(obj) {
    selectedObject = obj;
    if (obj) {
        transformControl.attach(obj);
        if (obj.userData.isProp) {
            propertiesPanel.style.display = 'flex';
            propColorInput.value = '#' + obj.material.color.getHexString();
        } else {
            propertiesPanel.style.display = 'none';
        }
    } else {
        transformControl.detach();
        propertiesPanel.style.display = 'none';
    }
}

// Tool Buttons
document.getElementById('tool-select').onclick = () => { transformControl.detach(); setActiveTool('tool-select'); };
document.getElementById('tool-translate').onclick = () => { transformControl.setMode('translate'); setActiveTool('tool-translate'); };
document.getElementById('tool-rotate').onclick = () => { transformControl.setMode('rotate'); setActiveTool('tool-rotate'); };
document.getElementById('tool-scale').onclick = () => { transformControl.setMode('scale'); setActiveTool('tool-scale'); };

function setActiveTool(id) {
    document.querySelectorAll('.tool-group:first-child .tool-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

// Add Props
function addProp(geometry, color) {
    const material = new THREE.MeshStandardMaterial({ color });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.position.set(0, 1, 0);
    mesh.userData = { isProp: true };
    scene.add(mesh);
    customProps.push(mesh);
    selectObject(mesh);
    document.getElementById('tool-translate').click();
}

document.getElementById('add-box').onclick = () => addProp(new THREE.BoxGeometry(1, 1, 1), 0x888888);
document.getElementById('add-cylinder').onclick = () => addProp(new THREE.CylinderGeometry(0.5, 0.5, 2, 16), 0x888888);
document.getElementById('add-plane').onclick = () => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshStandardMaterial({ color: 0xcccccc, side: THREE.DoubleSide }));
    m.userData = { isProp: true };
    m.position.set(0, 2, 0);
    scene.add(m);
    customProps.push(m);
    selectObject(m);
};

document.getElementById('delete-element').onclick = () => {
    if (selectedObject && selectedObject.userData.isProp) {
        transformControl.detach();
        scene.remove(selectedObject);
        selectedObject = null;
        propertiesPanel.style.display = 'none';
    }
};

propColorInput.oninput = (e) => {
    if (selectedObject && selectedObject.userData.isProp) {
        selectedObject.material.color.set(e.target.value);
    }
};

// Keyboard shortcuts
window.addEventListener('keydown', (e) => {
    switch (e.key.toLowerCase()) {
        case 'g': document.getElementById('tool-translate').click(); break;
        case 'r': document.getElementById('tool-rotate').click(); break;
        case 's': document.getElementById('tool-scale').click(); break;
        case 'q': document.getElementById('tool-select').click(); break;
        case 'delete':
        case 'backspace':
            document.getElementById('delete-element').click(); break;
        case ' ': // Space
            e.preventDefault();
            playBtn.click();
            break;
    }
});

// View Presets
document.getElementById('view-front').onclick = () => { camera.position.set(0, 2, 10); orbit.target.set(0,2,0); setActiveView('view-front'); };
document.getElementById('view-side').onclick = () => { camera.position.set(10, 2, 0); orbit.target.set(0,2,0); setActiveView('view-side'); };
document.getElementById('view-top').onclick = () => { camera.position.set(0, 15, 0); orbit.target.set(0,0,0); setActiveView('view-top'); };
document.getElementById('view-persp').onclick = () => { camera.position.set(5, 5, 5); orbit.target.set(0,2,0); setActiveView('view-persp'); };

function setActiveView(id) {
    document.querySelectorAll('.view-controls button').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

// --- Data Loading & Animation ---
async function loadScene() {
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('id');
    if (!videoId) {
        alert("No video ID provided");
        return;
    }

    try {
        const API_URL = window.location.origin;
        const res = await fetch(`${API_URL}/scene/${videoId}`);
        if (!res.ok) throw new Error("Failed to load scene data");
        sceneData = await res.json();
        
        slider.max = sceneData.total_frames - 1;
        totalFramesDisplay.innerText = sceneData.total_frames;
        loadingOverlay.style.display = 'none';
        
        renderFrame(0);
    } catch (e) {
        console.error(e);
        loadingOverlay.innerHTML = '<p style="color:red">Error loading scene data</p>';
    }
}

function renderFrame(idx) {
    if (!sceneData || !sceneData.frames[idx]) return;
    const frameData = sceneData.frames[idx];
    
    // Hide all first
    Object.values(mannequins).forEach(m => m.visible = false);
    
    // Update active characters
    frameData.characters.forEach(char => {
        if (!mannequins[char.id]) mannequins[char.id] = createMannequin(char.id);
        mannequins[char.id].visible = true;
        updateMannequin(mannequins[char.id], char);
    });
}

// Timeline
slider.oninput = (e) => {
    currentFrame = parseInt(e.target.value);
    frameDisplay.innerText = currentFrame;
    renderFrame(currentFrame);
};

playBtn.onclick = () => {
    isPlaying = !isPlaying;
    playBtn.innerHTML = isPlaying ? '<span class="icon">⏸️</span>' : '<span class="icon">▶️</span>';
};

lockCheckbox.onchange = (e) => {
    isLocked = e.target.checked;
};

// Render Loop
const clock = new THREE.Clock();
let frameTimer = 0;

function animate() {
    requestAnimationFrame(animate);
    
    const delta = clock.getDelta();
    orbit.update();
    
    if (isPlaying && sceneData && !isLocked) {
        frameTimer += delta;
        const frameDuration = 1 / sceneData.fps;
        
        if (frameTimer >= frameDuration) {
            frameTimer = 0;
            currentFrame = (currentFrame + 1) % sceneData.total_frames;
            slider.value = currentFrame;
            frameDisplay.innerText = currentFrame;
            renderFrame(currentFrame);
        }
    }
    
    renderer.render(scene, camera);
}

// Window resize
window.addEventListener('resize', () => {
    camera.aspect = viewport.clientWidth / viewport.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(viewport.clientWidth, viewport.clientHeight);
});

// Export tools
document.getElementById('screenshot-btn').onclick = () => {
    renderer.render(scene, camera);
    const link = document.createElement('a');
    link.download = `playground_frame_${currentFrame}.png`;
    link.href = renderer.domElement.toDataURL('image/png');
    link.click();
};

document.getElementById('export-json-btn').onclick = () => {
    const props = customProps.map(p => ({
        type: p.geometry.type,
        color: p.material.color.getHex(),
        position: p.position.toArray(),
        rotation: p.rotation.toArray(),
        scale: p.scale.toArray()
    }));
    
    const blob = new Blob([JSON.stringify({ frame: currentFrame, props }, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'playground_scene.json';
    link.click();
};

// Start
loadScene();
animate();
