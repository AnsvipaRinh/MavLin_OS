/**
 * OpenCode Task Failover Guard Plugin
 * 
 * Intercepts Task tool invocations via tool.execute.before hook.
 * Prevents exhausted/dead models from being selected by rewriting subagent_type
 * to the next healthy fallback worker using existing session-reuse machinery.
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

console.error('[failover-guard] Plugin loaded');

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = resolve(__dirname, '..');

const OPENCODE_CONFIG = resolve(PROJECT_ROOT, 'opencode.jsonc');
const MODEL_HEALTH = resolve(PROJECT_ROOT, '.opencode', 'sessions', 'model-health.json');
const REGISTRY = resolve(PROJECT_ROOT, '.opencode', 'sessions', 'registry.json');

// Cooldown default from session-reuse.py
const DEFAULT_COOLDOWN_SEC = 10800;

// In-memory cache for plugin state
const migrationCache = new Map(); // task_id -> { lastMigrationTs, lastWorker }

/**
 * Read and parse JSONC file (handles comments)
 */
function readJsonc(filePath) {
    try {
        const content = readFileSync(filePath, 'utf8');
        return JSON.parse(stripJsoncComments(content));
    } catch (e) {
        console.error(`[failover-guard] Failed to read ${filePath}:`, e.message);
        return null;
    }
}

/**
 * Strip JSONC comments (single-line // and multi-line block comments)
 */
function stripJsoncComments(jsonc) {
    let out = '';
    let i = 0;
    let inString = false;
    let esc = false;
    
    while (i < jsonc.length) {
        const c = jsonc[i];
        
        if (inString) {
            out += c;
            if (esc) {
                esc = false;
            } else if (c === '\\') {
                esc = true;
            } else if (c === '"') {
                inString = false;
            }
            i++;
            continue;
        }
        
        if (c === '"') {
            inString = true;
            out += c;
            i++;
            continue;
        }
        
        if (c === '/' && i + 1 < jsonc.length && jsonc[i + 1] === '/') {
            while (i < jsonc.length && jsonc[i] !== '\n') i++;
            continue;
        }
        
        if (c === '/' && i + 1 < jsonc.length && jsonc[i + 1] === '*') {
            i += 2;
            while (i + 1 < jsonc.length && !(jsonc[i] === '*' && jsonc[i + 1] === '/')) {
                i++;
            }
            i += 2;
            continue;
        }
        
        out += c;
        i++;
    }
    
    return out;
}

/**
 * Read opencode.jsonc and extract worker pins: { agentName -> model }
 */
function getWorkerPins() {
    const config = readJsonc(OPENCODE_CONFIG);
    if (!config?.agent) return {};
    
    const pins = {};
    for (const [agentName, spec] of Object.entries(config.agent)) {
        if (spec?.disable) continue;
        if (spec?.model && typeof spec.model === 'string' && spec.model.includes('/')) {
            pins[agentName] = spec.model;
        }
    }
    return pins;
}

/**
 * Get ordered worker list: build first, then build-b, build-c, ...
 */
function getOrderedWorkers(pins) {
    return Object.entries(pins)
        .filter(([agent]) => agent === 'build' || agent.startsWith('build-'))
        .sort((a, b) => {
            if (a[0] === 'build') return -1;
            if (b[0] === 'build') return 1;
            return a[0].localeCompare(b[0]);
        });
}

/**
 * Read model health file and return cooldown remaining for a model (seconds)
 */
function getCooldownRemaining(model) {
    if (!model) return 0;
    
    const health = readJsonc(MODEL_HEALTH);
    if (!health?.models) return 0;
    
    const entry = health.models[model.toLowerCase()];
    if (!entry || typeof entry !== 'object') return 0;
    
    const retryAfter = entry.retryAfter;
    if (typeof retryAfter !== 'number') return 0;
    
    const remaining = retryAfter - Date.now() / 1000;
    return Math.max(0, remaining);
}

/**
 * Resolve next healthy worker, excluding dead/unavailable models
 * Mirrors session-reuse.py resolve_next_worker logic
 */
