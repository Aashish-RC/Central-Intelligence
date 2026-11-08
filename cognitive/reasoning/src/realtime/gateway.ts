import { z } from 'zod';

export const RealtimeSessionConfigSchema = z.object({
  modalities: z.array(z.enum(['text', 'audio'])).default(['text', 'audio']),
  instructions: z.string().optional(),
  voice: z
    .enum(['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse'])
    .default('alloy'),
  input_audio_format: z.enum(['pcm16', 'g711_ulaw', 'g711_alaw']).default('pcm16'),
  output_audio_format: z.enum(['pcm16', 'g711_ulaw', 'g711_alaw']).default('pcm16'),
  turn_detection: z
    .object({
      type: z.enum(['server_vad']).default('server_vad'),
      threshold: z.number().min(0).max(1).default(0.5),
      prefix_padding_ms: z.number().default(300),
      silence_duration_ms: z.number().default(500),
    })
    .nullable()
    .optional(),
  tools: z.array(z.any()).default([]),
  temperature: z.number().min(0.6).max(1.2).default(0.8),
  max_response_output_tokens: z.union([z.number(), z.literal('inf')]).default('inf'),
});

export type RealtimeSessionConfig = z.infer<typeof RealtimeSessionConfigSchema>;

export interface RealtimeEvent {
  event_id?: string;
  type: string;
  [key: string]: any;
}

export class RealtimeSession {
  public id: string;
  public config: RealtimeSessionConfig;
  public createdAt: number;
  private messageBuffer: RealtimeEvent[] = [];

  constructor(id: string, config?: Partial<RealtimeSessionConfig>) {
    this.id = id;
    this.createdAt = Date.now();
    this.config = RealtimeSessionConfigSchema.parse(config || {});
  }

  processClientEvent(event: RealtimeEvent): RealtimeEvent[] {
    const responses: RealtimeEvent[] = [];
    const eventId = event.event_id || `evt_${Math.random().toString(36).substring(2, 9)}`;

    switch (event.type) {
      case 'session.update':
        if (event.session) {
          this.config = { ...this.config, ...event.session };
        }
        responses.push({
          event_id: `evt_resp_${Date.now()}`,
          type: 'session.updated',
          session: this.config,
        });
        break;

      case 'input_audio_buffer.append':
        this.messageBuffer.push(event);
        break;

      case 'input_audio_buffer.commit':
        responses.push({
          event_id: `evt_commit_${Date.now()}`,
          type: 'input_audio_buffer.committed',
          item_id: `item_${Date.now()}`,
        });
        break;

      case 'response.create':
        responses.push(
          {
            event_id: `evt_r_created_${Date.now()}`,
            type: 'response.created',
            response: {
              id: `resp_${Date.now()}`,
              status: 'in_progress',
              output: [],
            },
          },
          {
            event_id: `evt_r_done_${Date.now()}`,
            type: 'response.done',
            response: {
              id: `resp_${Date.now()}`,
              status: 'completed',
              output: [
                {
                  type: 'message',
                  role: 'assistant',
                  content: [
                    { type: 'text', text: 'Realtime audio gateway handshake acknowledged.' },
                  ],
                },
              ],
            },
          },
        );
        break;

      default:
        // Echo event acknowledgement
        responses.push({
          event_id: `evt_ack_${Date.now()}`,
          type: 'conversation.item.created',
          item: event,
        });
        break;
    }

    return responses;
  }
}

export class RealtimeGateway {
  private sessions: Map<string, RealtimeSession> = new Map();

  createSession(config?: Partial<RealtimeSessionConfig>): RealtimeSession {
    const id = `sess_${Math.random().toString(36).substring(2, 11)}`;
    const session = new RealtimeSession(id, config);
    this.sessions.set(id, session);
    return session;
  }

  getSession(id: string): RealtimeSession | undefined {
    return this.sessions.get(id);
  }

  deleteSession(id: string): boolean {
    return this.sessions.delete(id);
  }
}
