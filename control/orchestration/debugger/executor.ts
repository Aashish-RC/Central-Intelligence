/**
 * Live-Debugging Bridge CLI Runner
 * Sourced & ported from Rivet (packages/app-executor/bin/executor.mts) - MIT License
 *
 * Usage:
 *   node executor.js --port 21889
 */

import { startDebuggerServer } from './debuggerServer.js';

const port = Number(process.env.DEBUGGER_PORT || process.argv[2] || 21889);

console.log(`Starting Rivet Live-Debugging Bridge on port ${port}...`);
const server = startDebuggerServer({ port });

process.on('SIGINT', async () => {
  console.log('\nShutting down debugger bridge...');
  await server.stop();
  process.exit(0);
});
