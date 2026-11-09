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
]
