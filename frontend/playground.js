import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

// --- Global State ---
let sceneData = null;
let currentFrame = 0;
let isPlaying = false;
let isLocked = false;
let isVcamTargetLocked = false;
let mannequins = {}; 
let customProps = [];
let sceneCharacters = []; 
let characterIdCounter = 0;
let ws = null;
let pc = null;
const isRemote = new URLSearchParams(window.location.search).get('remote') === 'true';

// --- Motion Break System State ---
let playbackSpeed = 1;
let motionBreaks = [{ start: 0, end: Infinity, speed: 1, reversed: false, loop: false }];
let keyframes = [];

// --- Multi-Camera State ---
let sceneCameras = [];
let cameraIdCounter = 0;

// --- Scale Controls State ---
let uniformScale = true;

// --- DOM Elements ---
const viewport = document.getElementById('viewport');
const loadingOverlay = document.getElementById('loading-overlay');
const playBtn = document.getElementById('play-btn');
const slider = document.getElementById('timeline-slider');
const frameDisplay = document.getElementById('current-frame');
const totalFramesDisplay = document.getElementById('total-frames');
const lockCheckbox = document.getElementById('lock-frame');
const toggleBonesCheckbox = document.getElementById('toggle-bones');
const propColorInput = document.getElementById('prop-color');
const propertiesPanel = document.getElementById('properties-panel');

const scaleLockBtn = document.getElementById('scale-lock-btn');
const scaleX = document.getElementById('scale-x');
const scaleY = document.getElementById('scale-y');
const scaleZ = document.getElementById('scale-z');
const fovControl = document.getElementById('fov-control');
const cameraFov = document.getElementById('camera-fov');

const speedSlider = document.getElementById('speed-slider');
const speedLabel = document.getElementById('speed-label');

const cameraPipDiv = document.getElementById('camera-pip');
const pipCanvas = document.getElementById('pip-canvas');
let pipCamera = null;
const pipRenderer = new THREE.WebGLRenderer({ canvas: pipCanvas, antialias: true });

// --- Toast Helper ---
function showToast(message, color = '#2ecc71', duration = 3000) {
    const toast = document.createElement('div');
    toast.innerText = message;
    toast.style.cssText = `position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: ${color}; color: white; padding: 10px 20px; border-radius: 8px; z-index: 9999;`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), duration);
}

// --- Three.js Setup ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1e1e1e);
scene.fog = new THREE.Fog(0x1e1e1e, 50, 10000);

const camera = new THREE.PerspectiveCamera(45, viewport.clientWidth / viewport.clientHeight, 0.1, 10000);
camera.position.set(0, 2, 8); 

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(viewport.clientWidth, viewport.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
viewport.appendChild(renderer.domElement);

// Controls
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true;
orbit.dampingFactor = 0.05;
orbit.zoomSpeed = 2.0; 
orbit.target.set(0, 1, 0); 

const transformControl = new TransformControls(camera, renderer.domElement);
transformControl.size = 0.4; 
transformControl.addEventListener('dragging-changed', (event) => {
    orbit.enabled = !event.value;
});
transformControl.addEventListener('objectChange', (event) => {
    updateScaleInputs();
    updatePropertiesPanel(selectedObject);
    if(selectedObject && selectedObject.userData.helper) {
        selectedObject.userData.helper.update();
    }
    if(selectedObject && selectedObject.userData.isCameraMarker) {
        selectedObject.userData.helper.update();
    }
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
const gridHelper = new THREE.GridHelper(200, 200, 0x444444, 0x222222);
scene.add(gridHelper);

const planeGeo = new THREE.PlaneGeometry(200, 200);
const planeMat = new THREE.ShadowMaterial({ opacity: 0.6 });
const plane = new THREE.Mesh(planeGeo, planeMat);
plane.rotation.x = -Math.PI / 2;
plane.receiveShadow = true;
scene.add(plane);


// --- Mannequin Generator ---
const PERSON_COLORS = [
    0x00ff80, 0xff8000, 0x0080ff, 0xff0080, 
    0x80ff00, 0x00ffff, 0xff00ff, 0x8000ff
];

let xbotScene = null;
const gltfLoader = new GLTFLoader();
gltfLoader.load('Xbot.glb', (gltf) => {
    xbotScene = gltf.scene;
    xbotScene.traverse((child) => {
        if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
        }
    });
});

function createMannequin(id) {
    const group = new THREE.Group();
    
    const joints = [];
    for (let i = 0; i < 19; i++) {
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8));
        mesh.visible = false;
        group.add(mesh);
        joints.push(mesh);
    }
    
    let charMesh = null;
    let boneMap = {};
    
    if (xbotScene) {
        charMesh = SkeletonUtils.clone(xbotScene);
        charMesh.scale.set(1.5, 1.5, 1.5);
        charMesh.position.y = -1; 
        group.add(charMesh);
        
        const boneMat = new THREE.MeshBasicMaterial({ color: 0x00ffff, depthTest: false, transparent: true, opacity: 0.8 });
        const boneGeo = new THREE.SphereGeometry(2.0, 16, 16);
        
        charMesh.traverse((child) => {
            if (child.isBone) {
                boneMap[child.name] = child;
                const name = child.name.toLowerCase();
                const skipWords = ['end', 'thumb', 'index', 'middle', 'ring', 'pinky', 'toe'];
                const shouldSkip = skipWords.some(w => name.includes(w));
                
                if (!shouldSkip) {
                    const helper = new THREE.Mesh(boneGeo, boneMat);
                    helper.userData = { isBoneHelper: true, bone: child };
                    helper.visible = toggleBonesCheckbox ? toggleBonesCheckbox.checked : false;
                    child.add(helper);
                    
                    if (!group.userData.boneHelpers) group.userData.boneHelpers = [];
                    group.userData.boneHelpers.push(helper);
                }
            }
        });
    }
    
    group.userData = { isMannequin: true, joints, charMesh, boneMap, id, boneHelpers: group.userData.boneHelpers || [] };
    scene.add(group);
    updateOutliner();
    return group;
}

