const express = require('express');
const router = express.Router();
const https = require('https');
const http = require('http');
const store = require('../data/store');
const multer = require('multer');
const csv = require('csv-parse/sync');

const upload = multer({ storage: multer.memoryStorage() });

console.log('[API] Routes loaded - version 3');

// ─── Agent System Prompts ───
const AGENT_PROMPTS = {
    profiler: "You are DataScout Agent — an autonomous data profiling specialist. You DO NOT ask questions. You DO NOT explain what you can or cannot do. You IMMEDIATELY analyze any data given to you and return a structured JSON profiling report. Return ONLY valid JSON with these keys: profile_report.dataset_summary (total_records, total_columns, overall_completeness_score), profile_report.column_profiles (array with column_name, data_type_detected, null_count, null_percentage, unique_count, issues_found for each column), profile_report.data_quality_flags (array with severity, column, issue, affected_rows, recommendation), profile_report.schema_recommendation. NEVER return markdown. NEVER ask questions. ONLY return the JSON object.",
    quality: "You are DataGuard Agent — an autonomous data quality validation specialist. You DO NOT ask questions. You IMMEDIATELY validate any data and return a structured JSON quality report. Return ONLY valid JSON with these keys: quality_report.summary (overall_score 0-100, pass_fail PASS/FAIL/CONDITIONAL_PASS, total_records, total_issues, critical_issues), quality_report.dimension_scores (completeness, validity, consistency, uniqueness, accuracy each 0-100), quality_report.validation_results (array with rule_id, rule_name, severity, column, description, affected_records, recommendation), quality_report.data_readiness (ready_for_load boolean, blocking_issues array, warnings array). Check: invalid emails, future dates, negative values where unexpected, mixed boolean formats, mixed date formats, missing required fields, PII exposure. NEVER return markdown. NEVER ask questions. ONLY return the JSON object.",
    autoloader: "You are AutoLoad Agent — an autonomous Databricks Auto Loader specialist. You DO NOT ask questions about paths or schemas. You IMMEDIATELY generate Auto Loader pipeline code. Return ONLY valid JSON with these keys: autoloader_pipeline.configuration (source_path, source_format, checkpoint_path, target_catalog, target_schema, target_table, load_mode), autoloader_pipeline.inferred_schema (columns array with name, spark_type, nullable), autoloader_pipeline.pipeline_code (complete runnable PySpark code as string), autoloader_pipeline.data_transformations (array of transformations to apply), autoloader_pipeline.quality_expectations (array of Delta expectations). If target paths are provided in the input, use them. If not, use defaults: catalog=retail_dev, schema=bronze. Always add _ingestion_timestamp, _source_file, _load_date audit columns. NEVER return markdown. NEVER ask questions. ONLY return the JSON object.",
    classifier: "You are ClassifyGuard Agent — an autonomous data classification specialist. You DO NOT ask questions. You IMMEDIATELY classify every column for sensitivity, PII, and governance. Return ONLY valid JSON with these keys: classification_report.summary (total_columns_classified, pii_columns_found, restricted_columns, risk_level), classification_report.column_classifications (array with column_name, sensitivity_level PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED, pii_type DIRECT_PII/QUASI_PII/NON_PII, pii_category, requires_encryption, requires_masking), classification_report.unity_catalog_tags.sql_commands (array of ALTER TABLE SET TAGS SQL statements), classification_report.masking_recommendations (array with column, masking_function, databricks_sql), classification_report.access_policy_recommendations. Detect SSN patterns (XXX-XX-XXXX), credit card numbers (starts with 3/4/5), emails, phones, DOB, addresses. NEVER return markdown. NEVER ask questions. ONLY return the JSON object."
};