function resolveNextWorker(excludedModels = []) {
    const pins = getWorkerPins();
    const ordered = getOrderedWorkers(pins);
    
    const excl = new Set(excludedModels.map(m => m.toLowerCase()));
    
    // Load "never" list from model-fallback.json
    const never = getNeverList();
    
    const candidates = [];
    for (const [role, model] of ordered) {
        const low = model.toLowerCase();
        if (excl.has(low) || excl.has(low.split('/').pop())) continue;
        if (never.has(low) || never.has(low.split('/').pop())) continue;
        
        const rem = getCooldownRemaining(model);
        if (rem > 0) continue; // Skip models in cooldown
        
        // Primary build first when eligible; fallbacks ranked by chain order
        const rank = role === 'build' ? 0 : 1;
        candidates.push({ rank, role, model });
    }
    
    if (candidates.length > 0) {
        candidates.sort((a, b) => a.rank - b.rank);
        return { role: candidates[0].role, model: candidates[0].model, wait: null };
    }
    
    // All workers cooling down: report nearest retry
    let soonest = Infinity;
    let soonestModel = '';
    for (const [role, model] of ordered) {
        const rem = getCooldownRemaining(model);
        if (rem > 0 && rem < soonest) {
            soonest = rem;
            soonestModel = model;
        }
    }
    return { role: null, model: null, wait: [soonest, soonestModel] };
}

/**
 * Load "never" list from model-fallback.json
 */
function getNeverList() {
    const chainFile = resolve(PROJECT_ROOT, '.opencode', 'model-fallback.json');
    const chain = readJsonc(chainFile);
    if (!chain?.never) return new Set();
    return new Set(chain.never.map(x => x.toLowerCase()));
}

/**
 * Rotate session worker in registry (mirrors rotate_session_worker)
 */
function rotateSessionWorker(sessionId, newWorker, newModel, reason) {
    const registry = readJsonc(REGISTRY);
    if (!registry?.sessions?.[sessionId]) {
        console.error(`[failover-guard] Session ${sessionId} not found in registry`);
        return false;
    }
    
    const meta = registry.sessions[sessionId];
    const oldWorker = meta.agent;
    const oldModel = meta.model;
    
    meta.agent = newWorker;
    meta.model = newModel;
    meta.lastUsed = new Date().toISOString();
    meta.failure = '';
    meta.lastResult = (meta.lastResult || '') + ` [ROTATED ${oldWorker}/${oldModel} -> ${newWorker}/${newModel}: ${reason}]`;
    meta.migratedFrom = {
        worker: oldWorker,
        model: oldModel,
        at: new Date().toISOString(),
        reason
    };
    
    writeFileSync(REGISTRY, JSON.stringify(registry, null, 2) + '\n');
    console.log(`[failover-guard] Rotated session ${sessionId}: ${oldWorker}/${oldModel} -> ${newWorker}/${newModel} (${reason})`);
    return true;
}

/**
 * Check if subagent_type is a valid configured agent
 */
function isValidAgent(subagentType, validAgents) {
    return validAgents.has(subagentType);
}

/**
 * Check if value looks like a model ID (contains /)
 */
function isModelId(value) {
    return typeof value === 'string' && value.includes('/');
}

/**
 * Check if this is a continuation task (has existing registry entry)
 */
function isContinuationTask(taskId) {
    const registry = readJsonc(REGISTRY);
    return registry?.sessions?.[taskId] !== undefined;
}

/**
 * Get worker name from task's registry entry
 */
function getWorkerFromRegistry(taskId) {
    const registry = readJsonc(REGISTRY);
    return registry?.sessions?.[taskId]?.agent || null;
}

/**
 * Get model for a worker
 */
function getModelForWorker(worker) {
    const pins = getWorkerPins();
    return pins[worker] || null;
}

/**
 * Main hook handler for tool.execute.before
 */
