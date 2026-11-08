/**
 * Task Classifier
 * Analyzes prompts to determine task requirements for OmniRoute Auto Mode
 * Inspired by OmniRoute (domain/pipeline.ts) - MIT License
 */

import type { EngineMessage, Capability } from '../types.js';

export interface TaskClassification {
  primaryTask: Capability;
  requiredCapabilities: Capability[];
  hasMultimodal: boolean;
  estimatedTokens: number;
  complexity: 'simple' | 'moderate' | 'complex';
}

export function classifyTask(messages: EngineMessage[], hasTools = false): TaskClassification {
  const fullText = messages.map((m) => m.content).join('\n');
  const lower = fullText.toLowerCase();

  const hasMultimodal = messages.some(
    (m) => m.attachments && m.attachments.some((a) => a.type === 'image')
  );

  const requiredCapabilities: Capability[] = [];

  if (hasMultimodal) {
    requiredCapabilities.push('multimodal');
  }
  if (hasTools) {
    requiredCapabilities.push('tools');
  }

  // Code detection
  const codePatterns = [
    /```[\w-]*\n[\s\S]*?```/,
    /\b(function|def|class|const|let|var|import|export|return|async|await)\b/,
    /\b(python|javascript|typescript|c\+\+|golang|rust|html|css|sql|json)\b/,
    /\b(debug|refactor|compile|algorithm|syntax|regex|unit test)\b/,
  ];
  const isCode = codePatterns.some((pattern) => pattern.test(lower));

  // Math detection
  const mathPatterns = [
    /\b(calculate|solve|equation|integral|derivative|matrix|theorem|proof|arithmetic)\b/,
    /\b\d+[\s]*[\+\-\*\/\^][\s]*\d+\b/,
    /\b(logarithm|probability|statistics|variance|standard deviation)\b/,
  ];
  const isMath = mathPatterns.some((pattern) => pattern.test(lower));

  // Deep reasoning detection
  const reasoningPatterns = [
    /\b(analyze|critique|evaluate|compare and contrast|step-by-step reasoning|deduce)\b/,
    /\b(philosophical|counterfactual|root cause|strategic implications)\b/,
  ];
  const isReasoning = reasoningPatterns.some((pattern) => pattern.test(lower));

  // Creative writing detection
  const creativePatterns = [
    /\b(story|poem|haiku|script|dialogue|fiction|rhyme|creative write|metaphor)\b/,
  ];
  const isCreative = creativePatterns.some((pattern) => pattern.test(lower));

  // Simple query detection
  const isSimple =
    lower.length < 120 &&
    !isCode &&
    !isMath &&
    !isReasoning &&
    (/\b(hello|hi|what is|define|who is|capital of|translate)\b/.test(lower) || fullText.split(' ').length < 15);

  let primaryTask: Capability = 'fast';
  let complexity: 'simple' | 'moderate' | 'complex' = 'moderate';

  if (isCode) {
    primaryTask = 'code';
    requiredCapabilities.push('code');
    complexity = 'complex';
  } else if (isMath) {
    primaryTask = 'math';
    requiredCapabilities.push('math', 'reasoning');
    complexity = 'complex';
  } else if (isReasoning) {
    primaryTask = 'reasoning';
    requiredCapabilities.push('reasoning');
    complexity = 'complex';
  } else if (isCreative) {
    primaryTask = 'creative';
    requiredCapabilities.push('creative');
    complexity = 'moderate';
  } else if (isSimple) {
    primaryTask = 'fast';
    requiredCapabilities.push('fast');
    complexity = 'simple';
  }

  const estimatedTokens = Math.ceil(fullText.length / 4);

  return {
    primaryTask,
    requiredCapabilities: Array.from(new Set(requiredCapabilities)),
    hasMultimodal,
    estimatedTokens,
    complexity,
  };
}
