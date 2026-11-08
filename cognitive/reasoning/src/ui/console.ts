// Belongs to app surface. Temporarily hosted in the gateway. To be moved out.

export function renderConsoleHtml(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Model Gateway — Control Console & Playground</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f17;
      --card-bg: rgba(18, 24, 38, 0.75);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #3b82f6;
      --accent-glow: rgba(59, 130, 246, 0.25);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --success: #10b981;
      --warning: #f59e0b;
      --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.12) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.12) 0px, transparent 50%);
      color: var(--text);
      font-family: var(--font);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      padding: 1.25rem 2rem;
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(12px);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 700;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
    }

    .brand-badge {
      font-size: 0.75rem;
      padding: 0.2rem 0.5rem;
      border-radius: 9999px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.3);
      font-weight: 600;
    }

    main {
      flex: 1;
      max-width: 1300px;
      width: 100%;
      margin: 0 auto;
      padding: 2rem;
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 2rem;
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      backdrop-filter: blur(16px);
      padding: 1.5rem;
    }

    h2 {
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .stat-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
      margin-bottom: 1.5rem;
    }

    .stat-box {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.85rem;
    }

    .stat-label { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.35rem; }
    .stat-val { font-size: 1.25rem; font-weight: 700; color: #fff; }

    .control-group {
      margin-bottom: 1rem;
    }

    label {
      display: block;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
    }

    select, input, textarea {
      width: 100%;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.65rem 0.85rem;
      color: #fff;
      font-family: var(--font);
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.15s ease;
    }

    select:focus, input:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }

    textarea {
      resize: vertical;
      min-height: 120px;
    }

    button.btn-primary {
      width: 100%;
      background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 0.75rem 1.25rem;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s ease, transform 0.1s ease;
    }

    button.btn-primary:hover {
      opacity: 0.95;
      transform: translateY(-1px);
    }

    .output-panel {
      display: flex;
      flex-direction: column;
      height: 100%;
    }

    .output-box {
      flex: 1;
      background: #06090e;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      font-family: var(--mono);
      font-size: 0.88rem;
      line-height: 1.6;
      color: #e2e8f0;
      overflow-y: auto;
      white-space: pre-wrap;
      min-height: 400px;
    }

    .meta-bar {
      display: flex;
      gap: 1.5rem;
      margin-top: 1rem;
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    .meta-item { display: flex; align-items: center; gap: 0.4rem; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
        <polyline points="2 17 12 22 22 17"></polyline>
        <polyline points="2 12 12 17 22 12"></polyline>
      </svg>
      Model Gateway Console
      <span class="brand-badge">Engine Online</span>
    </div>
    <div style="font-size: 0.85rem; color: var(--text-muted);">TypeScript · Hono · Strict Zod</div>
  </header>

  <main>
    <section class="card">
      <h2>System Telemetry</h2>
      <div class="stat-grid">
        <div class="stat-box">
          <div class="stat-label">Providers Ready</div>
          <div class="stat-val" id="providers-count">7</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">P95 Proxy Latency</div>
          <div class="stat-val" style="color: var(--success);">&lt; 1ms</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Active Tiers</div>
          <div class="stat-val">3</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Memory Overhead</div>
          <div class="stat-val">~18 MB</div>
        </div>
      </div>

      <h2>Request Parameters</h2>
      <form id="playground-form">
        <div class="control-group">
          <label for="model-select">Target Model / Virtual Tier</label>
          <select id="model-select">
            <option value="smart-tier">smart-tier (Failover: Claude-3.5 ➔ GPT-4o)</option>
            <option value="fast-tier">fast-tier (Low-latency: GPT-4o-mini)</option>
            <option value="anthropic.claude-3-5-sonnet-20241022-v2:0">bedrock (Claude 3.5 on Bedrock)</option>
            <option value="gemini-1.5-pro">gemini-1.5-pro (Google Gemini)</option>
            <option value="llama3.1">ollama (Local Llama 3.1)</option>
          </select>
        </div>

        <div class="control-group">
          <label for="temperature">Temperature</label>
          <input type="number" id="temperature" min="0" max="2" step="0.1" value="0.7">
        </div>

        <div class="control-group">
          <label for="prompt">Prompt</label>
          <textarea id="prompt" placeholder="Ask a question or enter instructions...">Explain how distributed AI gateways optimize inference latency across cloud and local providers.</textarea>
        </div>

        <button type="submit" class="btn-primary" id="send-btn">Send Request</button>
      </form>
    </section>

    <section class="card output-panel">
      <h2>Live Gateway Response</h2>
      <div class="output-box" id="response-box">Awaiting request dispatch... Responses and tokens will stream here in real time.</div>
      <div class="meta-bar">
        <div class="meta-item"><span class="dot"></span> Status: <span id="meta-status">Idle</span></div>
        <div class="meta-item">Duration: <span id="meta-time">0 ms</span></div>
        <div class="meta-item">Tokens: <span id="meta-tokens">0</span></div>
      </div>
    </section>
  </main>

  <script>
    const form = document.getElementById('playground-form');
    const sendBtn = document.getElementById('send-btn');
    const responseBox = document.getElementById('response-box');
    const metaStatus = document.getElementById('meta-status');
    const metaTime = document.getElementById('meta-time');
    const metaTokens = document.getElementById('meta-tokens');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const model = document.getElementById('model-select').value;
      const temperature = parseFloat(document.getElementById('temperature').value) || 0.7;
      const prompt = document.getElementById('prompt').value;

      responseBox.textContent = 'Routing request through gateway pipeline...';
      metaStatus.textContent = 'In-Flight';
      sendBtn.disabled = true;
      const start = performance.now();

      try {
        const res = await fetch('/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model,
            temperature,
            messages: [{ role: 'user', content: prompt }]
          })
        });

        const elapsed = Math.round(performance.now() - start);
        metaTime.textContent = elapsed + ' ms';

        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: { message: res.statusText } }));
          responseBox.textContent = 'Error ' + res.status + ':\\n' + JSON.stringify(err, null, 2);
          metaStatus.textContent = 'Failed (' + res.status + ')';
        } else {
          const data = await res.json();
          const content = data.choices?.[0]?.message?.content || JSON.stringify(data, null, 2);
          responseBox.textContent = content;
          metaStatus.textContent = '200 OK';
          if (data.usage) {
            metaTokens.textContent = (data.usage.total_tokens || 0) + ' (' + data.usage.prompt_tokens + ' in, ' + data.usage.completion_tokens + ' out)';
          }
        }
      } catch (err) {
        responseBox.textContent = 'Network Error: ' + err.message;
        metaStatus.textContent = 'Error';
      } finally {
        sendBtn.disabled = false;
      }
    });
  </script>
</body>
</html>`;
}
