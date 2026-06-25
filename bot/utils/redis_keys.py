from datetime import date


def baa_cd(user_id: int, group_id: int) -> str:
    return f"baa:{user_id}:{group_id}"

def gather_cd(user_id: int, group_id: int) -> str:
    return f"gather:{user_id}:{group_id}"

def casino_limit(user_id: int, group_id: int) -> str:
    return f"casino_limit:{user_id}:{group_id}:{date.today()}"

def rate_key(user_id: int) -> str:
    return f"rate:{user_id}"

def rps_session(group_id: int) -> str:
    return f"session:rps:{group_id}"

def lb_group(group_id: int) -> str:
    return f"lb:{group_id}"

def lb_global() -> str:
    return "lb:global"

def maintenance() -> str:
    return "maintenance"