function updateMannequin(group, charData) {
    if (isLocked) return;

    const { joints, bones } = group.userData;
    const kpts = charData.keypoints;
    const zPos = -charData.depth_z * 10;
    
    const vw = sceneData.scene_width;
    const vh = sceneData.scene_height;
    
    for (let i = 0; i < 17; i++) {
        if (kpts[i] && kpts[i][2] > 0.2) {
            const x = (kpts[i][0] / vw - 0.5) * 10;
            const y = -(kpts[i][1] / vh - 0.5) * 10;
            joints[i].position.set(x, y, zPos);
            
            if (i >= 1 && i <= 4) joints[i].visible = false;
            else joints[i].visible = true;
        } else {
            joints[i].visible = false;
        }
    }
    
    if (joints[5].visible && joints[6].visible) {
        joints[17].position.copy(joints[5].position).lerp(joints[6].position, 0.5);
        joints[17].visible = true;
    } else {
        joints[17].visible = false;
    }
    
    if (joints[11].visible && joints[12].visible) {
        joints[18].position.copy(joints[11].position).lerp(joints[12].position, 0.5);
        joints[18].visible = true;
    } else {
        joints[18].visible = false;
    }
    
    if (joints[0].visible) {
        joints[0].position.y += 0.2; 
    }
    
    if (group.userData.charMesh && group.userData.boneMap) {
        const boneMap = group.userData.boneMap;
        
        const orientBone = (boneName, j1, j2, defaultAxis) => {
            const bone = boneMap[boneName];
            if (!bone || !joints[j1].visible || !joints[j2].visible) return;
            
            const p1 = joints[j1].position;
            const p2 = joints[j2].position;
            const dir = new THREE.Vector3().subVectors(p2, p1).normalize();
            
            const parentMatrixWorldInv = new THREE.Matrix4().copy(bone.parent.matrixWorld).invert();
            dir.transformDirection(parentMatrixWorldInv);
            
            const targetQuat = new THREE.Quaternion().setFromUnitVectors(defaultAxis, dir);
            bone.quaternion.copy(targetQuat);
        };
        
        orientBone('mixamorigSpine', 18, 17, new THREE.Vector3(0, 1, 0));
        
        orientBone('mixamorigLeftArm', 5, 7, new THREE.Vector3(1, 0, 0));
        orientBone('mixamorigLeftForeArm', 7, 9, new THREE.Vector3(1, 0, 0));
        orientBone('mixamorigRightArm', 6, 8, new THREE.Vector3(-1, 0, 0));
        orientBone('mixamorigRightForeArm', 8, 10, new THREE.Vector3(-1, 0, 0));
        
        orientBone('mixamorigLeftUpLeg', 11, 13, new THREE.Vector3(0, -1, 0));
        orientBone('mixamorigLeftLeg', 13, 15, new THREE.Vector3(0, -1, 0));
        orientBone('mixamorigRightUpLeg', 12, 14, new THREE.Vector3(0, -1, 0));
        orientBone('mixamorigRightLeg', 14, 16, new THREE.Vector3(0, -1, 0));
        
        if (joints[18].visible) {
            group.userData.charMesh.position.copy(joints[18].position);
            group.userData.charMesh.position.y -= 1; 
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
    let isBoneSelect = false;
    
    for (let hit of intersects) {
        if (hit.object.userData.isBoneHelper) {
            found = hit.object.userData.bone;
            isBoneSelect = true;
            break;
        }
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
        selectObject(found, isBoneSelect);
    } else {
        const isGizmo = intersects.find(hit => hit.object.parent && hit.object.parent.isTransformControls);
        if (!isGizmo) selectObject(null);
    }
}
renderer.domElement.addEventListener('pointerdown', onPointerDown);

function updateScaleInputs() {
    if(!selectedObject) return;
    scaleX.value = selectedObject.scale.x.toFixed(2);
    scaleY.value = selectedObject.scale.y.toFixed(2);
    scaleZ.value = selectedObject.scale.z.toFixed(2);
}

function updatePropertiesPanel(obj) {
    if(!obj) return;
    if (obj.userData && obj.userData.isCameraMarker) {
        fovControl.style.display = 'block';
        cameraFov.value = obj.userData.perspCamera.fov;
        cameraFov.oninput = (e) => {
            obj.userData.perspCamera.fov = parseFloat(e.target.value);
            obj.userData.perspCamera.updateProjectionMatrix();
            obj.userData.helper.update();
        };
    } else {
        fovControl.style.display = 'none';
    }
}

function selectObject(obj, isBoneSelect = false) {
    selectedObject = obj;
    if (obj) {
        if (isBoneSelect) {
            transformControl.setSpace('local');
            transformControl.setMode('rotate');
            document.getElementById('tool-rotate').click();
        } else {
            transformControl.setSpace('world');
        }
        
        transformControl.attach(obj);
        
        propertiesPanel.style.display = 'block';
        if (obj.userData && obj.userData.isProp && obj.material && obj.material.color) {
            document.getElementById('prop-color').parentElement.style.display = 'block';
            propColorInput.value = '#' + obj.material.color.getHexString();
        } else {
            document.getElementById('prop-color').parentElement.style.display = 'none';
        }
        updateScaleInputs();
        updatePropertiesPanel(obj);
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
    document.querySelectorAll('.tool-group .tool-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

if (toggleBonesCheckbox) {
    toggleBonesCheckbox.onchange = (e) => {
        const show = e.target.checked;
        sceneCharacters.forEach(group => {
            if (group.userData.boneHelpers) {
                group.userData.boneHelpers.forEach(h => h.visible = show);
            }
        });
        Object.values(mannequins).forEach(group => {
            if (group.userData.boneHelpers) {
                group.userData.boneHelpers.forEach(h => h.visible = show);
            }
        });
    };
}

// Scale Controls
scaleLockBtn.onclick = () => {
    uniformScale = !uniformScale;
    scaleLockBtn.classList.toggle('active', uniformScale);
};
[scaleX, scaleY, scaleZ].forEach(input => {
    input.oninput = (e) => {
        if(!selectedObject) return;
        const val = parseFloat(e.target.value);
        if(isNaN(val)) return;
        if(uniformScale) {
            selectedObject.scale.set(val, val, val);
            updateScaleInputs();
        } else {
            selectedObject.scale.set(parseFloat(scaleX.value), parseFloat(scaleY.value), parseFloat(scaleZ.value));
        }
    };
});
document.getElementById('reset-scale').onclick = () => {
    if(selectedObject) {
        selectedObject.scale.set(1,1,1);
        updateScaleInputs();
    }
};

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
    updateOutliner();
    selectObject(mesh);
    document.getElementById('tool-translate').click();
}

document.getElementById('add-box').onclick = () => addProp(new THREE.BoxGeometry(1, 1, 1), 0x888888);
document.getElementById('add-cylinder').onclick = () => addProp(new THREE.CylinderGeometry(0.5, 0.5, 2, 16), 0x888888);
document.getElementById('add-sphere').onclick = () => addProp(new THREE.SphereGeometry(0.5, 32, 32), 0x888888);
document.getElementById('add-cone').onclick = () => addProp(new THREE.ConeGeometry(0.5, 1, 16), 0x888888);
document.getElementById('add-torus').onclick = () => addProp(new THREE.TorusGeometry(0.5, 0.2, 16, 32), 0x888888);
document.getElementById('add-plane').onclick = () => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshStandardMaterial({ color: 0xcccccc, side: THREE.DoubleSide }));
    m.userData = { isProp: true };
    m.position.set(0, 2, 0);
    scene.add(m);
    customProps.push(m);
    updateOutliner();
    selectObject(m);
};
document.getElementById('add-spotlight').onclick = () => {
    const spotLight = new THREE.SpotLight(0xffffff, 10);
    spotLight.position.set(0, 5, 0);
    spotLight.castShadow = true;
    const spotLightHelper = new THREE.SpotLightHelper(spotLight);
    scene.add(spotLight);
    scene.add(spotLightHelper);
    scene.add(spotLight.target);
    spotLight.userData = { isProp: true, helper: spotLightHelper };
    customProps.push(spotLight);
    updateOutliner();
    selectObject(spotLight);
};

// GLB Import
const importGlbFile = document.getElementById('import-glb-file');
document.getElementById('import-glb').onclick = () => importGlbFile.click();
importGlbFile.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    gltfLoader.load(url, (gltf) => {
        const model = gltf.scene;
        model.traverse(c => {
            if(c.isMesh) { c.castShadow = true; c.receiveShadow = true; }
        });
        model.userData = { isProp: true };
        model.position.set(0, 1, 0);
        scene.add(model);
        customProps.push(model);
        selectObject(model);
        document.getElementById('tool-translate').click();
        updateOutliner();
        showToast('📦 3D Model Imported!', '#2ecc71');
    });
    importGlbFile.value = '';
};

// Multi-Camera System
function addSceneCamera(name) {
    const id = cameraIdCounter++;
    name = name || `Camera ${id + 1}`;
    
    const camGroup = new THREE.Group();
    camGroup.name = name;
    
    const body = new THREE.Mesh(
        new THREE.BoxGeometry(0.6, 0.4, 0.4), 
        new THREE.MeshStandardMaterial({ color: 0x333333 })
    );
    
    const lens = new THREE.Mesh(
        new THREE.CylinderGeometry(0.15, 0.2, 0.3, 16), 
        new THREE.MeshStandardMaterial({ color: 0x111111 })
    );
    lens.rotation.x = Math.PI / 2;
    lens.position.z = -0.3; 
    
    const stand = new THREE.Mesh(
        new THREE.CylinderGeometry(0.05, 0.05, 0.4),
        new THREE.MeshStandardMaterial({ color: 0x555555 })
    );
    stand.position.y = -0.4;
    
    camGroup.add(body);
    camGroup.add(lens);
    camGroup.add(stand);
    
    camGroup.position.copy(camera.position);
    camGroup.quaternion.copy(camera.quaternion);
    
    const perspCamera = new THREE.PerspectiveCamera(45, 16/9, 0.1, 1000);
    camGroup.add(perspCamera);
    
    const helper = new THREE.CameraHelper(perspCamera);
    scene.add(helper);
    
    camGroup.userData = { isProp: true, isCameraMarker: true, id, name, perspCamera, helper };
    scene.add(camGroup);
    customProps.push(camGroup);
    
    sceneCameras.push({ id, name, perspCamera, helper, marker: camGroup, fov: 45 });
    
    updateCameraList();
    updateCamDropdown();
    updateOutliner();
    
    showToast('📸 Camera Marker Added at Current View!', '#3498db');
    selectObject(camGroup);
}

document.getElementById('add-camera').onclick = () => addSceneCamera();

function switchToCamera(id) {
    const cam = sceneCameras.find(c => c.id === id);
    if(cam) {
        camera.position.copy(cam.marker.position);
        camera.quaternion.copy(cam.marker.quaternion);
        const dir = new THREE.Vector3(0, 0, -1);
        dir.applyQuaternion(camera.quaternion);
        orbit.target.copy(camera.position).addScaledVector(dir, 10);
        setActiveView('view-cam');
    }
}

function updateCameraList() {
    const list = document.getElementById('camera-list');
    list.innerHTML = '';
    sceneCameras.forEach(cam => {
        const div = document.createElement('div');
        div.className = 'camera-item';
        div.style.display = 'flex';
        div.style.justifyContent = 'space-between';
        
        const nameSpan = document.createElement('span');
        nameSpan.innerText = cam.name;
        nameSpan.style.cursor = 'pointer';
        nameSpan.onclick = () => { selectObject(cam.marker); };
        
        const actions = document.createElement('div');
        
        const previewBtn = document.createElement('button');
        previewBtn.innerText = '👁';
        previewBtn.title = "Preview Camera PIP";
        previewBtn.onclick = () => {
            pipCamera = cam.perspCamera;
            document.getElementById('pip-cam-name').innerText = cam.name;
            cameraPipDiv.style.display = 'block';
        };
        
        const delBtn = document.createElement('button');
        delBtn.innerText = '✕';
        delBtn.onclick = () => {
            scene.remove(cam.marker);
            scene.remove(cam.helper);
            sceneCameras = sceneCameras.filter(c => c.id !== cam.id);
            if(selectedObject === cam.marker) selectObject(null);
            updateCameraList();
            updateCamDropdown();
            updateOutliner();
            if(pipCamera === cam.perspCamera) {
                cameraPipDiv.style.display = 'none';
                pipCamera = null;
            }
        };
        
        actions.appendChild(previewBtn);
        actions.appendChild(delBtn);
        
        div.appendChild(nameSpan);
        div.appendChild(actions);
        list.appendChild(div);
    });
}

function updateCamDropdown() {
    const menu = document.getElementById('cam-dropdown-menu');
    menu.innerHTML = '';
    if (sceneCameras.length === 0) {
        menu.innerHTML = '<div class="cam-dropdown-empty">No cameras yet</div>';
        return;
    }
    sceneCameras.forEach(cam => {
        const btn = document.createElement('button');
        btn.innerText = cam.name;
        btn.onclick = () => switchToCamera(cam.id);
        menu.appendChild(btn);
    });
}
document.getElementById('pip-close').onclick = () => {
    cameraPipDiv.style.display = 'none';
    pipCamera = null;
};

// Scene Outliner
function updateOutliner() {
    const container = document.getElementById('outliner-body');
    container.innerHTML = '';
    scene.children.forEach(obj => {
        if(obj.isLight || obj.userData.isProp || obj.userData.isMannequin) {
            let icon = '📦';
            let name = obj.name || 'Object';
            if(obj.userData.isMannequin) { icon = '🧑'; name = 'Character ' + obj.userData.id; }
            if(obj.userData.isProp) { icon = '🟦'; name = obj.name || 'Prop'; }
            if(obj.isLight) { icon = '💡'; name = obj.type; }
            if(obj.userData.isCameraMarker) { icon = '📷'; name = obj.userData.name || 'Camera'; }
            
            const div = document.createElement('div');
            div.style.display = 'flex';
            div.style.justifyContent = 'space-between';
            div.style.cursor = 'pointer';
            
            const label = document.createElement('span');
            label.innerText = `${icon} ${name}`;
            label.onclick = () => selectObject(obj);
            
            const visToggle = document.createElement('span');
            visToggle.innerText = obj.visible ? '👁' : '👁🗨';
            visToggle.onclick = () => {
                toggleVisibility(obj);
                visToggle.innerText = obj.visible ? '👁' : '👁🗨';
            };
            
            div.appendChild(label);
            div.appendChild(visToggle);
            container.appendChild(div);
        }
    });
}
function toggleVisibility(obj) {
    obj.visible = !obj.visible;
}

// Collapsible Sections
document.querySelectorAll('.collapsible-header').forEach(header => {
    header.onclick = () => {
        const targetId = header.getAttribute('data-target');
        const body = document.getElementById(targetId);
        if (body.style.display === 'none') {
            body.style.display = 'block';
        } else {
            body.style.display = 'none';
        }
    };
});


document.getElementById('delete-element').onclick = () => {
    if (selectedObject) {
        transformControl.detach();
        scene.remove(selectedObject);
        
        if (sceneCharacters.includes(selectedObject)) {
            sceneCharacters = sceneCharacters.filter(c => c !== selectedObject);
        }
        
        if (selectedObject.userData.isCameraMarker) {
            scene.remove(selectedObject.userData.helper);
            sceneCameras = sceneCameras.filter(c => c.id !== selectedObject.userData.id);
            updateCameraList();
            updateCamDropdown();
        }
        
        selectedObject = null;
        propertiesPanel.style.display = 'none';
        updateOutliner();
    }
};

propColorInput.oninput = (e) => {
    if (selectedObject && selectedObject.userData.isProp && selectedObject.material) {
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
        case 'k':
            document.getElementById('add-keyframe-btn').click(); break;
        case ' ': // Space
            e.preventDefault();
            playBtn.click();
            break;
        case 'w': {
            const dir = new THREE.Vector3();
            camera.getWorldDirection(dir);
            dir.y = 0; dir.normalize();
            camera.position.addScaledVector(dir, 0.5);
            orbit.target.addScaledVector(dir, 0.5);
            break;
        }
        case 's': {
            const dir = new THREE.Vector3();
            camera.getWorldDirection(dir);
            dir.y = 0; dir.normalize();
            camera.position.addScaledVector(dir, -0.5);
            orbit.target.addScaledVector(dir, -0.5);
            break;
        }
        case 'a': {
            const dir = new THREE.Vector3();
            camera.getWorldDirection(dir);
            dir.y = 0; dir.normalize();
            dir.cross(camera.up);
            camera.position.addScaledVector(dir, -0.5);
            orbit.target.addScaledVector(dir, -0.5);
            break;
        }
        case 'd': {
            const dir = new THREE.Vector3();
            camera.getWorldDirection(dir);
            dir.y = 0; dir.normalize();
            dir.cross(camera.up);
            camera.position.addScaledVector(dir, 0.5);
            orbit.target.addScaledVector(dir, 0.5);
            break;
        }
    }
});

