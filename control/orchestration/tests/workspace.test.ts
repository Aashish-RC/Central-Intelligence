/**
 * Tests for Shared Working State Workspace (Feature 8.49)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import { SharedWorkspace } from '../engine/index.js';

describe('Shared Working State Workspace (Feature 8.49)', () => {
  test('1. Artifact creation, versioning, and retrieval', () => {
    const ws = new SharedWorkspace('ws_task_1');

    const a1 = ws.setArtifact('spec_doc', 'Specification', 'Initial draft', 'agent_planner');
    assert.strictEqual(a1.version, 1);
    assert.strictEqual(a1.author, 'agent_planner');

    const a2 = ws.setArtifact('spec_doc', 'Specification', 'Refined draft', 'agent_reviewer');
    assert.strictEqual(a2.version, 2);
    assert.strictEqual(a2.content, 'Refined draft');

    const retrieved = ws.getArtifact('spec_doc');
    assert.strictEqual(retrieved?.version, 2);
    assert.strictEqual(ws.listArtifacts().length, 1);
  });

  test('2. Speculative branching isolates parallel agent edits', () => {
    const ws = new SharedWorkspace('ws_task_2');
    ws.setArtifact('code.py', 'code.py', 'def main(): pass', 'agent_init');

    // Create branch
    ws.createBranch('feature_exp');
    ws.setBranchArtifact('feature_exp', 'code.py', 'code.py', 'def main(): return 42', 'agent_exp');

    // Main workspace remains unchanged
    assert.strictEqual(ws.getArtifact('code.py')?.content, 'def main(): pass');
  });

  test('3. Merge branch incorporates branch edits and detects conflicts', () => {
    const ws = new SharedWorkspace('ws_task_3');
    ws.setArtifact('config.yaml', 'config.yaml', 'port: 8080', 'agent_lead');

    ws.createBranch('branch_dev');
    ws.setBranchArtifact('branch_dev', 'config.yaml', 'config.yaml', 'port: 9090', 'agent_dev');
    // Also add a new file in branch
    ws.setBranchArtifact('branch_dev', 'auth.json', 'auth.json', '{"enabled": true}', 'agent_dev');

    // Concurrent edit on main
    ws.setArtifact('config.yaml', 'config.yaml', 'port: 8081', 'agent_lead');

    // Merge branch back into main
    const result = ws.mergeBranch('branch_dev', 'auto_prefer_branch');
    assert.strictEqual(result.merged.length, 2);
    assert.strictEqual(result.conflicts.length, 1);
    assert.strictEqual(result.conflicts[0].artifactId, 'config.yaml');
    assert.strictEqual(result.conflicts[0].mainAuthor, 'agent_lead');
    assert.strictEqual(result.conflicts[0].branchAuthor, 'agent_dev');

    // New file is now in main
    assert.ok(ws.getArtifact('auth.json') !== undefined);
  });

  test('4. Workspace snapshot and restore', () => {
    const ws = new SharedWorkspace('ws_task_4');
    ws.setArtifact('v1', 'v1', 100, 'agent_1');
    ws.setArtifact('v2', 'v2', 'hello', 'agent_1');

    const snap = ws.snapshot();
    assert.strictEqual(snap.v1, 100);
    assert.strictEqual(snap.v2, 'hello');

    // Mutate state
    ws.setArtifact('v1', 'v1', 999, 'agent_2');
    ws.setArtifact('v3', 'v3', 'extra', 'agent_2');
    assert.strictEqual(ws.listArtifacts().length, 3);

    // Restore
    ws.restoreSnapshot(snap);
    assert.strictEqual(ws.listArtifacts().length, 2);
    assert.strictEqual(ws.getArtifact('v1')?.content, 100);
    assert.strictEqual(ws.getArtifact('v3'), undefined);
  });
});
