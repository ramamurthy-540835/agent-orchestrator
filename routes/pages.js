const express = require('express');
const router = express.Router();
const store = require('../data/store');

router.get('/', (req, res) => {
    const solutions = store.getAllSolutions();
    const workspaces = store.getAllWorkspaces();
    const config = store.getConfig();
    res.render('index', { solutions, workspaces, config });
});

router.get('/solutions/new', (req, res) => {
    const workspaces = store.getAllWorkspaces();
    res.render('solution-form', { solution: null, workspaces, config: store.getConfig() });
});

router.get('/solutions/:id', (req, res) => {
    const solution = store.getSolution(req.params.id);
    if (!solution) return res.redirect('/');
    const workspaces = store.getAllWorkspaces();
    const workspace = solution.workspaceId ? store.getWorkspace(solution.workspaceId) : null;
    res.render('solution-detail', { solution, workspaces, workspace, config: store.getConfig() });
});

router.get('/solutions/:id/edit', (req, res) => {
    const solution = store.getSolution(req.params.id);
    if (!solution) return res.redirect('/');
    const workspaces = store.getAllWorkspaces();
    res.render('solution-form', { solution, workspaces, config: store.getConfig() });
});

router.get('/settings', (req, res) => {
    const workspaces = store.getAllWorkspaces();
    const config = store.getConfig();
    res.render('settings', { config, workspaces });
});

module.exports = router;
