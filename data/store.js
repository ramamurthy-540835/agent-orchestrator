const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const DATA_FILE = path.join(__dirname, 'solutions.json');

function readData() {
    if (!fs.existsSync(DATA_FILE)) {
        const initial = { solutions: [], workspaces: [], databricksConfig: { workspaceUrl: '', token: '' } };
        fs.writeFileSync(DATA_FILE, JSON.stringify(initial, null, 2));
        return initial;
    }
    const data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
    // Migrate: ensure workspaces array exists
    if (!data.workspaces) {
        data.workspaces = [];
        // Migrate old single config into a workspace
        if (data.databricksConfig && data.databricksConfig.workspaceUrl) {
            data.workspaces.push({
                id: uuidv4(),
                name: 'Default',
                environment: 'dev',
                workspaceUrl: data.databricksConfig.workspaceUrl,
                token: data.databricksConfig.token
            });
        }
        writeData(data);
    }
    return data;
}

function writeData(data) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// Legacy single config (kept for backward compat)
function getConfig() {
    const data = readData();
    return data.databricksConfig || { workspaceUrl: '', token: '' };
}

function saveConfig(config) {
    const data = readData();
    data.databricksConfig = config;
    writeData(data);
    return data.databricksConfig;
}

// ─── Workspaces CRUD ───
function getAllWorkspaces() {
    return readData().workspaces;
}

function getWorkspace(id) {
    return readData().workspaces.find(w => w.id === id);
}

function createWorkspace(name, environment, workspaceUrl, token) {
    const data = readData();
    const workspace = {
        id: uuidv4(),
        name,
        environment,
        workspaceUrl,
        token
    };
    data.workspaces.push(workspace);
    writeData(data);
    return workspace;
}

function updateWorkspace(id, updates) {
    const data = readData();
    const idx = data.workspaces.findIndex(w => w.id === id);
    if (idx === -1) return null;
    data.workspaces[idx] = { ...data.workspaces[idx], ...updates };
    writeData(data);
    return data.workspaces[idx];
}

function deleteWorkspace(id) {
    const data = readData();
    data.workspaces = data.workspaces.filter(w => w.id !== id);
    writeData(data);
    return true;
}

// ─── Solutions CRUD ───
function getAllSolutions() {
    return readData().solutions;
}

function getSolution(id) {
    return readData().solutions.find(s => s.id === id);
}

function createSolution(name, description, workspaceId) {
    const data = readData();
    const solution = {
        id: uuidv4(),
        name,
        description,
        workspaceId: workspaceId || null,
        steps: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        status: 'draft',
        lastRun: null
    };
    data.solutions.push(solution);
    writeData(data);
    return solution;
}

function updateSolution(id, updates) {
    const data = readData();
    const idx = data.solutions.findIndex(s => s.id === id);
    if (idx === -1) return null;
    data.solutions[idx] = { ...data.solutions[idx], ...updates, updatedAt: new Date().toISOString() };
    writeData(data);
    return data.solutions[idx];
}

function deleteSolution(id) {
    const data = readData();
    data.solutions = data.solutions.filter(s => s.id !== id);
    writeData(data);
    return true;
}

// ─── Workflow steps ───
function addStep(solutionId, step) {
    const data = readData();
    const solution = data.solutions.find(s => s.id === solutionId);
    if (!solution) return null;
    const newStep = {
        id: uuidv4(),
        name: step.name,
        endpointName: step.endpointName,
        description: step.description || '',
        inputMapping: step.inputMapping || 'passthrough',
        order: solution.steps.length
    };
    solution.steps.push(newStep);
    solution.updatedAt = new Date().toISOString();
    writeData(data);
    return newStep;
}

function updateStep(solutionId, stepId, updates) {
    const data = readData();
    const solution = data.solutions.find(s => s.id === solutionId);
    if (!solution) return null;
    const idx = solution.steps.findIndex(s => s.id === stepId);
    if (idx === -1) return null;
    solution.steps[idx] = { ...solution.steps[idx], ...updates };
    solution.updatedAt = new Date().toISOString();
    writeData(data);
    return solution.steps[idx];
}

function deleteStep(solutionId, stepId) {
    const data = readData();
    const solution = data.solutions.find(s => s.id === solutionId);
    if (!solution) return null;
    solution.steps = solution.steps.filter(s => s.id !== stepId);
    solution.steps.forEach((s, i) => s.order = i);
    solution.updatedAt = new Date().toISOString();
    writeData(data);
    return true;
}

function reorderSteps(solutionId, stepIds) {
    const data = readData();
    const solution = data.solutions.find(s => s.id === solutionId);
    if (!solution) return null;
    const reordered = [];
    stepIds.forEach((id, i) => {
        const step = solution.steps.find(s => s.id === id);
        if (step) {
            step.order = i;
            reordered.push(step);
        }
    });
    solution.steps = reordered;
    solution.updatedAt = new Date().toISOString();
    writeData(data);
    return solution.steps;
}

module.exports = {
    getConfig, saveConfig,
    getAllWorkspaces, getWorkspace, createWorkspace, updateWorkspace, deleteWorkspace,
    getAllSolutions, getSolution, createSolution, updateSolution, deleteSolution,
    addStep, updateStep, deleteStep, reorderSteps
};
