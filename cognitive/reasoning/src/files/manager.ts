import { z } from 'zod';

export interface FileObject {
  id: string;
  object: 'file';
  bytes: number;
  created_at: number;
  filename: string;
  purpose: 'fine-tune' | 'batch' | 'assistants' | 'user_data';
  status: 'uploaded' | 'processed' | 'error';
  content?: string;
}

export const CreateFineTuningJobSchema = z.object({
  training_file: z.string().min(1),
  validation_file: z.string().optional(),
  model: z.string().min(1),
  hyperparameters: z.record(z.any()).optional(),
  suffix: z.string().optional(),
});

export type CreateFineTuningJobRequest = z.infer<typeof CreateFineTuningJobSchema>;

export interface FineTuningJob {
  id: string;
  object: 'fine_tuning.job';
  model: string;
  created_at: number;
  finished_at?: number;
  fine_tuned_model?: string;
  organization_id?: string;
  result_files: string[];
  status: 'validating_files' | 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  validation_file?: string;
  training_file: string;
  trained_tokens?: number;
}

export class FileManager {
  private files: Map<string, FileObject> = new Map();
  private fineTuningJobs: Map<string, FineTuningJob> = new Map();

  uploadFile(filename: string, purpose: FileObject['purpose'], content: string): FileObject {
    const id = `file-${Math.random().toString(36).substring(2, 10)}`;
    const file: FileObject = {
      id,
      object: 'file',
      bytes: Buffer.byteLength(content, 'utf-8'),
      created_at: Math.floor(Date.now() / 1000),
      filename,
      purpose,
      status: 'uploaded',
      content,
    };
    this.files.set(id, file);
    return file;
  }

  getFile(id: string): FileObject | null {
    return this.files.get(id) || null;
  }

  deleteFile(id: string): boolean {
    return this.files.delete(id);
  }

  listFiles(purpose?: string): { object: 'list'; data: FileObject[] } {
    let list = Array.from(this.files.values());
    if (purpose) {
      list = list.filter((f) => f.purpose === purpose);
    }
    return { object: 'list', data: list };
  }

  createFineTuningJob(req: CreateFineTuningJobRequest): FineTuningJob {
    const id = `ftjob-${Math.random().toString(36).substring(2, 10)}`;
    const now = Math.floor(Date.now() / 1000);
    const job: FineTuningJob = {
      id,
      object: 'fine_tuning.job',
      model: req.model,
      created_at: now,
      training_file: req.training_file,
      validation_file: req.validation_file,
      result_files: [],
      status: 'running',
      trained_tokens: 15000,
      fine_tuned_model: `ft:${req.model}:org:${req.suffix || 'custom'}:${now}`,
    };
    this.fineTuningJobs.set(id, job);
    return job;
  }

  getFineTuningJob(id: string): FineTuningJob | null {
    const job = this.fineTuningJobs.get(id);
    if (!job) return null;
    if (job.status === 'running') {
      job.status = 'succeeded';
      job.finished_at = Math.floor(Date.now() / 1000);
    }
    return job;
  }

  cancelFineTuningJob(id: string): FineTuningJob | null {
    const job = this.fineTuningJobs.get(id);
    if (!job) return null;
    if (job.status !== 'succeeded') {
      job.status = 'cancelled';
      job.finished_at = Math.floor(Date.now() / 1000);
    }
    return job;
  }
}
