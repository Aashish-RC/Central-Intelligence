import { z } from 'zod';

export const ImageGenerationSchema = z.object({
  prompt: z.string().min(1),
  model: z.string().default('dall-e-3'),
  n: z.number().int().min(1).max(10).default(1),
  quality: z.enum(['standard', 'hd']).default('standard'),
  response_format: z.enum(['url', 'b64_json']).default('url'),
  size: z.enum(['256x256', '512x512', '1024x1024', '1792x1024', '1024x1792']).default('1024x1024'),
  style: z.enum(['vivid', 'natural']).optional(),
  user: z.string().optional(),
});

export type ImageGenerationRequest = z.infer<typeof ImageGenerationSchema>;

export interface ImageDataItem {
  url?: string;
  b64_json?: string;
  revised_prompt?: string;
}

export interface ImageGenerationResponse {
  created: number;
  data: ImageDataItem[];
}

export interface ImageProviderClient {
  generate(req: ImageGenerationRequest): Promise<ImageGenerationResponse>;
}

export class DefaultImageProvider implements ImageProviderClient {
  private apiKey?: string;

  constructor(apiKey?: string) {
    this.apiKey = apiKey;
  }

  async generate(req: ImageGenerationRequest): Promise<ImageGenerationResponse> {
    const created = Math.floor(Date.now() / 1000);
    const data: ImageDataItem[] = [];

    for (let i = 0; i < req.n; i++) {
      if (req.response_format === 'b64_json') {
        const dummyPixel =
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
        data.push({
          b64_json: dummyPixel,
          revised_prompt: `High-fidelity rendering of: ${req.prompt}`,
        });
      } else {
        data.push({
          url: `https://images.gateway.local/generations/${created}-${i}.png`,
          revised_prompt: `High-fidelity rendering of: ${req.prompt}`,
        });
      }
    }

    return {
      created,
      data,
    };
  }
}

export class ImageRouter {
  private client: ImageProviderClient;

  constructor(client?: ImageProviderClient) {
    this.client = client || new DefaultImageProvider();
  }

  async handleGeneration(body: unknown): Promise<ImageGenerationResponse> {
    const validated = ImageGenerationSchema.parse(body);
    return await this.client.generate(validated);
  }
}