async function handleTaskExecuteBefore(input, output) {
    // Only intercept Task tool. Verified live 2026-10-04: the built-in
    // tool ID is lowercase "task" (GET /experimental/tool/ids).
    if (input.tool !== 'task' && input.tool !== 'Task') return;

    const args = output.args;
    if (!args) return;

    // Verified live 2026-10-04 via /experimental/tool schema: the worker
    // selector field is "subagent_type" (required), continuation id is
    // "task_id" (optional). Never use args.agent here.
    const subagentType = args.subagent_type;
    const taskId = args.task_id;

    // No subagent_type to validate
    if (!subagentType) return;
    
    const validAgents = new Set(Object.keys(getWorkerPins()));
    
    // Case 1: Model ID passed as subagent_type (contains /)
    if (isModelId(subagentType)) {
        console.error(`[failover-guard] REJECT: Model ID "${subagentType}" used as subagent_type`);
        
        // Find the correct worker for this model
        const pins = getWorkerPins();
        let targetWorker = null;
        for (const [worker, model] of Object.entries(pins)) {
            if (model === subagentType) {
                targetWorker = worker;
                break;
            }
        }
        
        // If model not found in pins, resolve from fallback chain
        if (!targetWorker) {
            const result = resolveNextWorker([subagentType]);
            if (result.role) {
                targetWorker = result.role;
            } else {
                throw new Error(`Invalid subagent_type "${subagentType}": model not in fallback chain, and all fallbacks exhausted`);
            }
        }
        
        // Check target worker's health
        const targetModel = getModelForWorker(targetWorker);
        const cooldown = getCooldownRemaining(targetModel);
        if (cooldown > 0) {
            const result = resolveNextWorker([targetModel, subagentType]);
            if (!result.role) {
                throw new Error(`All workers exhausted. Earliest: ${result.wait?.[1]} in ${Math.ceil(result.wait?.[0] || 0)}s`);
            }
            targetWorker = result.role;
        }
        
        console.log(`[failover-guard] REWRITE: ${subagentType} -> ${targetWorker}`);
        args.subagent_type = targetWorker;
        return;
    }
    
    // Case 2: Valid worker but dead model
    if (isValidAgent(subagentType, new Set(Object.keys(getWorkerPins())))) {
        const model = getModelForWorker(subagentType);
        if (!model) {
            console.warn(`[failover-guard] Worker ${subagentType} has no model mapping`);
            return;
        }
        
        const cooldown = getCooldownRemaining(model);
        if (cooldown > 0) {
            console.log(`[failover-guard] Worker ${subagentType} model ${model} in cooldown (${Math.ceil(cooldown)}s remaining)`);
            
            // Find healthy fallback
            const result = resolveNextWorker([model]);
            if (!result.role) {
                const waitInfo = result.wait || [0, 'unknown'];
                throw new Error(`Worker ${subagentType} exhausted (${Math.ceil(cooldown)}s cooldown). All fallbacks exhausted. Earliest: ${waitInfo[1]} in ${Math.ceil(waitInfo[0])}s`);
            }
            
            const newWorker = result.role;
            console.log(`[failover-guard] ROTATE: ${subagentType}/${model} -> ${newWorker}/${getModelForWorker(newWorker)}`);
            
            // For continuation tasks, rotate registry
            if (taskId && isContinuationTask(taskId)) {
                const rotated = rotateSessionWorker(taskId, newWorker, getModelForWorker(newWorker), 'failover-guard');
                if (!rotated) {
                    console.error(`[failover-guard] Failed to rotate registry for ${taskId}`);
                }
            }
            
            // Rewrite subagent_type (verified field name, 2026-10-04)
            args.subagent_type = newWorker;
        }
        return;
    }
    
    // Case 3: Invalid/unknown subagent_type
    if (!validAgents.has(subagentType)) {
        console.error(`[failover-guard] REJECT: Unknown subagent_type "${subagentType}". Valid agents: ${Array.from(validAgents).join(', ')}`);
        throw new Error(`Invalid subagent_type "${subagentType}". Valid agents: ${Array.from(validAgents).join(', ')}`);
    }
    
    // Case 4: Healthy worker - allow through
    return;
}

export default async function (input, options) {
    return {
        "tool.execute.before": handleTaskExecuteBefore
    };
}