"""Dual-Boundary Context Assembler (Layer 9 Crown Jewel, Features 9.11, 9.12).

Provides hardened architectural separation between high-trust system instructions
and low-trust external content (user prompts, tool results, web retrieval, memory).
Neutralizes prompt injections, role confusion, and delimiter escaping.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from control.context.trust.instruction_frame import InstructionFrame
from control.context.trust.injection_detector import InjectionDetector, InjectionDetectionResult
from control.context.trust.untrusted_sandbox import UntrustedBlock


@dataclass
class DualBoundaryAssemblyResult:
    """Output payload from DualBoundaryAssembler."""
    prompt: str
    system_frame: InstructionFrame
    untrusted_blocks: List[UntrustedBlock]
    injections_detected: int
    flagged_sources: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class DualBoundaryAssembler:
    """🚩 Crown Jewel: Dual-Boundary Context Assembler."""

    def __init__(self, detector: Optional[InjectionDetector] = None):
        self.detector = detector or InjectionDetector()

    def assemble_with_boundaries(
        self,
        system_instructions: str,
        user_input: Optional[str] = None,
        tool_outputs: Optional[List[Dict[str, Any]]] = None,
        retrieved_content: Optional[List[Dict[str, Any]]] = None,
        memory_records: Optional[List[Dict[str, Any]]] = None,
    ) -> DualBoundaryAssemblyResult:
        """Assembles prompt with strict dual-boundary trust segregation."""
        # 1. System frame (immutable, high trust)
        system_frame = InstructionFrame(
            content=system_instructions,
            trust_level="system",
            mutable=False,
        )

        untrusted_blocks: List[UntrustedBlock] = []

        # 2. Ingest Memory Records
        if memory_records:
            for mem in memory_records:
                key = mem.get("key", "fact")
                val = mem.get("value") or mem.get("text") or mem.get("content") or ""
                untrusted_blocks.append(
                    UntrustedBlock(
                        content=f"{key}: {val}",
                        source=f"memory:{key}",
                        trust="medium" if mem.get("verified") else "low",
                    )
                )

        # 3. Ingest Retrieved Content (L3 Knowledge)
        if retrieved_content:
            for chunk in retrieved_content:
                text = chunk.get("content") or chunk.get("text") or ""
                source = chunk.get("doc_id") or chunk.get("source") or "knowledge_chunk"
                is_verified = chunk.get("verified", False)
                untrusted_blocks.append(
                    UntrustedBlock(
                        content=text,
                        source=f"retrieval:{source}",
                        trust="medium" if is_verified else "low",
                    )
                )

        # 4. Ingest Tool Outputs (L5 Action)
        if tool_outputs:
            for tool in tool_outputs:
                tool_name = tool.get("name") or tool.get("tool_name") or "tool"
                output_str = str(tool.get("output") or tool.get("result") or "")
                untrusted_blocks.append(
                    UntrustedBlock(
                        content=output_str,
                        source=f"tool:{tool_name}",
                        trust="low",
                    )
                )

        # 5. Ingest User Input
        if user_input:
            untrusted_blocks.append(
                UntrustedBlock(
                    content=user_input,
                    source="user",
                    trust="low",
                )
            )

        # 6. Detect and sanitize injection attempts across all untrusted content
        injections_detected = 0
        flagged_sources = []

        for block in untrusted_blocks:
            detection: InjectionDetectionResult = self.detector.detect(block.content)
            if detection.is_injection:
                injections_detected += 1
                block.flagged = True
                block.threats_detected = detection.matched_patterns
                block.content = detection.sanitized_content
                flagged_sources.append(block.source)

        # 7. Render dual-boundary structured payload
        rendered_system = system_frame.render()
        rendered_blocks = [block.render() for block in untrusted_blocks]

        full_prompt = (
            f"{rendered_system}\n\n"
            "<context_payload>\n"
            + "\n\n".join(rendered_blocks)
            + "\n</context_payload>"
        )

        return DualBoundaryAssemblyResult(
            prompt=full_prompt,
            system_frame=system_frame,
            untrusted_blocks=untrusted_blocks,
            injections_detected=injections_detected,
            flagged_sources=flagged_sources,
            metadata={
                "total_untrusted_blocks": len(untrusted_blocks),
                "injections_neutralized": injections_detected,
            },
        )
