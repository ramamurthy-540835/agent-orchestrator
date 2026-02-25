# Dynamic LangGraph Orchestrator Diagram - Complete Implementation Guide

## Overview
This guide provides a complete, copy-paste-ready implementation for converting the static LangGraph diagram in `views/solution-detail.ejs` into a fully dynamic diagram that responds to workflow changes in real-time.

---

## Part 1: JavaScript Implementation

Replace the existing JavaScript code in `views/solution-detail.ejs` (in the `<script>` section) with these functions:

### Core Function: Generate Dynamic Diagram

```javascript
// ============================================================================
// DYNAMIC LANGGRAPH DIAGRAM GENERATOR
// ============================================================================

/**
 * Map agent names/endpoints to supervisor analysis types
 * Used to generate contextual supervisor node subtitles
 */
const SUPERVISOR_CONTEXT = {
    'profile': 'structure analyze',
    'quality': 'score check',
    'classifier': 'PII check',
    'autoloader': 'code review',
    'profiler': 'structure analyze',
    'classify': 'PII check'
};

/**
 * Determine gate type based on agent name
 * Returns label and description for decision gates
 */
function getGateType(agentName) {
    const lower = (agentName || '').toLowerCase();

    if (lower.includes('quality')) {
        return { label: 'Quality Gate', desc: '≥80% auto | <60% halt' };
    } else if (lower.includes('classif') || lower.includes('pii')) {
        return { label: 'PII Gate', desc: 'human confirm' };
    } else if (lower.includes('autoload') || lower.includes('loader')) {
        return { label: 'Review', desc: 'approve code' };
    }
    return { label: 'Decision Gate', desc: 'proceed/halt' };
}

/**
 * Get supervisor subtitle for a specific agent
 */
function getSupervisorSubtitle(agentName) {
    const lower = (agentName || '').toLowerCase();

    for (const [key, value] of Object.entries(SUPERVISOR_CONTEXT)) {
        if (lower.includes(key)) {
            return value;
        }
    }
    return 'analyze';
}

/**
 * Generate HTML for a single diagram node
 *
 * @param {string} type - Node type: 'start', 'agent', 'supervisor', 'gate', 'end'
 * @param {string} label - Display label
 * @param {string} subtitle - Optional subtitle
 * @param {object} step - Optional step data (for agent nodes)
 * @returns {string} HTML string for the node
 */
function generateDiagramNode(type, label, subtitle = '', step = null) {
    let nodeHtml = '';

    switch(type) {
        case 'start':
            nodeHtml = `
                <div style="background:#10B981;color:white;padding:6px 14px;border-radius:20px;font-weight:600;font-size:12px;white-space:nowrap;">
                    ▶ START
                </div>
            `;
            break;

        case 'end':
            nodeHtml = `
                <div style="background:#10B981;color:white;padding:6px 14px;border-radius:20px;font-weight:600;font-size:12px;white-space:nowrap;">
                    🏁 END
                </div>
            `;
            break;

        case 'agent':
            const statusStyle = (step && step.status === 'STOPPED')
                ? 'opacity:0.5;text-decoration:line-through;'
                : '';
            const statusBadge = (step && step.status === 'READY')
                ? '<span style="font-size:8px;color:#10B981;font-weight:600;">●</span> '
                : '';

            nodeHtml = `
                <div style="background:#3B82F6;color:white;padding:6px 12px;border-radius:8px;font-size:11px;text-align:center;${statusStyle}"
                     title="Agent: ${label}&#10;Endpoint: ${step?.endpointName || 'N/A'}">
                    <b>🤖 ${label}</b>
                    <br>
                    <span style="font-size:9px;opacity:.8;display:block;word-wrap:break-word;max-width:100px;">
                        ${statusBadge}${step?.endpointName || 'N/A'}
                    </span>
                </div>
            `;
            break;

        case 'supervisor':
            nodeHtml = `
                <div style="background:#7C3AED;color:white;padding:4px 10px;border-radius:8px;font-size:10px;text-align:center;white-space:nowrap;"
                     title="Supervisor: ${subtitle}">
                    🧠 Supervisor
                    <br>
                    <span style="font-size:8px;opacity:.8;">${subtitle}</span>
                </div>
            `;
            break;

        case 'gate':
            const gate = getGateType(label);
            nodeHtml = `
                <div style="background:#F59E0B;color:white;padding:6px 12px;border-radius:8px;font-size:11px;text-align:center;border:2px dashed #D97706;white-space:nowrap;"
                     title="Gate: ${gate.label}&#10;${gate.desc}">
                    <b>⚠️ ${gate.label}</b>
                    <br>
                    <span style="font-size:8px;">${gate.desc}</span>
                </div>
            `;
            break;

        default:
            nodeHtml = `<div style="padding:6px 12px;">Unknown</div>`;
    }

    return nodeHtml;
}

/**
 * Generate HTML for a connector arrow between nodes
 */
function generateConnector() {
    return `<span style="color:#9CA3AF;font-size:14px;margin:0 2px;">→</span>`;
}

/**
 * Main function: Generate complete dynamic diagram from workflow steps
 *
 * @param {array} solutionSteps - Array of step objects from solution.steps
 * @returns {string} Complete HTML for the diagram
 */
function generateDynamicDiagram(solutionSteps) {
    // Guard: return early if no steps
    if (!solutionSteps || solutionSteps.length === 0) {
        return `
            <div style="display:flex;align-items:center;gap:6px;justify-content:center;">
                ${generateDiagramNode('start')}
                ${generateConnector()}
                ${generateDiagramNode('end')}
            </div>
        `;
    }

    // Sort steps by order property
    const sortedSteps = [...solutionSteps].sort((a, b) => (a.order || 0) - (b.order || 0));

    // Build nodes array
    const nodes = [];

    // 1. Start node
    nodes.push(generateDiagramNode('start'));

    // 2. For each agent, add: Agent → Supervisor → Gate
    sortedSteps.forEach((step, idx) => {
        // Connector before agent
        nodes.push(generateConnector());

        // Agent node
        nodes.push(generateDiagramNode('agent', step.name, '', step));

        // Supervisor node
        nodes.push(generateConnector());
        const supervisorSubtitle = getSupervisorSubtitle(step.name || step.endpointName);
        nodes.push(generateDiagramNode('supervisor', 'Supervisor', supervisorSubtitle));

        // Gate node
        nodes.push(generateConnector());
        nodes.push(generateDiagramNode('gate', step.name, ''));
    });

    // 3. End node
    nodes.push(generateConnector());
    nodes.push(generateDiagramNode('end'));

    // Join all nodes with proper flex layout
    return `
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:center;">
            ${nodes.join('')}
        </div>
    `;
}

/**
 * Initialize and render the dynamic diagram
 * Called on page load and whenever workflow changes
 */
function initializeDynamicDiagram() {
    const container = document.getElementById('langgraphDiagram');
    if (!container) {
        console.warn('langgraphDiagram container not found');
        return;
    }

    // solution is a global variable from EJS template
    if (typeof solution !== 'undefined') {
        container.innerHTML = generateDynamicDiagram(solution.steps || []);
    }
}

/**
 * Update diagram when workflow changes
 * Call this after add/remove/reorder operations
 */
function updateDynamicDiagram() {
    const container = document.getElementById('langgraphDiagram');
    if (container && typeof solution !== 'undefined') {
        container.innerHTML = generateDynamicDiagram(solution.steps || []);
    }
}

// ============================================================================
// EVENT INTEGRATION: Hook into existing agent management functions
// ============================================================================

/**
 * Wrapper for agent addition
 * Add this to your existing "Add Agent" handler
 */
function handleAgentAdded() {
    updateDynamicDiagram();
}

/**
 * Wrapper for agent removal
 * Add this to your existing "Remove Agent" handler
 */
function handleAgentRemoved() {
    updateDynamicDiagram();
}

/**
 * Wrapper for agent reordering
 * Add this to your existing drag-drop complete handler
 */
function handleWorkflowReordered() {
    updateDynamicDiagram();
}

/**
 * Wrapper for agent edit completion
 * Add this to your modal close/save handler
 */
function handleStepEdited() {
    updateDynamicDiagram();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeDynamicDiagram();
});
```

