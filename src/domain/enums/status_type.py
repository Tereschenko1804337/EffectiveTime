from enum import Enum

class StatusType(Enum):
    new = "new"
    in_work = "in work"
    wait_for_detail = "wait for detail"
    info_received = "info received"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"
    deferred = "deferred"
