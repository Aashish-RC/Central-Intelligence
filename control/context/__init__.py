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
]