// ─── Agent Endpoints using Environment Variables ───
router.post('/orchestration/profile', async (req, res) => {
    try {
        const { data, priorOutputs } = req.body;
        if (!data) return res.status(400).json({ error: 'data field is required' });

        const config = {
            workspaceUrl: process.env.DATABRICKS_HOST,
            token: process.env.DATABRICKS_TOKEN
        };

        let userInput = data;
        if (priorOutputs && Array.isArray(priorOutputs) && priorOutputs.length > 0) {
            const context = priorOutputs.map(p => `[${p.agent} output]:\n${typeof p.output === 'string' ? p.output : JSON.stringify(p.output)}`).join('\n\n---\n');
            userInput = `${data}\n\n--- Previous Agent Results ---\n${context}`;
        }

        const payload = {
            input: [
                { role: 'user', content: `${AGENT_PROMPTS.profiler}\n\n${userInput}` }
            ]
        };

        const response = await databricksRequest(config, 'POST', '/serving-endpoints/mit_structured_data_profiler_endpoint/invocations', payload);
        res.json({ agent: 'profiler', output: response });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

router.post('/orchestration/quality', async (req, res) => {
    try {
        const { data, priorOutputs } = req.body;
        if (!data) return res.status(400).json({ error: 'data field is required' });

        const config = {
            workspaceUrl: process.env.DATABRICKS_HOST,
            token: process.env.DATABRICKS_TOKEN
        };

        let userInput = data;
        if (priorOutputs && Array.isArray(priorOutputs) && priorOutputs.length > 0) {
            const context = priorOutputs.map(p => `[${p.agent} output]:\n${typeof p.output === 'string' ? p.output : JSON.stringify(p.output)}`).join('\n\n---\n');
            userInput = `${data}\n\n--- Previous Agent Results ---\n${context}`;
        }

        const payload = {
            input: [
                { role: 'user', content: `${AGENT_PROMPTS.quality}\n\n${userInput}` }
            ]
        };

        const response = await databricksRequest(config, 'POST', '/serving-endpoints/mit_data_quality_agent_endpoint/invocations', payload);
        res.json({ agent: 'quality', output: response });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

router.post('/orchestration/classify', async (req, res) => {
    try {
        const { data, priorOutputs } = req.body;
        if (!data) return res.status(400).json({ error: 'data field is required' });

        const config = {
            workspaceUrl: process.env.DATABRICKS_HOST,
            token: process.env.DATABRICKS_TOKEN
        };

        let userInput = data;
        if (priorOutputs && Array.isArray(priorOutputs) && priorOutputs.length > 0) {
            const context = priorOutputs.map(p => `[${p.agent} output]:\n${typeof p.output === 'string' ? p.output : JSON.stringify(p.output)}`).join('\n\n---\n');
            userInput = `${data}\n\n--- Previous Agent Results ---\n${context}`;
        }

        const payload = {
            input: [
                { role: 'user', content: `${AGENT_PROMPTS.classifier}\n\n${userInput}` }
            ]
        };

        const response = await databricksRequest(config, 'POST', '/serving-endpoints/mit_data_classifier_endpoint/invocations', payload);
        res.json({ agent: 'classifier', output: response });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

router.post('/orchestration/autoload', async (req, res) => {
    try {
        const { data, priorOutputs, sourcePath, targetTable } = req.body;
        if (!data) return res.status(400).json({ error: 'data field is required' });

        const config = {
            workspaceUrl: process.env.DATABRICKS_HOST,
            token: process.env.DATABRICKS_TOKEN
        };

        let userInput = data;
        if (sourcePath) userInput += `\n\nSource path: ${sourcePath}`;
        if (targetTable) userInput += `\nTarget table: ${targetTable}`;

        if (priorOutputs && Array.isArray(priorOutputs) && priorOutputs.length > 0) {
            const context = priorOutputs.map(p => `[${p.agent} output]:\n${typeof p.output === 'string' ? p.output : JSON.stringify(p.output)}`).join('\n\n---\n');
            userInput += `\n\n--- Previous Agent Results ---\n${context}`;
        }

        const payload = {
            input: [
                { role: 'user', content: `${AGENT_PROMPTS.autoloader}\n\n${userInput}` }
            ]
        };

        const response = await databricksRequest(config, 'POST', '/serving-endpoints/mit_autoloader_agent_endpoint/invocations', payload);
        res.json({ agent: 'autoloader', output: response });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ─── Proxy Routes to Python Orchestration Service (port 8001) ───
const ORCHESTRATION_SERVICE_URL = 'http://localhost:8001';

router.get('/orchestration/:workflowId', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/${req.params.workflowId}`);
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to fetch orchestration status: ${err.message}` });
    }
});

router.post('/orchestration/:workflowId/approve', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/${req.params.workflowId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to approve orchestration: ${err.message}` });
    }
});

// New LangGraph orchestration endpoints
router.post('/orchestration/start', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to start orchestration workflow: ${err.message}` });
    }
});

router.get('/orchestration/:workflowId/results', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/${req.params.workflowId}/results`);
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to fetch workflow results: ${err.message}` });
    }
});

router.get('/orchestration/:workflowId/log', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/${req.params.workflowId}/log`);
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to fetch workflow log: ${err.message}` });
    }
});

