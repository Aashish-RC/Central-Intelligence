import { describe, expect, it } from 'vitest';
import { DynamicSemanticToolSearch } from '../src/mcp/tool-search.js';

describe('Feature 40: Dynamic Semantic Tool Search (Tool RAG / Injected Tool Catalog)', () => {
  const tools = [
    {
      name: 'get_weather_forecast',
      description: 'Fetch current weather and 7-day temperature forecast for a city',
      inputSchema: { type: 'object', properties: { city: { type: 'string' } } },
    },
    {
      name: 'execute_sql_query',
      description: 'Run SQL select queries against relational PostgreSQL database tables',
      inputSchema: { type: 'object', properties: { sql: { type: 'string' } } },
    },
    {
      name: 'send_email_notification',
      description: 'Deliver email messages via SMTP with subject and recipient address',
      inputSchema: {
        type: 'object',
        properties: { to: { type: 'string' }, subject: { type: 'string' } },
      },
    },
    {
      name: 'calculate_tax_deductions',
      description: 'Compute fiscal year business accounting tax expenses and write-offs',
      inputSchema: { type: 'object', properties: { income: { type: 'number' } } },
    },
  ];

  it('ranks and filters tools matching semantic intent of query', () => {
    const searcher = new DynamicSemanticToolSearch(tools);

    const weatherResults = searcher.search(
      'Will it rain tomorrow in Paris? temperature forecast',
      1,
    );
    expect(weatherResults.length).toBe(1);
    expect(weatherResults[0].name).toBe('get_weather_forecast');

    const sqlResults = searcher.search('query postgres database customer rows table', 1);
    expect(sqlResults.length).toBe(1);
    expect(sqlResults[0].name).toBe('execute_sql_query');
  });

  it('returns all tools if topK exceeds total tool count', () => {
    const searcher = new DynamicSemanticToolSearch(tools);
    const results = searcher.search('anything', 10);
    expect(results.length).toBe(4);
  });
});
