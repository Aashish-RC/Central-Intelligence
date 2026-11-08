import { z } from 'zod';

export const VideoGenerationSchema = z.object({
  prompt: z.string().min(1),
  model: z.string().default('sora-1.0'),
  duration_seconds: z.number().int().min(1).max(60).default(5),
  resolution: z.enum(['720p', '1080p', '4k']).default('720p'),
  aspect_ratio: z.enum(['16:9', '9:16', '1:1']).default('16:9'),
});

export type VideoGenerationRequest = z.infer<typeof VideoGenerationSchema>;

export type VideoStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface VideoJob {
  id: string;
  object: 'video';
  model: string;
  status: VideoStatus;
  prompt: string;
  video_url?: string;
  duration_seconds: number;
  resolution: string;
  created_at: number;
  completed_at?: number;
  progress_percentage: number;
}

export class VideoGenerator {
  private jobs: Map<string, VideoJob> = new Map();

  createVideoJob(req: VideoGenerationRequest): VideoJob {
    const id = `vid_${Math.random().toString(36).substring(2, 11)}`;
    const now = Math.floor(Date.now() / 1000);
    const job: VideoJob = {
      id,
      object: 'video',
      model: req.model,
      status: 'processing',
      prompt: req.prompt,
      duration_seconds: req.duration_seconds,
      resolution: req.resolution,
      created_at: now,
      progress_percentage: 25,
    };

    this.jobs.set(id, job);
    return job;
  }

  getVideoJob(id: string): VideoJob | null {
    const job = this.jobs.get(id);
    if (!job) return null;

    if (job.status === 'processing') {
      job.progress_percentage = Math.min(100, job.progress_percentage + 35);
      if (job.progress_percentage >= 100) {
        job.status = 'completed';
        job.completed_at = Math.floor(Date.now() / 1000);
        job.video_url = `https://videos.gateway.local/renders/${job.id}.mp4`;
      }
    }

    return job;
  }

  listVideos(limit = 20): { object: 'list'; data: VideoJob[] } {
    return {
      object: 'list',
      data: Array.from(this.jobs.values()).slice(0, limit),
    };
  }
}