router.post('/orchestration/:workflowId/decision', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/${req.params.workflowId}/decision`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to submit orchestration decision: ${err.message}` });
    }
});

// Resume workflow after human checkpoint
router.post('/orchestration/:workflowId/resume', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/orchestration/${req.params.workflowId}/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to resume workflow: ${err.message}` });
    }
});

router.post('/interview/start', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/interview/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to start interview: ${err.message}` });
    }
});

router.post('/interview/:interviewId/answer', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/interview/${req.params.interviewId}/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to submit interview answer: ${err.message}` });
    }
});

router.get('/databricks/status', async (req, res) => {
    try {
        const response = await fetch(`${ORCHESTRATION_SERVICE_URL}/databricks/status`);
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ error: `Failed to check Databricks status: ${err.message}` });
    }
});

// ─── Legacy Databricks Config ───
router.get('/config', (req, res) => {
    res.json(store.getConfig());
});

router.post('/config', (req, res) => {
    const { workspaceUrl, token } = req.body;
    res.json(store.saveConfig({ workspaceUrl, token }));
});

// ─── Workspaces CRUD ───
router.get('/workspaces', (req, res) => {
    res.json(store.getAllWorkspaces());
});

router.get('/workspaces/:id', (req, res) => {
    const ws = store.getWorkspace(req.params.id);
    if (!ws) return res.status(404).json({ error: 'Not found' });
    res.json(ws);
});

router.post('/workspaces', (req, res) => {
    const { name, environment, workspaceUrl, token } = req.body;
    if (!name || !workspaceUrl || !token) return res.status(400).json({ error: 'Name, URL, and token are required' });
    res.json(store.createWorkspace(name, environment || 'dev', workspaceUrl, token));
});

router.put('/workspaces/:id', (req, res) => {
    const result = store.updateWorkspace(req.params.id, req.body);
    if (!result) return res.status(404).json({ error: 'Not found' });
    res.json(result);
});

router.delete('/workspaces/:id', (req, res) => {
    store.deleteWorkspace(req.params.id);
    res.json({ success: true });
});

// ─── List serving endpoints from a specific workspace ───
router.get('/workspaces/:id/endpoints', async (req, res) => {
    const ws = store.getWorkspace(req.params.id);
    if (!ws) return res.json({ endpoints: [], error: 'Workspace not found' });
    try {
        const data = await databricksRequest(ws, 'GET', '/api/2.0/serving-endpoints');
        const endpoints = (data.endpoints || [])
            .filter(ep => ep && ep.name && !ep.name.startsWith('databricks-'))
            .map(ep => {
                if (!ep || !ep.name) return null;

                // Handle various state field formats from Databricks API
                let state = 'UNKNOWN';
                if (ep.state) {
                    if (typeof ep.state === 'string') {
                        state = ep.state; // Direct string: "READY", "NOT_READY", etc
                    } else if (ep.state.ready === true) {
                        state = 'READY';
                    } else if (ep.state.ready === false) {
                        state = 'STOPPED';
                    }
                }
                return {
                    name: ep.name,
                    state: state,
                    creator: ep.creator_user_name || ep.creator,
                    creation_timestamp: ep.creation_timestamp
                };
            })
            .filter(e => e !== null)
            .sort((a, b) => {
                // Sort: READY first, then others alphabetically
                if (a.state === 'READY' && b.state !== 'READY') return -1;
                if (a.state !== 'READY' && b.state === 'READY') return 1;
                return (a.name || '').localeCompare(b.name || '');
            });
        res.json({ endpoints });
    } catch (err) {
        console.error('[ENDPOINTS] Error:', err.message);
        res.json({ endpoints: [], error: err.message });
    }
});

// ─── Legacy endpoints listing (uses first workspace or old config) ───
router.get('/endpoints', async (req, res) => {
    const workspaces = store.getAllWorkspaces();
    const config = workspaces.length > 0 ? workspaces[0] : store.getConfig();
    if (!config.workspaceUrl || !config.token) {
        return res.json({ endpoints: [], error: 'Databricks not configured' });
    }
    try {
        const data = await databricksRequest(config, 'GET', '/api/2.0/serving-endpoints');
        const endpoints = (data.endpoints || [])
            .filter(ep => ep && ep.name && !ep.name.startsWith('databricks-'))
            .map(ep => {
                if (!ep || !ep.name) return null;

                // Handle various state field formats from Databricks API
                let state = 'UNKNOWN';
                if (ep.state) {
                    if (typeof ep.state === 'string') {
                        state = ep.state;
                    } else if (ep.state.ready === true) {
                        state = 'READY';
                    } else if (ep.state.ready === false) {
                        state = 'STOPPED';
                    }
                }
                return {
                    name: ep.name,
                    state: state,
                    creator: ep.creator_user_name || ep.creator,
                    creation_timestamp: ep.creation_timestamp
                };
            })
            .filter(e => e !== null)
            .sort((a, b) => {
                if (a.state === 'READY' && b.state !== 'READY') return -1;
                if (a.state !== 'READY' && b.state === 'READY') return 1;
                return (a.name || '').localeCompare(b.name || '');
            });
        res.json({ endpoints });
    } catch (err) {
        console.error('[ENDPOINTS] Error:', err.message);
        res.json({ endpoints: [], error: err.message });
    }
});

// ─── Agent Inventory: Real + Mock agents ───
router.get('/agents/inventory', async (req, res) => {
    try {
        const workspaces = store.getAllWorkspaces();
        const config = workspaces.length > 0 ? workspaces[0] : store.getConfig();

        // Real agents from Databricks
        let realAgents = [];
        if (config.workspaceUrl && config.token) {
            try {
                const data = await databricksRequest(config, 'GET', '/api/2.0/serving-endpoints');
                realAgents = (data.endpoints || [])
                    .filter(ep => ep && ep.name && !ep.name.startsWith('databricks-'))
                    .map(ep => {
                        if (!ep || !ep.name) return null;

                        // Handle various state field formats
                        let state = 'UNKNOWN';
                        if (ep.state) {
                            if (typeof ep.state === 'string') {
                                state = ep.state;
                            } else if (ep.state.ready === true) {
                                state = 'READY';
                            } else if (ep.state.ready === false) {
                                state = 'STOPPED';
                            }
                        }
                        return {
                            name: ep.name,
                            display_name: (ep.name || '').replace(/_endpoint$/, '').replace(/_/g, ' ').toUpperCase(),
                            state: state,
                            source: 'DATABRICKS',
                            icon: '🤖',
                            type: 'Real Agent',
                            category: categorizeAgent(ep.name || '')
                        };
                    })
                    .filter(a => a !== null);
            } catch (e) {
                console.log('[INVENTORY] Failed to fetch real agents:', e.message);
            }
        }

        // Mock agents from orchestration service
        let mockAgents = [];
        try {
            const mockResp = await fetch('http://localhost:8001/mock-agents');
            if (mockResp.ok) {
                const mockData = await mockResp.json();
                mockAgents = (mockData.agents || []).map(agent => ({
                    name: agent.name,
                    display_name: agent.display_name,
                    state: 'READY',
                    source: 'MOCK',
                    icon: agent.icon || '🔄',
                    type: 'Mock Agent',
                    category: agent.category
                }));
            }
        } catch (e) {
            console.log('[INVENTORY] Failed to fetch mock agents:', e.message);
        }

        // Combine and sort: Real READY first, then Mock, then Stopped
        const all = [...realAgents, ...mockAgents];
        const sorted = all.sort((a, b) => {
            // Sort by: source (Real > Mock) -> state (READY > others) -> name
            if (a.source !== b.source) {
                return a.source === 'DATABRICKS' ? -1 : 1;
            }
            if (a.state !== b.state) {
                return a.state === 'READY' ? -1 : 1;
            }
            return (a.name || '').localeCompare(b.name || '');
        });

        res.json({
            agents: sorted,
            summary: {
                total: sorted.length,
                real_ready: realAgents.filter(a => a.state === 'READY').length,
                real_stopped: realAgents.filter(a => a.state !== 'READY').length,
                mock: mockAgents.length
            }
        });
    } catch (err) {
        res.status(500).json({
            error: err.message,
            agents: [],
            summary: { total: 0, real_ready: 0, real_stopped: 0, mock: 0 }
        });
    }
});

// Helper function to categorize agents
function categorizeAgent(agentName) {
    const name = agentName.toLowerCase();
    if (name.includes('profile')) return 'Profiling';
    if (name.includes('quality')) return 'Quality';
    if (name.includes('classify')) return 'Classification';
    if (name.includes('autoload')) return 'Loading';
    return 'Other';
}

// ─── Solutions CRUD ───
router.get('/solutions', (req, res) => {
    res.json(store.getAllSolutions());
});

router.get('/solutions/:id', (req, res) => {
    const solution = store.getSolution(req.params.id);
    if (!solution) return res.status(404).json({ error: 'Not found' });
    res.json(solution);
});

router.post('/solutions', (req, res) => {
    const { name, description, workspaceId } = req.body;
    if (!name) return res.status(400).json({ error: 'Name is required' });
    res.json(store.createSolution(name, description || '', workspaceId));
});

router.put('/solutions/:id', (req, res) => {
    const result = store.updateSolution(req.params.id, req.body);
    if (!result) return res.status(404).json({ error: 'Not found' });
    res.json(result);
});

router.delete('/solutions/:id', (req, res) => {
    store.deleteSolution(req.params.id);
    res.json({ success: true });
});

// ─── Workflow Steps ───
router.post('/solutions/:id/steps', (req, res) => {
    const step = store.addStep(req.params.id, req.body);
    if (!step) return res.status(404).json({ error: 'Solution not found' });
    res.json(step);
});

router.put('/solutions/:id/steps/:stepId', (req, res) => {
    const step = store.updateStep(req.params.id, req.params.stepId, req.body);
    if (!step) return res.status(404).json({ error: 'Not found' });
    res.json(step);
});

router.delete('/solutions/:id/steps/:stepId', (req, res) => {
    store.deleteStep(req.params.id, req.params.stepId);
    res.json({ success: true });
});

router.put('/solutions/:id/reorder', (req, res) => {
    const { stepIds } = req.body;
    const steps = store.reorderSteps(req.params.id, stepIds);
    if (!steps) return res.status(404).json({ error: 'Not found' });
    res.json(steps);
});

// ─── Execute Workflow (now uses LangGraph orchestrator) ───
router.post('/solutions/:id/execute', upload.single('file'), async (req, res) => {
    try {
        const solution = store.getSolution(req.params.id);
        if (!solution) return res.status(404).json({ error: 'Solution not found' });

        if (solution.steps.length === 0) {
            return res.status(400).json({ error: 'No steps in workflow' });
        }

        // Handle file upload or JSON input
        let inputData = '';
        if (req.file) {
            // Convert uploaded file to text/CSV for LangGraph
            const fileContent = req.file.buffer.toString('utf-8');
            inputData = fileContent;
        } else {
            inputData = req.body.input || '';
        }

        if (!inputData) {
            return res.status(400).json({ error: 'No input data provided' });
        }

        // Use agent_order from request if provided (from frontend), otherwise build from solution steps
        let agentOrder = req.body.agent_order;

        if (!agentOrder || agentOrder.length === 0) {
            // Fallback: build agent order from solution steps (sorted by order)
            // Map step names/endpoints to internal agent names for LangGraph
            const agentNameMap = {
                'profiler': 'profiler',
                'data profiler': 'profiler',
                'auto loader': 'profiler',
                'profile': 'profiler',
                'mit_structured_data_profiler_endpoint': 'profiler',

                'quality': 'quality',
                'data quality check': 'quality',
                'quality check': 'quality',
                'mit_data_quality_agent_endpoint': 'quality',
                'mit_data_quality_agent_endpoint_qa': 'quality',

                'classify': 'classify',
                'classifier': 'classifier',
                'classification': 'classifier',
                'pii guard': 'classifier',
                'mit_data_classifier_endpoint': 'classifier',

                'autoload': 'autoloader',
                'autoloader': 'autoloader',
                'autoloader agent': 'autoloader',
                'auto load': 'autoloader',
                'mit_autoloader_agent_endpoint': 'autoloader'
            };

            agentOrder = solution.steps
                .sort((a, b) => a.order - b.order)
                .map(step => {
                    const stepName = step.name.toLowerCase();
                    const endpointName = (step.endpointName || '').toLowerCase();
                    // Try step name first, then endpoint name
                    return agentNameMap[stepName] || agentNameMap[endpointName] || stepName;
                });
        }

        // Get mock mode preference from request (default: true for mock mode)
        const useMockMode = req.body.useMockMode !== false;

        console.log(`[Execute] Starting LangGraph orchestration for solution ${solution.id}, agents: ${agentOrder.join(', ')} (mapped from steps: ${solution.steps.map(s => s.name).join(', ')}), mode: ${useMockMode ? 'MOCK' : 'REAL'}`);

        // Call the Python LangGraph orchestrator service
        const orchestrationUrl = 'http://localhost:8001/orchestration/start';
        const orchestrationPayload = {
            user_id: 'ui-user',
            input_data: inputData,
            agent_order: agentOrder,
            context: { solution_id: solution.id },
            use_mock_mode: useMockMode
        };

        try {
            const response = await fetch(orchestrationUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(orchestrationPayload)
            });

            if (!response.ok) {
                const errText = await response.text();
                console.error(`[Execute Error] Orchestration service returned ${response.status}: ${errText}`);
                return res.status(500).json({ error: `Orchestration service error: ${response.statusText}` });
            }

            const workflowData = await response.json();

            console.log(`[Execute] Workflow started: ${workflowData.workflow_id}`);

            // Store the workflow info for later retrieval
            store.updateSolution(solution.id, {
                lastRun: { timestamp: new Date().toISOString(), workflow_id: workflowData.workflow_id }
            });

            // Return the workflow ID so the UI can poll for results
            res.json({
                solutionId: solution.id,
                workflow_id: workflowData.workflow_id,
                status: workflowData.status,
                message: 'Workflow started. Use workflow_id to poll for results.'
            });

        } catch (err) {
            console.error(`[Execute Error] Failed to call orchestration service:`, err.message);
            res.status(500).json({ error: `Failed to start orchestration: ${err.message}` });
        }
    } catch (err) {
        console.error('[Execute Error]', err);
        res.status(500).json({ error: err.message });
    }
});

// ─── Helpers ───
function buildPayload(step, input) {
    // All Databricks agent endpoints use the Responses API format: {"input": [{"role":"user","content":"..."}]}
    const content = typeof input === 'string' ? input : JSON.stringify(input);
    return {
        input: [{ role: 'user', content: content }]
    };
}

function extractOutput(response) {
    // Databricks Responses API format: response.output[].content[].text
    try {
        if (response?.output && Array.isArray(response.output)) {
            const texts = [];
            for (const item of response.output) {
                if (item?.content && Array.isArray(item.content)) {
                    for (const content of item.content) {
                        if (content?.text) {
                            texts.push(content.text);
                        }
                    }
                }
            }
            if (texts.length > 0) return texts.join('\n\n');
        }
    } catch (e) {}

    // Fallback for other formats
    if (response?.choices?.[0]?.message?.content) return response.choices[0].message.content;
    if (response?.predictions) return response.predictions;
    if (typeof response === 'string') return response;
    return JSON.stringify(response);
}

function databricksRequest(config, method, apiPath, body) {
    return new Promise((resolve, reject) => {
        if (!config || !config.workspaceUrl || !config.token) {
            return reject(new Error('Databricks configuration missing: workspaceUrl or token'));
        }
        let baseUrl = (config.workspaceUrl || '').replace(/\/+$/, '');
        if (!baseUrl.startsWith('http')) baseUrl = 'https://' + baseUrl;
        const url = new URL(apiPath, baseUrl);
        const isHttps = url.protocol === 'https:';
        const transport = isHttps ? https : http;

        const options = {
            hostname: url.hostname,
            port: url.port || (isHttps ? 443 : 80),
            path: url.pathname + url.search,
            method,
            headers: {
                'Authorization': `Bearer ${config.token}`,
                'Content-Type': 'application/json'
            }
        };

        const req = transport.request(options, (resp) => {
            let data = '';
            resp.on('data', chunk => data += chunk);
            resp.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch {
                    resolve(data);
                }
            });
        });

        req.on('error', reject);
        req.setTimeout(120000, () => { req.destroy(); reject(new Error('Request timeout')); });

        if (body) req.write(JSON.stringify(body));
        req.end();
    });
}

module.exports = router;