// View Presets
document.getElementById('view-front').onclick = () => { camera.position.set(0, 2, 10); orbit.target.set(0,2,0); setActiveView('view-front'); };
document.getElementById('view-side').onclick = () => { camera.position.set(10, 2, 0); orbit.target.set(0,2,0); setActiveView('view-side'); };
document.getElementById('view-top').onclick = () => { camera.position.set(0, 15, 0.001); orbit.target.set(0,0,0); setActiveView('view-top'); };
document.getElementById('view-persp').onclick = () => { camera.position.set(5, 5, 5); orbit.target.set(0,2,0); setActiveView('view-persp'); };
document.getElementById('view-cam').onclick = () => {
    if (selectedObject && selectedObject.userData.isCameraMarker) {
        switchToCamera(selectedObject.userData.id);
    } else {
        alert("Please select a Camera Marker first to view from its perspective.");
    }
};

function setActiveView(id) {
    document.querySelectorAll('.view-controls button').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

// Environment & Lighting Controls
document.getElementById('scene-bg-color').oninput = (e) => { scene.background.set(e.target.value); };
document.getElementById('scene-ambient').oninput = (e) => { ambientLight.intensity = parseFloat(e.target.value); };
document.getElementById('scene-sun').oninput = (e) => { dirLight.intensity = parseFloat(e.target.value); };
document.getElementById('scene-sun-x').oninput = (e) => { dirLight.position.x = parseFloat(e.target.value); };
document.getElementById('scene-sun-y').oninput = (e) => { dirLight.position.y = parseFloat(e.target.value); };
document.getElementById('scene-sun-z').oninput = (e) => { dirLight.position.z = parseFloat(e.target.value); };
document.getElementById('toggle-grid').onchange = (e) => { gridHelper.visible = e.target.checked; };
document.getElementById('toggle-shadows').onchange = (e) => {
    renderer.shadowMap.enabled = e.target.checked;
    dirLight.castShadow = e.target.checked;
    scene.traverse(c => {
        if(c.isMesh) { c.castShadow = e.target.checked; c.receiveShadow = e.target.checked; }
    });
};
document.getElementById('toggle-fog').onchange = (e) => {
    if(e.target.checked) scene.fog = new THREE.Fog(0x1e1e1e, 50, 10000);
    else scene.fog = null;
};

// --- Image Mode State ---
let imagePlane = null;
let gyroEnabled = false;

const API_URL = window.location.origin;

// --- Data Loading & Animation ---
async function loadScene() {
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('id');
    
    setupPhoneConnection();
    
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    if (isMobile) {
        document.getElementById('enable-gyro-btn').style.display = 'block';
    }
    
    if (!videoId) {
        console.log('3D Playground: Standalone mode (no video ID)');
        updateOutliner();
        return;
    }

    loadingOverlay.style.display = 'flex';
    try {
        const res = await fetch(`${API_URL}/scene/${videoId}`);
        if (!res.ok) throw new Error("Failed to load scene data");
        sceneData = await res.json();
        
        loadingOverlay.style.display = 'none';

        if (sceneData.mode === 'image') {
            setupImageScene(videoId);
        } else {
            document.getElementById('timeline-bar').style.display = 'flex';
            slider.max = sceneData.total_frames - 1;
            totalFramesDisplay.innerText = sceneData.total_frames;
            
            motionBreaks = [{ start: 0, end: sceneData.total_frames - 1, speed: 1, reversed: false, loop: false }];
            updateMotionSegments();
            updateKeyframeMarkers();
            
            renderFrame(0);
        }
        updateOutliner();
    } catch (e) {
        console.error(e);
        loadingOverlay.style.display = 'none';
        loadingOverlay.innerHTML = '<p style="color:red">Error loading scene data</p>';
        loadingOverlay.style.display = 'flex';
    }
}

function setupImageScene(videoId) {
    gridHelper.visible = false;
    plane.visible = false;
    
    const aspect = sceneData.scene_width / sceneData.scene_height;
    const planeWidth = 20;
    const planeHeight = 20 / aspect;
    
    const geo = new THREE.PlaneGeometry(planeWidth, planeHeight, 512, 512);
    
    const textureLoader = new THREE.TextureLoader();
    const baseMap = textureLoader.load(`${API_URL}${sceneData.base_url}`);
    const depthMap = textureLoader.load(`${API_URL}${sceneData.depth_url}`);
    
    const mat = new THREE.MeshStandardMaterial({
        map: baseMap,
        displacementMap: depthMap,
        displacementScale: 4.0,
        roughness: 0.8,
        metalness: 0.1,
        side: THREE.DoubleSide
    });
    
    imagePlane = new THREE.Mesh(geo, mat);
    imagePlane.rotation.x = -Math.PI / 2;
    imagePlane.position.y = 5;
    scene.add(imagePlane);
    
    camera.position.set(0, 5, 20);
    orbit.target.set(0, 5, 0);
    updateOutliner();
}

function setupPhoneConnection() {
    const btn = document.getElementById('view-on-phone-btn');
    const overlay = document.getElementById('qr-overlay');
    const closeBtn = document.getElementById('close-qr-btn');
    const qrImg = document.getElementById('qr-code-img');
    const qrText = document.getElementById('qr-url-text');
    
    btn.onclick = async () => {
        try {
            const res = await fetch(`${API_URL}/network-ip`);
            const data = await res.json();
            const ip = data.ip || window.location.hostname;
            const port = window.location.port ? `:${window.location.port}` : '';
            const path = window.location.pathname;
            const searchParams = new URLSearchParams(window.location.search);
            searchParams.set('remote', 'true');
            const search = '?' + searchParams.toString();
            const phoneUrl = `${window.location.protocol}//${ip}${port}${path}${search}`;
            
            qrText.innerText = phoneUrl;
            qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(phoneUrl)}`;
            qrImg.style.display = 'block';
            overlay.style.display = 'flex';
        } catch (e) {
            console.error("Could not get IP for QR", e);
            alert("Could not generate QR code.");
        }
    };
    
    closeBtn.onclick = () => {
        overlay.style.display = 'none';
    };
    
    const gyroBtn = document.getElementById('enable-gyro-btn');
    gyroBtn.onclick = () => {
        if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
            DeviceOrientationEvent.requestPermission()
                .then(permissionState => {
                    if (permissionState === 'granted') {
                        gyroEnabled = true;
                        gyroBtn.style.display = 'none';
                        orbit.enabled = false;
                        window.addEventListener('deviceorientation', handleGyro);
                    }
                })
                .catch(console.error);
        } else {
            gyroEnabled = true;
            gyroBtn.style.display = 'none';
            orbit.enabled = false;
            window.addEventListener('deviceorientation', handleGyro);
        }
    };
}

const zee = new THREE.Vector3(0, 0, 1);
const euler = new THREE.Euler();
const q0 = new THREE.Quaternion();
const q1 = new THREE.Quaternion(-Math.sqrt(0.5), 0, 0, Math.sqrt(0.5));
let alphaOffset = null; 

function handleGyro(e) {
    if (!gyroEnabled) return;
    
    let alpha = e.alpha ? THREE.MathUtils.degToRad(e.alpha) : 0; 
    let beta = e.beta ? THREE.MathUtils.degToRad(e.beta) : 0; 
    let gamma = e.gamma ? THREE.MathUtils.degToRad(e.gamma) : 0; 
    
    if (alphaOffset === null) {
        alphaOffset = alpha;
    }
    alpha = alpha - alphaOffset;
    
    let orient = window.orientation ? THREE.MathUtils.degToRad(window.orientation) : 0; 
    
    euler.set(beta, alpha, -gamma, 'YXZ');
    
    const quaternion = new THREE.Quaternion();
    quaternion.setFromEuler(euler);
    quaternion.multiply(q1);
    quaternion.multiply(q0.setFromAxisAngle(zee, -orient));
    
    camera.quaternion.copy(quaternion);
    
    if (isRemote && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            x: quaternion.x,
            y: quaternion.y,
            z: quaternion.z,
            w: quaternion.w
        }));
    }
}

// ===========================================
// --- ADD CHARACTER (Manual) ---
// ===========================================
document.getElementById('add-character').onclick = () => {
    if (!xbotScene) {
        alert('Character model is still loading. Please wait...');
        return;
    }
    const id = characterIdCounter++;
    const group = createMannequin(id);
    
    if (group.userData.charMesh) {
        group.userData.charMesh.position.set(0, 0, 0);
        group.userData.charMesh.scale.set(1.5, 1.5, 1.5);
    }
    group.position.set(id * 1.5, 0, 0); 
    
    sceneCharacters.push(group);
    updateOutliner();
    selectObject(group);
    transformControl.setMode('translate');
};

// ===========================================
// --- TEXT TO MOTION (AI) ---
// ===========================================
const aiMotionBtn = document.getElementById('ai-motion-btn');
if (aiMotionBtn) {
    aiMotionBtn.onclick = async () => {
        const textInput = document.getElementById('ai-motion-text').value;
        if (!textInput.trim()) {
            alert("Please enter a motion instruction.");
            return;
        }

        // Get selected character or the first one
        let targetChar = selectedObject && selectedObject.userData.isMannequin ? selectedObject : sceneCharacters[0];
        if (!targetChar) {
            alert("Please add and select a character first.");
            return;
        }

        aiMotionBtn.innerText = "✨ Generating...";
        aiMotionBtn.disabled = true;

        try {
            const response = await fetch('/api/text-to-motion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    instruction: textInput,
                    character_id: targetChar.userData.id
                })
            });

            if (!response.ok) {
                throw new Error("Failed to generate motion");
            }

            const motionData = await response.json();
            
            // Expected motionData format:
            // { actions: [ { type: "move", axis: "z", amount: 2, duration: 1000 }, { type: "rotate", axis: "y", amount: 90, duration: 500 } ] }
            
            // Execute actions sequentially for simple motion block
            for (const action of motionData.actions) {
                await executeMotionAction(targetChar, action);
            }

        } catch (err) {
            console.error(err);
            alert("Error generating motion: " + err.message);
        } finally {
            aiMotionBtn.innerHTML = '<span class="icon">✨</span> Generate Motion';
            aiMotionBtn.disabled = false;
        }
    };
}

function executeMotionAction(charGroup, action) {
    return new Promise(resolve => {
        const startPos = charGroup.position.clone();
        const startRot = charGroup.rotation.clone();
        
        let targetPos = startPos.clone();
        let targetRot = startRot.clone();
        
        if (action.type === 'move') {
            if (action.axis === 'x') targetPos.x += action.amount;
            if (action.axis === 'y') targetPos.y += action.amount;
            if (action.axis === 'z') targetPos.z += action.amount;
        } else if (action.type === 'rotate') {
            const rad = THREE.MathUtils.degToRad(action.amount);
            if (action.axis === 'x') targetRot.x += rad;
            if (action.axis === 'y') targetRot.y += rad;
            if (action.axis === 'z') targetRot.z += rad;
        }
        
        const duration = action.duration || 1000;
        const startTime = performance.now();
        
        function animateAction(time) {
            const elapsed = time - startTime;
            const t = Math.min(elapsed / duration, 1);
            
            // simple ease-in-out
            const easedT = t < .5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            
            charGroup.position.lerpVectors(startPos, targetPos, easedT);
            charGroup.rotation.set(
                THREE.MathUtils.lerp(startRot.x, targetRot.x, easedT),
                THREE.MathUtils.lerp(startRot.y, targetRot.y, easedT),
                THREE.MathUtils.lerp(startRot.z, targetRot.z, easedT)
            );
            
            if (t < 1) {
                requestAnimationFrame(animateAction);
            } else {
                resolve();
            }
        }
        requestAnimationFrame(animateAction);
    });
}

// ===========================================
// --- IMPORT 2D → 3D ---
// ===========================================
const import2dFile = document.getElementById('import-2d-file');
document.getElementById('import-2d-3d').onclick = () => import2dFile.click();
import2dFile.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    loadingOverlay.querySelector('p').innerText = 'Processing 2D → 3D...';
    loadingOverlay.style.display = 'flex';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch(`${API_URL}/playground/process-image`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.status === 'completed') {
            add3DImageToScene(data.base_url, data.depth_url);
        } else {
            alert('Error: ' + (data.message || 'Processing failed'));
        }
    } catch (err) {
        console.error(err);
        alert('Failed to process image.');
    } finally {
        loadingOverlay.style.display = 'none';
        import2dFile.value = '';
    }
};

function add3DImageToScene(baseUrl, depthUrl) {
    const textureLoader = new THREE.TextureLoader();
    const baseMap = textureLoader.load(`${API_URL}${baseUrl}`);
    const depthMap = textureLoader.load(`${API_URL}${depthUrl}`);
    
    const geo = new THREE.PlaneGeometry(16, 9, 256, 256);
    const mat = new THREE.MeshStandardMaterial({
        map: baseMap,
        displacementMap: depthMap,
        displacementScale: 3.0,
        roughness: 0.8,
        metalness: 0.1,
        side: THREE.DoubleSide
    });
    
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.isProp = true;
    mesh.userData.is3DImage = true;
    scene.add(mesh);
    customProps.push(mesh);
    updateOutliner();
    selectObject(mesh);
    transformControl.setMode('translate');
}

// ===========================================
// --- IMPORT 360° PANORAMA ---
// ===========================================
const import360File = document.getElementById('import-360-file');
document.getElementById('import-360').onclick = () => import360File.click();
import360File.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (ev) => {
        const textureLoader = new THREE.TextureLoader();
        textureLoader.load(ev.target.result, (texture) => {
            texture.colorSpace = THREE.SRGBColorSpace;
            
            const width = 30;
            const height = 12;
            const depth = 30;
            const geo = new THREE.BoxGeometry(width, height, depth);
            geo.translate(0, height / 2, 0); 
            
            texture.generateMipmaps = false;
            texture.minFilter = THREE.LinearFilter;
            
            const opticalCenter = new THREE.Vector3(0, 2, 0);
            
            const shaderMat = new THREE.ShaderMaterial({
                uniforms: {
                    tEquirect: { value: texture },
                    opticalCenter: { value: opticalCenter }
                },
                vertexShader: `
                    varying vec3 vWorldPosition;
                    void main() {
                        vec4 worldPosition = modelMatrix * vec4(position, 1.0);
                        vWorldPosition = worldPosition.xyz;
                        gl_Position = projectionMatrix * viewMatrix * worldPosition;
                    }
                `,
                fragmentShader: `
                    uniform sampler2D tEquirect;
                    uniform vec3 opticalCenter;
                    varying vec3 vWorldPosition;
                    
                    #define PI 3.14159265359
                    
                    void main() {
                        vec3 dir = normalize(vWorldPosition - opticalCenter);
                        float u = 0.5 + atan(dir.x, -dir.z) / (2.0 * PI);
                        float v = 0.5 + asin(dir.y) / PI;
                        gl_FragColor = texture2D(tEquirect, vec2(u, v));
                    }
                `,
                side: THREE.DoubleSide
            });
            
            const mesh = new THREE.Mesh(geo, shaderMat);
            
            mesh.userData.isPanorama = true;
            mesh.userData.isProp = true; 
            
            scene.add(mesh);
            customProps.push(mesh);
            updateOutliner();
            selectObject(mesh);
            
            scene.background = null; 
            
            texture.mapping = THREE.EquirectangularReflectionMapping;
            scene.environment = texture;
            
            showToast('✅ 360° Panorama Applied!', '#2ecc71');
        });
    };
    reader.readAsDataURL(file);
    import360File.value = '';
};

// ===========================================
// --- IMPORT MOTION VIDEO ---
// ===========================================
const importMotionFile = document.getElementById('import-motion-file');
document.getElementById('import-motion').onclick = () => {
    if (sceneCharacters.length === 0) {
        alert('Please add a character first (🧑 Add Character) before importing motion.');
        return;
    }
    importMotionFile.click();
};
importMotionFile.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    loadingOverlay.querySelector('p').innerText = 'Extracting motion from video...';
    loadingOverlay.style.display = 'flex';
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', 'playground');
    formData.append('colormap', 'grayscale');
    formData.append('safe_mode', 'none');
    formData.append('autocut_capture', 'end_frame');
    
    try {
        const uploadRes = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });
        const uploadData = await uploadRes.json();
        const videoId = uploadData.video_id;
        
        let completed = false;
        while (!completed) {
            await new Promise(r => setTimeout(r, 1000));
            const statusRes = await fetch(`${API_URL}/status/${videoId}`);
            const statusData = await statusRes.json();
            if (statusData.status === 'completed') {
                completed = true;
            } else if (statusData.status === 'error') {
                throw new Error(statusData.message || 'Processing failed');
            } else {
                const pct = statusData.total > 0 ? Math.round((statusData.progress / statusData.total) * 100) : 0;
                loadingOverlay.querySelector('p').innerText = `Extracting motion... ${pct}%`;
            }
        }
        
        const sceneRes = await fetch(`${API_URL}/scene/${videoId}`);
        sceneData = await sceneRes.json();
        
        document.getElementById('timeline-bar').style.display = 'flex';
        slider.max = sceneData.total_frames - 1;
        totalFramesDisplay.innerText = sceneData.total_frames;
        
        motionBreaks = [{ start: 0, end: sceneData.total_frames - 1, speed: 1, reversed: false, loop: false }];
        updateMotionSegments();
        updateKeyframeMarkers();
        
        renderFrame(0);
        
    } catch (err) {
        console.error(err);
        alert('Failed to process motion video: ' + err.message);
    } finally {
        loadingOverlay.style.display = 'none';
        importMotionFile.value = '';
    }
};

function renderFrame(idx) {
    if (!sceneData || !sceneData.frames[idx]) return;
    const frameData = sceneData.frames[idx];
    
    Object.values(mannequins).forEach(m => m.visible = false);
    
    frameData.characters.forEach(char => {
        if (!mannequins[char.id]) mannequins[char.id] = createMannequin(char.id);
        mannequins[char.id].visible = true;
        updateMannequin(mannequins[char.id], char);
    });
}

// Timeline & Motion Breaks
speedSlider.oninput = (e) => {
    playbackSpeed = parseFloat(e.target.value);
    speedLabel.innerText = playbackSpeed + '×';
};

document.getElementById('add-keyframe-btn').onclick = () => {
    if(!keyframes.includes(currentFrame)) {
        keyframes.push(currentFrame);
        keyframes.sort((a,b) => a - b);
        updateKeyframeMarkers();
    }
};

document.getElementById('split-motion-btn').onclick = () => {
    const idx = motionBreaks.findIndex(s => currentFrame >= s.start && currentFrame <= s.end);
    if(idx !== -1) {
        const seg = motionBreaks[idx];
        if (currentFrame > seg.start && currentFrame < seg.end) {
            const newSeg = { start: currentFrame, end: seg.end, speed: seg.speed, reversed: seg.reversed, loop: seg.loop };
            seg.end = currentFrame - 1;
            motionBreaks.splice(idx + 1, 0, newSeg);
            updateMotionSegments();
            showToast('✂️ Motion Split!', '#f39c12');
        }
    }
};

function getCurrentSegment(frame) {
    for (let seg of motionBreaks) {
        if (frame >= seg.start && frame <= seg.end) return seg;
    }
    return motionBreaks[motionBreaks.length - 1] || { start: 0, end: Infinity, speed: 1, reversed: false, loop: false };
}

document.getElementById('reverse-segment-btn').onclick = () => {
    const seg = getCurrentSegment(currentFrame);
    if(seg) {
        seg.reversed = !seg.reversed;
        updateMotionSegments();
        showToast(seg.reversed ? '⏪ Segment Reversed' : '⏩ Segment Forward', '#9b59b6');
    }
};
document.getElementById('loop-segment-btn').onclick = () => {
    const seg = getCurrentSegment(currentFrame);
    if(seg) {
        seg.loop = !seg.loop;
        updateMotionSegments();
        showToast(seg.loop ? '🔁 Segment Looping' : '➡️ Segment No Loop', '#3498db');
    }
};

function updateKeyframeMarkers() {
    const container = document.getElementById('keyframe-markers');
    container.innerHTML = '';
    if (!sceneData || sceneData.total_frames === 0) return;
    
    keyframes.forEach(kf => {
        const pct = (kf / (sceneData.total_frames - 1)) * 100;
        const div = document.createElement('div');
        div.style.position = 'absolute';
        div.style.left = `${pct}%`;
        div.style.width = '4px';
        div.style.height = '100%';
        div.style.background = '#f1c40f';
        div.style.transform = 'translateX(-50%)';
        container.appendChild(div);
    });
}

function updateMotionSegments() {
    const container = document.getElementById('motion-segments');
    container.innerHTML = '';
    if (!sceneData || sceneData.total_frames === 0) return;
    
    motionBreaks.forEach((seg, i) => {
        const startPct = (seg.start / (sceneData.total_frames - 1)) * 100;
        const endPct = (seg.end / (sceneData.total_frames - 1)) * 100;
        const widthPct = endPct - startPct;
        
        const div = document.createElement('div');
        div.style.position = 'absolute';
        div.style.left = `${startPct}%`;
        div.style.width = `${widthPct}%`;
        div.style.height = '4px';
        div.style.bottom = '0';
        div.style.background = i % 2 === 0 ? '#3498db' : '#9b59b6';
        if(seg.reversed) div.style.borderTop = '2px solid red';
        if(seg.loop) div.style.borderBottom = '2px solid green';
        container.appendChild(div);
    });
}

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
    if (orbit.enabled) {
        orbit.update();
    }
    
    if (isVcamTargetLocked) {
        camera.lookAt(orbit.target); 
    }
    
    if (isPlaying && sceneData && !isLocked) {
        const seg = getCurrentSegment(currentFrame);
        const activeSpeed = playbackSpeed * seg.speed;
        frameTimer += delta * activeSpeed;
        const frameDuration = 1 / sceneData.fps;
        
        if (frameTimer >= frameDuration) {
            frameTimer -= frameDuration;
            
            if (seg.reversed) {
                currentFrame--;
                if (currentFrame < seg.start) {
                    if (seg.loop) {
                        currentFrame = seg.end;
                    } else {
                        currentFrame = Math.max(0, currentFrame);
                        if (currentFrame === 0) {
                            isPlaying = false;
                            playBtn.innerHTML = '<span class="icon">▶️</span>';
                        }
                    }
                }
            } else {
                currentFrame++;
                if (currentFrame > seg.end || currentFrame >= sceneData.total_frames) {
                    if (seg.loop) {
                        currentFrame = seg.start;
                    } else {
                        currentFrame = Math.min(sceneData.total_frames - 1, currentFrame);
                        if (currentFrame === sceneData.total_frames - 1) {
                            isPlaying = false;
                            playBtn.innerHTML = '<span class="icon">▶️</span>';
                        }
                    }
                }
            }
            slider.value = currentFrame;
            frameDisplay.innerText = currentFrame;
            renderFrame(currentFrame);
        }
    }
    
    renderer.render(scene, camera);
    
    if(cameraPipDiv.style.display !== 'none' && pipCamera) {
        pipRenderer.render(scene, pipCamera);
    }
}

// Window resize
window.addEventListener('resize', () => {
    camera.aspect = viewport.clientWidth / viewport.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(viewport.clientWidth, viewport.clientHeight);
});

// Record to Video
let mediaRecorder;
let recordedChunks = [];
const recordBtn = document.getElementById('record-btn');
const recordingIndicator = document.getElementById('recording-indicator');

recordBtn.onclick = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        recordBtn.innerHTML = '🔴 Record';
        recordingIndicator.style.display = 'none';
        showToast('Recording Saved!', '#3498db');
    } else {
        const stream = renderer.domElement.captureStream(30);
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
        recordedChunks = [];
        
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };
        
        mediaRecorder.onstop = () => {
            const blob = new Blob(recordedChunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'recording.webm';
            a.click();
            URL.revokeObjectURL(url);
        };
        
        mediaRecorder.start();
        recordBtn.innerHTML = '⏹ Stop';
        recordingIndicator.style.display = 'block';
    }
};

// Export tools
document.getElementById('screenshot-btn').onclick = () => {
    renderer.render(scene, camera);
    const link = document.createElement('a');
    link.download = `playground_frame_${currentFrame}.png`;
    link.href = renderer.domElement.toDataURL('image/png');
    link.click();
};

// ===========================================
// --- V-CAM SYNC (WEBSOCKET STREAMING) ---
// ===========================================
let vcamInterval = null;
function initCameraSync() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/camera`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log("Camera Sync WS Connected");
        if (isRemote) {
            ws.send(JSON.stringify({type: 'remote_ready'}));
        }
    };
    
    if (!isRemote) {
        ws.onmessage = async (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'remote_ready') {
                    document.getElementById('qr-overlay').style.display = 'none';
                    
                    showToast('📱 V-Cam Connected Successfully!', '#2ecc71');

                    if (vcamInterval) clearInterval(vcamInterval);
                    vcamInterval = setInterval(() => {
                        if (ws.readyState === WebSocket.OPEN) {
                            const imgData = renderer.domElement.toDataURL('image/jpeg', 0.4);
                            ws.send(JSON.stringify({type: 'frame', image: imgData}));
                        }
                    }, 100); 
                    
                } else if (msg.type === 'move') {
                    camera.translateZ(msg.z * 0.15); 
                    camera.translateX(msg.x * 0.15);
                } else if (msg.type === 'target_lock') {
                    isVcamTargetLocked = msg.state;
                } else if (msg.type === 'stop') {
                    if (vcamInterval) clearInterval(vcamInterval);
                    orbit.enabled = true; 
                    
                    showToast('📱 V-Cam Disconnected.', '#e74c3c');
                } else if (msg.x !== undefined) {
                    camera.quaternion.set(msg.x, msg.y, msg.z, msg.w);
                    orbit.enabled = false;
                }
            } catch (e) {}
        };
        
        ws.onclose = () => {
            if (vcamInterval) clearInterval(vcamInterval);
            orbit.enabled = true;
        };
    } else {
        const hideSelectors = ['.topbar', '.toolbar', '#timeline-bar', '#viewport'];
        hideSelectors.forEach(s => {
            const el = document.querySelector(s);
            if (el) el.style.display = 'none';
        });
        document.body.style.background = '#1a1a1a';
        document.body.style.margin = '0';
        document.body.style.overflow = 'hidden';
        
        const statusText = document.createElement('div');
        statusText.innerText = 'Menunggu video dari PC...';
        statusText.style.color = 'white';
        statusText.style.position = 'absolute';
        statusText.style.top = '20px';
        statusText.style.width = '100%';
        statusText.style.textAlign = 'center';
        statusText.style.fontFamily = 'sans-serif';
        statusText.style.zIndex = '10';
        document.body.appendChild(statusText);
        
        const streamImg = document.createElement('img');
        streamImg.style.position = 'absolute';
        streamImg.style.top = '0';
        streamImg.style.left = '0';
        streamImg.style.width = '100vw';
        streamImg.style.height = '100vh';
        streamImg.style.objectFit = 'cover';
        document.body.appendChild(streamImg);
        
        const stopBtn = document.createElement('button');
        stopBtn.innerText = '⏹ STOP';
        stopBtn.style.position = 'absolute';
        stopBtn.style.top = '20px';
        stopBtn.style.right = '20px';
        stopBtn.style.zIndex = '9999';
        stopBtn.style.padding = '10px 20px';
        stopBtn.style.fontSize = '14px';
        stopBtn.style.background = 'rgba(231, 76, 60, 0.8)';
        stopBtn.style.color = 'white';
        stopBtn.style.border = 'none';
        stopBtn.style.borderRadius = '8px';
        stopBtn.style.display = 'none';
        document.body.appendChild(stopBtn);
        
        const recenterBtn = document.createElement('button');
        recenterBtn.innerText = '🎯 Recenter POV';
        recenterBtn.style.position = 'absolute';
        recenterBtn.style.top = '20px';
        recenterBtn.style.left = '20px';
        recenterBtn.style.zIndex = '9999';
        recenterBtn.style.padding = '10px 20px';
        recenterBtn.style.fontSize = '14px';
        recenterBtn.style.background = 'rgba(52, 152, 219, 0.8)';
        recenterBtn.style.color = 'white';
        recenterBtn.style.border = 'none';
        recenterBtn.style.borderRadius = '8px';
        recenterBtn.style.display = 'none';
        document.body.appendChild(recenterBtn);
        
        recenterBtn.onclick = () => {
            alphaOffset = null; 
        };
        
        let isLockedOnPhone = false;
        const lockBtn = document.createElement('button');
        lockBtn.innerText = '🔓 Target Lock: OFF';
        lockBtn.style.position = 'absolute';
        lockBtn.style.bottom = '40px';
        lockBtn.style.right = '40px';
        lockBtn.style.zIndex = '9999';
        lockBtn.style.padding = '15px 25px';
        lockBtn.style.fontSize = '14px';
        lockBtn.style.background = 'rgba(149, 165, 166, 0.8)';
        lockBtn.style.color = 'white';
        lockBtn.style.border = 'none';
        lockBtn.style.borderRadius = '8px';
        lockBtn.style.display = 'none';
        document.body.appendChild(lockBtn);
        
        lockBtn.onclick = () => {
            isLockedOnPhone = !isLockedOnPhone;
            lockBtn.innerText = isLockedOnPhone ? '🔒 Target Lock: ON' : '🔓 Target Lock: OFF';
            lockBtn.style.background = isLockedOnPhone ? 'rgba(46, 204, 113, 0.8)' : 'rgba(149, 165, 166, 0.8)';
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'target_lock', state: isLockedOnPhone}));
            }
        };
        
        const startBtn = document.createElement('button');
        startBtn.innerText = '🎥 START V-CAM';
        startBtn.style.position = 'absolute';
        startBtn.style.top = '50%';
        startBtn.style.left = '50%';
        startBtn.style.transform = 'translate(-50%, -50%)';
        startBtn.style.zIndex = '9999';
        startBtn.style.padding = '20px 40px';
        startBtn.style.fontSize = '24px';
        startBtn.style.background = '#e74c3c';
        startBtn.style.color = 'white';
        startBtn.style.border = 'none';
        startBtn.style.borderRadius = '12px';
        startBtn.style.boxShadow = '0 4px 15px rgba(0,0,0,0.5)';
        document.body.appendChild(startBtn);
        
        startBtn.onclick = async () => {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
            recenterBtn.style.display = 'block';
            lockBtn.style.display = 'block';
            
            try {
                if (document.documentElement.requestFullscreen) {
                    await document.documentElement.requestFullscreen();
                } else if (document.documentElement.webkitRequestFullscreen) {
                    await document.documentElement.webkitRequestFullscreen();
                }
                if (screen.orientation && screen.orientation.lock) {
                    await screen.orientation.lock('landscape');
                }
            } catch(e) { console.log('Fullscreen/Landscape lock not supported on this device'); }

            if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
                try {
                    const perm = await DeviceOrientationEvent.requestPermission();
                    if (perm === 'granted') {
                        gyroEnabled = true;
                        window.addEventListener('deviceorientation', handleGyro);
                    } else {
                        statusText.innerText = 'Izin Gyroscope ditolak!';
                    }
                } catch(e) { statusText.innerText = 'Error: ' + e; }
            } else {
                gyroEnabled = true;
                window.addEventListener('deviceorientation', handleGyro);
            }
            
            const joystickZone = document.createElement('div');
            joystickZone.style.position = 'absolute';
            joystickZone.style.bottom = '40px';
            joystickZone.style.left = '40px';
            joystickZone.style.width = '120px';
            joystickZone.style.height = '120px';
            joystickZone.style.background = 'rgba(255, 255, 255, 0.2)';
            joystickZone.style.borderRadius = '50%';
            joystickZone.style.touchAction = 'none'; 
            joystickZone.style.zIndex = '999';
            document.body.appendChild(joystickZone);

            const stick = document.createElement('div');
            stick.style.position = 'absolute';
            stick.style.top = '30px';
            stick.style.left = '30px';
            stick.style.width = '60px';
            stick.style.height = '60px';
            stick.style.background = 'rgba(255, 255, 255, 0.6)';
            stick.style.borderRadius = '50%';
            stick.style.pointerEvents = 'none';
            joystickZone.appendChild(stick);
            
            let moveX = 0;
            let moveZ = 0;
            
            function handleTouch(e) {
                e.preventDefault();
                const rect = joystickZone.getBoundingClientRect();
                const touch = e.targetTouches[0];
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                let dx = touch.clientX - centerX;
                let dy = touch.clientY - centerY;
                
                const distance = Math.min(Math.sqrt(dx*dx + dy*dy), 40); 
                const angle = Math.atan2(dy, dx);
                dx = Math.cos(angle) * distance;
                dy = Math.sin(angle) * distance;
                stick.style.transform = `translate(${dx}px, ${dy}px)`;
                
                moveX = dx / 40;
                moveZ = dy / 40; 
            }
            
            joystickZone.addEventListener('touchstart', handleTouch, {passive: false});
            joystickZone.addEventListener('touchmove', handleTouch, {passive: false});
            joystickZone.addEventListener('touchend', () => {
                stick.style.transform = `translate(0px, 0px)`;
                moveX = 0; moveZ = 0;
            });

            const joystickInterval = setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN && (moveX !== 0 || moveZ !== 0)) {
                    ws.send(JSON.stringify({type: 'move', x: moveX, z: moveZ}));
                }
            }, 30); 
            
            stopBtn.onclick = () => {
                gyroEnabled = false;
                window.removeEventListener('deviceorientation', handleGyro);
                clearInterval(joystickInterval);
                
                if (document.exitFullscreen) {
                    document.exitFullscreen().catch(()=>{});
                }
                if (screen.orientation && screen.orientation.unlock) {
                    screen.orientation.unlock();
                }
                
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'target_lock', state: false})); 
                    ws.send(JSON.stringify({type: 'stop'})); 
                    ws.close();
                }
                
                statusText.innerText = 'V-Cam Dihentikan. Silakan tutup halaman ini.';
                statusText.style.display = 'block';
                streamImg.style.display = 'none';
                joystickZone.style.display = 'none';
                stopBtn.style.display = 'none';
                recenterBtn.style.display = 'none';
                lockBtn.style.display = 'none';
            };
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'frame') {
                    streamImg.src = msg.image;
                    statusText.style.display = 'none'; 
                }
            } catch (e) {}
        };
    }
}
initCameraSync();


document.getElementById('export-json-btn').onclick = () => {
    const props = customProps.map(p => ({
        type: p.geometry.type,
        color: p.material && p.material.color ? p.material.color.getHex() : null,
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