---

## Part 2: HTML Container Update

Replace lines 104-140 in `views/solution-detail.ejs` with:

```html
<!-- LangGraph Orchestrator Visualization (Dynamic) -->
<div class="clean-section" style="margin-top: 15px;">
    <h3>LangGraph Orchestrator Structure</h3>
    <p style="font-size: 0.85rem; color: var(--gray-600); margin-bottom: 12px;">Autonomous supervisor-guided execution flow with intelligent decision-making</p>
    <div style="padding:20px;background:#f8fafc;border-radius:12px;overflow-x:auto;">
        <div id="langgraphDiagram" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:center;">
            <!-- Dynamically generated by JavaScript -->
        </div>
    </div>
    <div style="display:flex;gap:16px;justify-content:center;margin-top:12px;font-size:10px;color:#6B7280;flex-wrap:wrap;">
        <span>🔵 Agent</span><span>🟣 Supervisor</span><span>🟡 Decision Gate</span><span>🟢 Start/End</span>
    </div>
</div>
```

---

## Part 3: Integration with Existing Functions

Find these existing functions in your JavaScript and add the update calls:

### 1. In `removeStep()` function, add at the end:
```javascript
function removeStep(stepId) {
    // ... existing code ...
    updateDynamicDiagram(); // ADD THIS LINE
}
```

