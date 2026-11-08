"""Browser Agent: Coordinates multi-step web workflows and enforces human confirmation on consequential steps."""

from typing import List, Optional
from ..core.interfaces import (
    BaseBrowserAgent,
    BaseBrowserSessionRunner,
    BaseConfirmationGate,
)
from ..core.models import (
    ActionRiskLevel,
    BrowserAction,
    BrowserTaskReport,
    ConfirmationStatus,
)
from ..engine.confirmation_rules import ConfirmationRulesGate
from ..runtime.session_runner import BrowserSessionRunner


class BrowserAgent(BaseBrowserAgent):
    """Executes browser workflows and halts before executing consequential actions unless confirmed."""

    def __init__(
        self,
        session_runner: Optional[BaseBrowserSessionRunner] = None,
        confirmation_gate: Optional[BaseConfirmationGate] = None,
    ):
        self.runner = session_runner or BrowserSessionRunner()
        self.gate = confirmation_gate or ConfirmationRulesGate()

    def run_task(
        self,
        task_id: str,
        goal: str,
        planned_actions: List[BrowserAction],
        auto_approve_consequential: bool = False,
    ) -> BrowserTaskReport:
        self.runner.start_session()
        action_log: List[BrowserAction] = []
        confirmations_requested = 0
        confirmations_approved = 0

        for action in planned_actions:
            obs = self.runner.get_current_observation()
            allowed = self.gate.evaluate_and_gate(action, current_url=obs.current_url)

            if not allowed:
                # Consequential action requires human confirmation
                confirmations_requested += 1

                if auto_approve_consequential:
                    # User approved in interactive modal or test mode
                    self.gate.approve_action(action.action_id)
                    confirmations_approved += 1
                    # Re-verify and execute
                    self.runner.execute_action(action)
                    action_log.append(action)
                else:
                    # Halt browsing task and wait for human confirmation
                    action_log.append(action)
                    return BrowserTaskReport(
                        task_id=task_id,
                        goal=goal,
                        actions_executed=len(action_log) - 1,
                        confirmations_requested=confirmations_requested,
                        confirmations_approved=confirmations_approved,
                        success=False,
                        final_url=obs.current_url,
                        error_message=(
                            f"Task paused: Consequential action '{action.action_type.value}' on target "
                            f"'{action.target_selector or action.url}' requires confirmation. "
                            f"Reason: {action.consequential_reason}"
                        ),
                        action_log=action_log,
                    )
            else:
                self.runner.execute_action(action)
                action_log.append(action)

        final_obs = self.runner.get_current_observation()
        return BrowserTaskReport(
            task_id=task_id,
            goal=goal,
            actions_executed=len(action_log),
            confirmations_requested=confirmations_requested,
            confirmations_approved=confirmations_approved,
            success=True,
            final_url=final_obs.current_url,
            extracted_data={"title": final_obs.page_title, "snippet": final_obs.dom_snippet},
            action_log=action_log,
        )
