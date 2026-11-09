"""Knowledge Access Control Package."""
from .openfga_bridge import check_document_access, filter_results_by_permission

__all__ = ["check_document_access", "filter_results_by_permission"]