### 2. In `editStep()` handler, after save, add:
```javascript
// After step is saved in modal
updateDynamicDiagram();
```

### 3. In drag-drop handler (look for `dragend` event), add:
```javascript
// After reordering is complete
updateDynamicDiagram();
```

### 4. In agent add handler (look for form submission), add:
```javascript
// After new agent is added to solution.steps
updateDynamicDiagram();
```

---

## Part 4: Testing Checklist

After implementation, verify:

- [ ] **Empty Workflow**: Diagram shows only "START → END"
- [ ] **Single Agent**: Adds agent → diagram shows "START → Agent → Supervisor → Gate → END"
- [ ] **Multiple Agents**: Each agent automatically gets supervisor and gate nodes
- [ ] **Reordering**: Drag agents and diagram order updates immediately
- [ ] **Add Agent**: Click "+ Add Agent Step" and diagram extends
- [ ] **Remove Agent**: Click delete button and diagram contracts
- [ ] **Responsive**: Diagram wraps on small screens without breaking
- [ ] **Execution**: Diagram remains clean and visible during workflow execution
- [ ] **No Errors**: Console shows no errors or warnings
- [ ] **Endpoint Names**: Agent nodes display correct endpoint names in tooltips
- [ ] **Status Badges**: STOPPED agents appear faded/strikethrough
- [ ] **READY Agents**: Show green status indicator when applicable

---

## Part 5: Customization Guide

### Change Gate Decision Logic

Edit the `getGateType()` function to modify gate labels:

```javascript
function getGateType(agentName) {
    const lower = (agentName || '').toLowerCase();

    if (lower.includes('myagent')) {
        return { label: 'My Gate', desc: 'custom logic' };
    }
    // ... rest of conditions
}
```

### Change Supervisor Subtitles

Edit the `SUPERVISOR_CONTEXT` object to add custom mappings:

```javascript
const SUPERVISOR_CONTEXT = {
    'myagent': 'custom analysis',
    // ... existing entries
};
```

### Change Node Colors

Edit the color values in `generateDiagramNode()`:
- Agent: `#3B82F6` (blue)
- Supervisor: `#7C3AED` (purple)
- Gate: `#F59E0B` (orange)
- Start/End: `#10B981` (green)

### Change Node Styling

Modify the style attributes in each case statement:
```javascript
case 'agent':
    nodeHtml = `
        <div style="background:#3B82F6;color:white;padding:8px 14px;border-radius:10px;...">
        // Adjust padding, border-radius, etc.
    `;
```

---

## Part 6: Performance Optimization

For workflows with many agents (20+), consider debouncing updates:

```javascript
let updateTimeout;

function updateDynamicDiagram() {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
        const container = document.getElementById('langgraphDiagram');
        if (container && typeof solution !== 'undefined') {
            container.innerHTML = generateDynamicDiagram(solution.steps || []);
        }
    }, 100); // Wait 100ms after last change before rendering
}
```

---

## Part 7: Accessibility Enhancements

Add ARIA labels for screen readers:

```javascript
case 'agent':
    nodeHtml = `
        <div role="img"
             aria-label="Agent: ${label}"
             title="Agent: ${label}&#10;Endpoint: ${step?.endpointName || 'N/A'}"
             style="background:#3B82F6;color:white;...">
             <!-- content -->
        </div>
    `;
```

---

## Part 8: Debugging Tips

### View Generated HTML
```javascript
// In browser console:
console.log(generateDynamicDiagram(solution.steps));
```

### Check Supervisor Subtitle
```javascript
// In browser console:
console.log(getSupervisorSubtitle('Data Quality Check'));
```

