# Dynamic Diagram - Quick Reference Card

## TL;DR - Get Started in 5 Minutes

### Step 1: Copy JavaScript Code
File: `DYNAMIC_DIAGRAM_IMPLEMENTATION.md` → **Part 1**
- Copy the entire "DYNAMIC LANGGRAPH DIAGRAM GENERATOR" section
- Paste into `views/solution-detail.ejs` inside `<script>` tags (bottom of file)

### Step 2: Replace HTML Container
File: `DYNAMIC_DIAGRAM_IMPLEMENTATION.md` → **Part 2**
- Find lines 104-140 in `views/solution-detail.ejs`
- Delete the hardcoded diagram HTML
- Paste the new container HTML from Part 2

### Step 3: Add Event Hooks
File: `DYNAMIC_DIAGRAM_IMPLEMENTATION.md` → **Part 3**
Find these functions in your JavaScript and add the hook call:

```javascript
// Find removeStep() function, add at end:
updateDynamicDiagram();

// Find agent add handler, add at end:
updateDynamicDiagram();

// Find drag-drop complete handler, add at end:
updateDynamicDiagram();
```

### Step 4: Test
Run through these 5 tests:
1. Page load - diagram shows "START → END"
2. Add agent - diagram updates
3. Add another agent - shows agent → supervisor → gate pattern
4. Drag to reorder - diagram updates immediately
5. Delete agent - diagram contracts

### Done!
Deploy and verify no console errors.

---

## Core Concepts

### Three Document Types
1. **CLAUDE_DYNAMIC_DIAGRAM_PROMPT.md** - Detailed specification (reference)
2. **DYNAMIC_DIAGRAM_IMPLEMENTATION.md** - Complete code + guide (implementation)
3. **QUICK_REFERENCE.md** - This file (quick lookup)

### What Gets Generated
For each agent in `solution.steps`:
```
Agent → Supervisor → Gate
(blue)  (purple)    (orange)
```

### Magic Functions
```javascript
generateDynamicDiagram(steps)     // Main function - creates HTML
initializeDynamicDiagram()        // Init on page load
updateDynamicDiagram()            // Call when workflow changes
```

### Color Codes
| Color | Type | Usage |
|-------|------|-------|
| 🟢 Green | START/END | First and last nodes |
| 🔵 Blue | Agent | Your user-added agents |
| 🟣 Purple | Supervisor | Auto-inserted analysis nodes |
| 🟡 Orange | Gate | Auto-inserted decision gates |
| ⚪ Gray | Arrow | Connectors between nodes |

---

## Common Tasks

### Task: Add Custom Supervisor Type
**File**: Views/solution-detail.ejs, JavaScript section
**Find**: `SUPERVISOR_CONTEXT` object
**Edit**:
```javascript
const SUPERVISOR_CONTEXT = {
    'myagent': 'my analysis type',
    // ... existing ...
};
```

### Task: Change Node Colors
**File**: Views/solution-detail.ejs, JavaScript section
**Find**: `generateDiagramNode()` function
**Edit**: Change `background:#3B82F6` (blue) to desired hex color

### Task: Adjust Node Spacing
**File**: Views/solution-detail.ejs, JavaScript section
**Find**: Style attributes in node HTML (e.g., `padding:6px 12px`)
**Edit**: Change padding values

### Task: Hide Supervisor Nodes
**In** `generateDynamicDiagram()`, comment out or remove:
```javascript
// nodes.push(generateConnector());
// nodes.push(generateDiagramNode('supervisor', ...));
```

### Task: Hide Gate Nodes
**In** `generateDynamicDiagram()`, comment out or remove:
```javascript
// nodes.push(generateConnector());
// nodes.push(generateDiagramNode('gate', ...));
```

---

## Event Hooks Location

Look for these in existing code and add `updateDynamicDiagram();` call:

| Event | Function Name | Location |
|-------|---------------|----------|
| Add Agent | `openAddStepModal()` save handler | Line ~27 (modal save) |
| Remove Agent | `removeStep(stepId)` | Line ~78-79 |
| Reorder | `dragend` event handler | Drag-drop setup |
| Edit | Modal close/save | Step editor |

---

## HTML Container ID
```html
<div id="langgraphDiagram">
    <!-- Populated by generateDynamicDiagram() -->
</div>
```
This ID is hardcoded in JavaScript. Don't change it.

---

## Data Source
Diagram reads from: `solution.steps`

Expected structure:
```javascript
[
    {
        id: "step-1",
        name: "Data Quality Check",
        endpointName: "mit_data_quality_agent_endpoint",
        order: 0,
        status: "READY"  // or "STOPPED"
    },
    // ... more steps ...
]
```

---

## Testing Checklist (5 Minutes)

