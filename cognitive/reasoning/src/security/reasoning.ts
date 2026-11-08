import crypto from 'node:crypto';
import type { ChatCompletionResponse } from '../types/chat.js';

export type ReasoningIsolationMode = 'preserve' | 'extract' | 'redact' | 'encrypt';

export interface ReasoningIsolationOptions {
  mode: ReasoningIsolationMode;
  encryptionKey?: string; // 32-byte hex or string for AES-256-GCM
}

export class ReasoningIsolationEngine {
  private mode: ReasoningIsolationMode;
  private encryptionKey: Buffer | null = null;

  constructor(options: ReasoningIsolationOptions = { mode: 'extract' }) {
    this.mode = options.mode;
    if (options.encryptionKey) {
      this.encryptionKey = crypto.createHash('sha256').update(options.encryptionKey).digest();
    }
  }

  /**
   * Encrypts plaintext using AES-256-GCM with an authenticated tag.
   */
  public encryptReasoning(text: string): string {
    if (!this.encryptionKey) {
      throw new Error('Encryption key is required for AES-256-GCM reasoning encryption.');
    }
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv('aes-256-gcm', this.encryptionKey, iv);
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    const authTag = cipher.getAuthTag().toString('hex');
    return `${iv.toString('hex')}:${authTag}:${encrypted}`;
  }

  /**
   * Decrypts AES-256-GCM encrypted reasoning text.
   */
  public decryptReasoning(payload: string): string {
    if (!this.encryptionKey) {
      throw new Error('Encryption key is required for AES-256-GCM reasoning decryption.');
    }
    const [ivHex, authTagHex, encryptedHex] = payload.split(':');
    if (!ivHex || !authTagHex || !encryptedHex) {
      throw new Error('Invalid encrypted payload format.');
    }
    const decipher = crypto.createDecipheriv(
      'aes-256-gcm',
      this.encryptionKey,
      Buffer.from(ivHex, 'hex'),
    );
    decipher.setAuthTag(Buffer.from(authTagHex, 'hex'));
    let decrypted = decipher.update(encryptedHex, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  }

  /**
   * Parses reasoning blocks (e.g. <think>...</think>) from text.
   */
  public parseReasoning(content: string): { reasoning: string | null; cleanContent: string } {
    const thinkRegex = /<think>([\s\S]*?)<\/think>/i;
    const match = thinkRegex.exec(content);

    if (match) {
      const reasoning = match[1].trim();
      const cleanContent = content.replace(thinkRegex, '').trim();
      return { reasoning, cleanContent };
    }

    return { reasoning: null, cleanContent: content };
  }

  /**
   * Processes a ChatCompletionResponse according to configured isolation mode.
   */
  public processResponse(response: ChatCompletionResponse): ChatCompletionResponse {
    if (this.mode === 'preserve') return response;

    const choices = response.choices.map((choice) => {
      const content = choice.message.content || '';
      const { reasoning, cleanContent } = this.parseReasoning(content);

      if (!reasoning) {
        return choice;
      }

      const updatedMessage: any = {
        ...choice.message,
        content: cleanContent,
      };

      if (this.mode === 'extract') {
        updatedMessage.reasoning_content = reasoning;
      } else if (this.mode === 'encrypt') {
        updatedMessage.reasoning_content = this.encryptReasoning(reasoning);
        updatedMessage.reasoning_encrypted = true;
      }
      // If 'redact', reasoning is omitted completely

      return {
        ...choice,
        message: updatedMessage,
      };
    });

    return {
      ...response,
      choices,
    };
  }
}