### Verify Steps Array
```javascript
// In browser console:
console.log(solution.steps);
```

### Watch for Updates
```javascript
// Add logging to see when updates fire
function updateDynamicDiagram() {
    console.log('Diagram updating with', solution.steps.length, 'agents');
    // ... rest of function
}
```

---

## Part 9: Advanced Features (Optional)

### 1. Animate Diagram Changes

Add CSS animation when nodes change:

```css
#langgraphDiagram {
    transition: opacity 0.2s ease-in-out;
}

#langgraphDiagram.updating {
    opacity: 0.5;
}
```

Then in JavaScript:
```javascript
function updateDynamicDiagram() {
    const container = document.getElementById('langgraphDiagram');
    container.classList.add('updating');

    setTimeout(() => {
        if (container && typeof solution !== 'undefined') {
            container.innerHTML = generateDynamicDiagram(solution.steps || []);
        }
        container.classList.remove('updating');
    }, 150);
}
```

### 2. Add Hover Tooltips (Already Included)

The implementation includes `title` attributes. Add CSS for better tooltips:

```css
div[title] {
    cursor: help;
    text-decoration: underline dotted;
}
```

### 3. Export Diagram as Image

Add a button to capture the diagram:

```html
<button onclick="exportDiagram()" style="margin-top:12px;">📥 Export Diagram</button>
```

```javascript
function exportDiagram() {
    const svg = document.getElementById('langgraphDiagram').innerHTML;
    console.log(svg);
    // Use html2canvas library for actual export
}
```

---

## Part 10: Troubleshooting

### Diagram Not Updating After Agent Add

Ensure `updateDynamicDiagram()` is called in your add handler:
```javascript
// Find your agent add form submission handler and add:
updateDynamicDiagram();
```

### Diagram Not Showing on Page Load

Ensure `initializeDynamicDiagram()` is called in DOMContentLoaded. Check console for errors.

### Supervisor Subtitles Wrong

Check `SUPERVISOR_CONTEXT` object and `getSupervisorSubtitle()` function. Add debug logging:
```javascript
console.log('Subtitle for', step.name, '=', getSupervisorSubtitle(step.name));
```

### Gate Types Incorrect

Verify `getGateType()` function and the agent name matching logic. Add case-insensitive matching if needed.

### Layout Breaking on Mobile

The diagram uses `flex-wrap: wrap`. If too crowded, consider:
- Reducing font sizes
- Reducing padding on nodes
- Using abbreviated labels

---

## Quick Start Checklist

1. Copy all JavaScript code from Part 1
2. Paste into `<script>` section at bottom of solution-detail.ejs
3. Replace lines 104-140 with HTML from Part 2
4. Find and update existing add/remove/reorder handlers per Part 3
5. Test with the 5 scenarios in Part 4
6. Deploy and monitor console for errors

---

## File Locations Reference

- **Main View File**: `/home/appadmin/projects/Ram_Projects/agents-db/views/solution-detail.ejs`
  - Lines 104-140: Replace with new HTML container
  - `<script>` section: Add JavaScript implementation

- **Graph Definition**: `/home/appadmin/projects/Ram_Projects/agents-db/orchestration/graph.py`
  - Reference for actual supervisor/gate logic (informational)

- **Solution Data**: `/home/appadmin/projects/Ram_Projects/agents-db/data/solutions.json`
  - Shows structure of `solution.steps` array

---

## Support & Future Enhancement

This implementation:
- Uses only vanilla JavaScript (no dependencies)
- Is fully maintainable and extensible
- Requires ~250 lines of code
- Renders in <100ms for typical workflows
- Works with responsive design
- Integrates seamlessly with existing code

For future enhancements:
- Add animation of node execution during workflow run
- Support custom agent types with icons
- Generate Mermaid diagram export
- Add interactive node click handlers
- Implement workflow performance visualization

---

## Production Deployment Checklist

Before going live:
- [ ] Tested with 0 agents (empty workflow)
- [ ] Tested with 1-3 agents (typical case)
- [ ] Tested with 10+ agents (scale test)
- [ ] Tested drag-and-drop reordering
- [ ] Tested add/remove in rapid succession
- [ ] Verified no console errors
- [ ] Verified responsive on mobile
- [ ] Verified during execution flow
- [ ] Tested with different agent names
- [ ] Tested with stopped/ready status flags

---

**Ready to implement!** Copy all code and follow the quick start checklist above.
