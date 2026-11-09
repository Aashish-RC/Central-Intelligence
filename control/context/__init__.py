"""Layer 9: Context Engineering Subsystem Package."""

from control.context.assembly.context_assembler import (
    ContextAssembler,
    TokenBudgetConfig,
    AssembledContext,
    ContextSource,
    AssemblyStrategy,
)
from control.context.prompts.templates import PromptTemplate, TemplateRenderError
from control.context.prompts.layering import (
    InstructionTier,
    LayeredDirective,
    InstructionLayerResolver,
)
from control.context.prompts.registry import PromptRegistry, ABExperimentVariant
from control.context.trust.instruction_frame import InstructionFrame
from control.context.trust.untrusted_sandbox import UntrustedBlock
from control.context.trust.injection_detector import InjectionDetector, InjectionDetectionResult
from control.context.trust.boundary_assembler import DualBoundaryAssembler, DualBoundaryAssemblyResult
from control.context.audit.context_audit import ContextAuditLog, ContextAuditRecord
from control.context.cache.prefix_optimizer import (
    PrefixCacheOptimizer,
    CacheableSection,
    SectionStability,
    OptimizedContextResult,
)
from control.context.adapters.anthropic_adapter import AnthropicContextAdapter
from control.context.adapters.openai_adapter import OpenAIContextAdapter
from control.context.adapters.gemini_adapter import GeminiContextAdapter
from control.context.adapters.ollama_adapter import OllamaContextAdapter
from control.context.situational.injector import SituationalInjector, SituationalContext

__all__ = [
    "ContextAssembler",
    "TokenBudgetConfig",
    "AssembledContext",
    "ContextSource",
    "AssemblyStrategy",
    "PromptTemplate",
    "TemplateRenderError",
    "InstructionTier",
    "LayeredDirective",
    "InstructionLayerResolver",
    "PromptRegistry",
    "ABExperimentVariant",
    "InstructionFrame",
    "UntrustedBlock",
    "InjectionDetector",
    "InjectionDetectionResult",
    "DualBoundaryAssembler",
    "DualBoundaryAssemblyResult",
    "ContextAuditLog",
    "ContextAuditRecord",
    "PrefixCacheOptimizer",
    "CacheableSection",
    "SectionStability",
    "OptimizedContextResult",
    "AnthropicContextAdapter",
    "OpenAIContextAdapter",
    "GeminiContextAdapter",
    "OllamaContextAdapter",
    "SituationalInjector",
    "SituationalContext",
]
