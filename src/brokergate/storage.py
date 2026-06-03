from brokergate.models import AuditEvent, OrderDraft


class InMemoryStore:
    def __init__(self) -> None:
        self.order_drafts: dict[str, OrderDraft] = {}
        self.audit_events: list[AuditEvent] = []

    def save_draft(self, draft: OrderDraft) -> OrderDraft:
        self.order_drafts[draft.id] = draft
        return draft

    def get_draft(self, draft_id: str) -> OrderDraft | None:
        return self.order_drafts.get(draft_id)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        self.audit_events.append(event)
        return event


store = InMemoryStore()

