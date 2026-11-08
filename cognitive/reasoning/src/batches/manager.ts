import { z } from 'zod';

export const CreateBatchSchema = z.object({
  input_file_id: z.string().min(1),
  endpoint: z.enum(['/v1/chat/completions', '/v1/embeddings']),
  completion_window: z.enum(['24h']).default('24h'),
  metadata: z.record(z.string()).optional(),
});

export type CreateBatchRequest = z.infer<typeof CreateBatchSchema>;

export type BatchStatus =
  | 'validating'
  | 'in_progress'
  | 'completed'
  | 'cancelling'
  | 'cancelled'
  | 'failed'
  | 'expired';

export interface BatchObject {
  id: string;
  object: 'batch';
  endpoint: string;
  errors?: unknown;
  input_file_id: string;
  completion_window: string;
  status: BatchStatus;
  output_file_id?: string;
  error_file_id?: string;
  created_at: number;
  in_progress_at?: number;
  expires_at?: number;
  finalizing_at?: number;
  completed_at?: number;
  failed_at?: number;
  cancelled_at?: number;
  request_counts: {
    total: number;
    completed: number;
    failed: number;
  };
  metadata?: Record<string, string>;
}

export class BatchManager {
  private batches: Map<string, BatchObject> = new Map();

  createBatch(req: CreateBatchRequest): BatchObject {
    const id = `batch_${Math.random().toString(36).substring(2, 11)}`;
    const now = Math.floor(Date.now() / 1000);
    const batch: BatchObject = {
      id,
      object: 'batch',
      endpoint: req.endpoint,
      input_file_id: req.input_file_id,
      completion_window: req.completion_window,
      status: 'in_progress',
      created_at: now,
      in_progress_at: now,
      expires_at: now + 86400,
      request_counts: {
        total: 10,
        completed: 0,
        failed: 0,
      },
      metadata: req.metadata,
    };

    this.batches.set(id, batch);
    return batch;
  }

  getBatch(batchId: string): BatchObject | null {
    const batch = this.batches.get(batchId);
    if (!batch) return null;

    // Simulate progress if still in_progress
    if (batch.status === 'in_progress') {
      batch.request_counts.completed = Math.min(
        batch.request_counts.total,
        batch.request_counts.completed + 2,
      );
      if (batch.request_counts.completed === batch.request_counts.total) {
        batch.status = 'completed';
        batch.completed_at = Math.floor(Date.now() / 1000);
        batch.output_file_id = `file_out_${batch.id}`;
      }
    }
    return batch;
  }

  cancelBatch(batchId: string): BatchObject | null {
    const batch = this.batches.get(batchId);
    if (!batch) return null;
    if (batch.status === 'completed' || batch.status === 'failed') {
      return batch;
    }
    batch.status = 'cancelled';
    batch.cancelled_at = Math.floor(Date.now() / 1000);
    return batch;
  }

  listBatches(limit = 20): { object: 'list'; data: BatchObject[]; has_more: boolean } {
    const all = Array.from(this.batches.values()).sort((a, b) => b.created_at - a.created_at);
    const data = all.slice(0, limit);
    return {
      object: 'list',
      data,
      has_more: all.length > limit,
    };
  }
}
