import { z } from 'zod';

export const EmbeddingsRequestSchema = z.object({
  model: z.string().default('text-embedding-3-small'),
  input: z.union([z.string(), z.array(z.string())]),
  dimensions: z.number().int().optional(),
  encoding_format: z.enum(['float', 'base64']).default('float'),
  user: z.string().optional(),
});

export type EmbeddingsRequest = z.infer<typeof EmbeddingsRequestSchema>;

export interface EmbeddingObject {
  object: 'embedding';
  index: number;
  embedding: number[];
}

export interface EmbeddingsResponse {
  object: 'list';
  data: EmbeddingObject[];
  model: string;
  usage: {
    prompt_tokens: number;
    total_tokens: number;
  };
}

export class EmbeddingsGenerator {
  static generateEmbeddingVector(text: string, dimensions = 64): number[] {
    const vec = new Array(dimensions).fill(0);
    const tokens = text.match(/\w+/g) || [];
    for (const token of tokens) {
      let hash = 0;
      for (let i = 0; i < token.length; i++) {
        hash = (hash << 5) - hash + token.charCodeAt(i);
        hash |= 0;
      }
      const idx = Math.abs(hash) % dimensions;
      vec[idx] += 1;
    }

    const norm = Math.sqrt(vec.reduce((sum, v) => sum + v * v, 0));
    if (norm === 0) return vec;
    return vec.map((v) => Number((v / norm).toFixed(6)));
  }

  static createEmbeddings(req: EmbeddingsRequest): EmbeddingsResponse {
    const inputs = Array.isArray(req.input) ? req.input : [req.input];
    const dim = req.dimensions || 64;

    let totalTokens = 0;
    const data: EmbeddingObject[] = inputs.map((text, index) => {
      totalTokens += Math.max(1, Math.ceil(text.length / 4));
      return {
        object: 'embedding',
        index,
        embedding: EmbeddingsGenerator.generateEmbeddingVector(text, dim),
      };
    });

    return {
      object: 'list',
      data,
      model: req.model,
      usage: {
        prompt_tokens: totalTokens,
        total_tokens: totalTokens,
      },
    };
  }
}