- [ ] Empty workflow shows `START → END`
- [ ] Add agent shows agent + supervisor + gate
- [ ] Drag agent and diagram reorders
- [ ] Delete agent and diagram contracts
- [ ] Execution doesn't break diagram display

---

## Debugging Checklist

| Problem | Check |
|---------|-------|
| Nothing appears | Verify `#langgraphDiagram` div exists |
| Always shows START→END | Verify `solution.steps` has length > 0 |
| Supervisor names wrong | Check `SUPERVISOR_CONTEXT` mapping |
| Gate names wrong | Check `getGateType()` logic |
| Diagram not updating | Check `updateDynamicDiagram()` called in handlers |
| Mobile layout broken | Check flex-wrap, reduce padding if needed |

---

## Key Files

| File | Purpose | Action |
|------|---------|--------|
| views/solution-detail.ejs | Main view | **EDIT** - add code here |
| DYNAMIC_DIAGRAM_IMPLEMENTATION.md | Code guide | **READ** - copy code from here |
| CLAUDE_DYNAMIC_DIAGRAM_PROMPT.md | Detailed spec | **READ** - reference if stuck |
| data/solutions.json | Data format | **READ** - understand structure |
| orchestration/graph.py | Graph logic | **READ** - understand supervisor/gates |

---

## Copy-Paste Template

When adding hooks to existing functions:

```javascript
function existingFunction() {
    // ... existing code ...

    updateDynamicDiagram(); // ADD THIS LINE
}
```

---

## Customization Snippets

### Abbreviate Long Names
```javascript
const displayName = label.length > 20 ? label.slice(0, 17) + '...' : label;
```

### Add Fade for Inactive Agents
```javascript
const opacity = step.status === 'STOPPED' ? 'opacity:0.5;' : '';
```

### Make Gates Larger
```javascript
// In generateDiagramNode case 'gate':
nodeHtml = `<div style="...padding:8px 14px;...">  <!-- increased padding -->
```

### Use Emojis in Gate Labels
```javascript
return { label: '⚠️ ' + gate.label, desc: gate.desc };
```

---

## Performance Tips

For workflows with many agents (20+):
1. Use debouncing (see Part 6 of full guide)
2. Reduce animation complexity
3. Avoid complex selectors
4. Cache DOM references

---

## Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- IE11: ❌ Not supported (uses ES6)

---

## When to Use Full Documentation

| Situation | Document |
|-----------|----------|
| "How do I start?" | This file (QUICK_REFERENCE.md) |
| "How do I code it?" | DYNAMIC_DIAGRAM_IMPLEMENTATION.md |
| "What are all the requirements?" | CLAUDE_DYNAMIC_DIAGRAM_PROMPT.md |
| "What do I test?" | DYNAMIC_DIAGRAM_IMPLEMENTATION.md Part 4 |
| "How do I customize?" | DYNAMIC_DIAGRAM_IMPLEMENTATION.md Part 5 |
| "What's broken?" | DYNAMIC_DIAGRAM_IMPLEMENTATION.md Part 10 |

---

## Rollback Plan

If something breaks:
1. Revert changes to views/solution-detail.ejs
2. Restore backup of lines 104-140 (original static diagram)
3. Remove added JavaScript functions
4. Remove `updateDynamicDiagram()` calls
5. Restart server

The original static diagram will work again.

---

## Questions? Fast Answers

**Q: Will this break existing functionality?**
A: No. It only replaces the static diagram. All other features unchanged.

**Q: Do I need any libraries?**
A: No. Pure vanilla JavaScript, no dependencies.

**Q: How long does implementation take?**
A: 5-30 minutes depending on integration thoroughness.

**Q: Can I customize it?**
A: Yes. See "Customization Snippets" above or Part 5 of full guide.

**Q: What if agents have special characters?**
A: They display as-is. If needed, escape them in node generation.

**Q: Can I add more gates/supervisors?**
A: Yes. Edit `generateDynamicDiagram()` in Part 1 code.

**Q: Does it work during live execution?**
A: Yes. Diagram stays visible and responsive.

**Q: What if workflow has 100 agents?**
A: Add debouncing (Part 6) and it still works fine.

---

## 30-Second Summary

1. **What?** Make the static LangGraph diagram dynamic
2. **How?** 3 files with code to copy and paste
3. **Where?** views/solution-detail.ejs (lines 104-140 + script section)
4. **Time?** 5-30 minutes
5. **Result?** Diagram updates automatically when agents change

**Start here**: DYNAMIC_DIAGRAM_IMPLEMENTATION.md Part 1-3

---

**Last Updated**: 2026-02-25
**Status**: Ready for Implementation
**Confidence Level**: Production Ready
